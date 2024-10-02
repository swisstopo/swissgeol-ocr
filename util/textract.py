from __future__ import annotations

import fitz
import os
import backoff
import pymupdf
from botocore.exceptions import ClientError
from textractor import Textractor
from trp.t_pipeline import add_page_orientation
import trp.trp2 as t2
import trp as t1
import textractcaller.t_call as t_call
import statistics


from util.readingorder import TextLine


GET_PIXMAP_ZOOM_FOR_TEXTRACT = 2
MAX_DIMENSION_PIXELS = 4000
MAX_DIMENSION_POINTS = MAX_DIMENSION_PIXELS // GET_PIXMAP_ZOOM_FOR_TEXTRACT


def textract_coordinate_transform(
        clip_rect: fitz.Rect,
        pixmap_rect: fitz.IRect,
        pixmap_with_margin_rect: fitz.IRect,
        rotate: float
) -> fitz.Matrix:
    # The rectangle surrounding the rotated version of the clip (corresponds to the image that was sent to AWS Textract,
    # without margins)
    rotated_clip_rect = (clip_rect.quad * fitz.Matrix(1, 1).prerotate(rotate)).rect

    # Matrix to transform the Textract coordinates to the pixmap coordinates
    transform1 = fitz.Rect(0, 0, 1, 1).torect(pixmap_with_margin_rect)

    # Matrix to transform the pixmap coordinates back to the rotated PyMuPDF coordinates
    transform2 = pixmap_rect.torect(rotated_clip_rect)

    # Matrix to change the PyMuPDF coordinates back to the unrotated version
    transform3 = fitz.Matrix(1, 1).prerotate(-rotate)

    # Matrix to transform the Textract coordinates back to the original unrotated PyMuPDF coordinates
    return transform1 * transform2 * transform3


def text_lines_from_document(
        document: t1.Document,
        transform: fitz.Matrix,
        rotate: float,
        page_height: float
) -> list[TextLine]:
    page = document.pages[0]

    if 'PageOrientationBasedOnWords' in page.custom:
        orientation = page.custom['PageOrientationBasedOnWords']
    else:
        orientation = 0

    return [TextLine.from_textract(line, orientation - rotate, page_height, transform) for line in page.lines]


def textract(doc: fitz.Document, extractor: Textractor, tmp_file_path: str, clip_rect: fitz.Rect, rotate: float) -> list[TextLine]:
    page = doc[0]
    old_rotation = page.rotation
    old_cropbox = page.cropbox

    clip_transformed = clip_rect * page.rect.torect(page.cropbox)

    page.set_cropbox(clip_transformed.intersect(page.mediabox))  # TODO make more robust, e.g. 267123080-bp.pdf
    page.set_rotation(page.rotation + rotate)
    doc.save(tmp_file_path)

    page.set_rotation(old_rotation)
    page.set_cropbox(old_cropbox.intersect(page.mediabox))

    document = call_textract(extractor, tmp_file_path)
    os.remove(tmp_file_path)

    # Matrix to transform Textract coordinates via Pixmap coordinates back to PyMuPDF coordinates
    # TODO cleanup method after removing the Pixmap creation
    transform = textract_coordinate_transform(
        clip_rect=clip_rect,
        pixmap_rect=fitz.IRect(0,0,1,1),
        pixmap_with_margin_rect=fitz.IRect(0,0,1,1),
        rotate=rotate
    )
    return text_lines_from_document(document, transform, rotate, doc[0].rect.height)


def backoff_hdlr(details):
    print("Backing off {wait:0.1f} seconds after {tries} tries.".format(**details))


@backoff.on_exception(backoff.expo,
                      ClientError,
                      on_backoff=backoff_hdlr,
                      base=2)
def call_textract(extractor: Textractor, tmp_file_path: str) -> t1.Document:
    j = t_call.call_textract(
        input_document=tmp_file_path,
        boto3_textract_client=extractor.textract_client,
        call_mode=t_call.Textract_Call_Mode.FORCE_SYNC
    )
    t_document: t2.TDocument = t2.TDocumentSchema().load(j)
    try:
        t_document = add_page_orientation(t_document)
    except statistics.StatisticsError:
        # catch "statistics.StatisticsError: no mode for empty data"
        pass

    return t1.Document(t2.TDocumentSchema().dump(t_document))


def clip_rects(main_rect: fitz.Rect) -> list[fitz.Rect]:
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
            fitz.Rect(x0, y0, x0 + MAX_DIMENSION_POINTS, y0 + MAX_DIMENSION_POINTS).intersect(main_rect)
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
        if fitz.Rect(other_line.rect).intersect(line.rect).get_area() > 0.6 * line.rect.get_area()
    )
