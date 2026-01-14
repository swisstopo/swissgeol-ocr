from __future__ import annotations

from pathlib import Path

import botocore.exceptions
import pymupdf
import os
import backoff
from botocore.exceptions import ClientError
from marshmallow import EXCLUDE, Schema
from marshmallow.fields import Nested, List
from mypy_boto3_textract import TextractClient as Textractor
import trp.trp2 as t2
import trp as t1
import textractcaller.t_call as t_call


from ocr.readingorder import TextLine


MAX_DIMENSION_POINTS = 2000


def textract_coordinate_transform(clip_rect: pymupdf.Rect) -> pymupdf.Matrix:
    # Matrix to transform the Textract coordinates to the rotated PyMuPDF coordinates
    return pymupdf.Rect(0, 0, 1, 1).torect(clip_rect)


def text_lines_from_document(
        document: t1.Document,
        transform: pymupdf.Matrix,
        page_height: float
) -> list[TextLine]:
    page = document.pages[0]

    return [TextLine.from_textract(line, page_height, transform) for line in page.lines]


def textract(doc_path: Path, extractor: Textractor, tmp_file_path: Path, clip_rect: pymupdf.Rect) -> list[TextLine]:
    with pymupdf.Document(doc_path) as doc:
        page = doc[0]
        page_height = page.rect.height  # height of the original, unrotated page, for computing the derotated_rect
        clip_transformed = clip_rect * page.rect.torect(page.cropbox)

        # Even thought the documentation says that the cropbox is always contained in the mediabox, this is not always the
        # case, e.g. 267123080-bp.pdf. The discrepancies are usually very small (floating point accuracy errors?). Even so,
        # a trivial call such as page.set_cropbox(page.cropbox) will fail with an "CropBox not in MediaBox" error, if this
        # is the case. To avoid such errors, we take an explicit intersection with the mediabox whenever we call
        # page.set_cropbox(). Possibly related to: https://github.com/pymupdf/PyMuPDF/issues/1615
        page.set_cropbox(clip_transformed.intersect(page.mediabox))
        doc.save(tmp_file_path, deflate=True, garbage=3, use_objstms=1)
        document = call_textract(extractor, tmp_file_path)
        os.remove(tmp_file_path)

        if document is None:
            return []

        # Matrix to transform Textract coordinates back to PyMuPDF coordinates
        transform = textract_coordinate_transform(clip_rect=clip_rect)

        return text_lines_from_document(document, transform, page_height)


def backoff_hdlr(details):
    print("Backing off {wait:0.1f} seconds after {tries} tries.".format(**details))


@backoff.on_exception(backoff.expo,
                      ClientError,
                      on_backoff=backoff_hdlr,
                      base=2,
                      max_tries=3)
def call_textract(extractor: Textractor, tmp_file_path: Path) -> t1.Document | None:
    if os.path.getsize(tmp_file_path) >= 10 * 1024 * 1024:  # 10 MB
        print("Page larger than 10MB. Skipping page.")
        return None
    try:
        j = t_call.call_textract(
            input_document=str(tmp_file_path),
            boto3_textract_client=extractor,
            call_mode=t_call.Textract_Call_Mode.FORCE_SYNC
        )

        # Workaround for the following combination of issues:
        # - AWS Textract returns a new 'RotationAngle' field as part of the 'Geometry' schema.
        # - The schema defined in the textract-response-parser library does not include this field. This has been
        #   reported, and there even is a PR for it, but this has been open for 4 months and the repository itself
        #   has not been updated for 2 years, so maybe it will never be merged. If the repo is indeed dead, then
        #   we should start looking for an alternative, or even implement the schema directly without relying on a
        #   library.
        #   See https://github.com/aws-samples/amazon-textract-response-parser/issues/192
        #       https://github.com/aws-samples/amazon-textract-response-parser/pull/193
        # - The JSON library marshmallow has a setting 'unknown' that allows you to ignore such JSON fields that
        #   are not defined in the schema. However, this setting does not automatically propagate to nested fields.
        #   See https://github.com/marshmallow-code/marshmallow/issues/980
        # Workaround inspired by https://github.com/marshmallow-code/marshmallow/issues/1428#issuecomment-558297299
        def set_unknown_all(schema: Schema, unknown):
            schema.unknown = unknown
            for field in schema.fields.values():
                if isinstance(field, Nested):
                    set_unknown_all(field.schema, unknown)
                if isinstance(field, List) and isinstance(field.inner, Nested):
                    set_unknown_all(field.inner.schema, unknown)
            return schema

        permissive_schema = set_unknown_all(t2.TDocumentSchema(), EXCLUDE)
        t_document: t2.TDocument = permissive_schema.load(j)
    except extractor.exceptions.InvalidParameterException:
        print("Encountered InvalidParameterException from Textract. Page might require more than 10MB memory. Skipping page.")
        return None
    except botocore.exceptions.SSLError:
        print("Encountered SSLError from Textract. Page might require more than 10MB memory. Skipping page.")
        return None
    except extractor.exceptions.UnsupportedDocumentException:  # 1430.pdf page 18
        print("Encountered UnsupportedDocumentException from Textract. Page might have excessive width or height. Skipping page.")
        return None

    return t1.Document(t2.TDocumentSchema().dump(t_document))


def clip_rects(main_rect: pymupdf.Rect) -> list[pymupdf.Rect]:
    # Create small enough subsections of the page, so that AWS Textract gives good results. Even though Textract
    # officially supports up to 10000px width and height, we see a significant decrease in quality once one dimension
    # exceeds ca. 5000px. (Cf. LGD-319.)
    overlap = MAX_DIMENSION_POINTS // 5

    if main_rect.width <= MAX_DIMENSION_POINTS and main_rect.height <= MAX_DIMENSION_POINTS:
        return [main_rect]
    else:
        x_starts = range(0, int(main_rect.width - overlap), MAX_DIMENSION_POINTS - overlap)
        y_starts = range(0, int(main_rect.height - overlap), MAX_DIMENSION_POINTS - overlap)
        clip_rects = [main_rect]
        clip_rects.extend([
            pymupdf.Rect(x0, y0, x0 + MAX_DIMENSION_POINTS, y0 + MAX_DIMENSION_POINTS).intersect(main_rect)
            for x0 in x_starts
            for y0 in y_starts
        ])
        print("  Applying text extraction also to {} smaller page excerpts.".format(len(clip_rects) - 1))
        return clip_rects


def combine_text_lines(lines1: list[TextLine], lines2: list[TextLine]) -> list[TextLine]:
    keep_lines = [line for line in lines1 if not_covered_in(line, lines2)]
    keep_lines.extend([line for line in lines2 if not_covered_in(line, keep_lines)])
    return keep_lines


def not_covered_in(line: TextLine, other_lines: list[TextLine]) -> bool:
    return not any(
        True
        for other_line in other_lines
        if pymupdf.Rect(other_line.rect).intersect(line.rect).get_area() > 0.6 * line.rect.get_area()
    )
