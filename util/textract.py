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


def textract(page: fitz.Page, extractor: Textractor, tmp_file_path: str, clip_rect: fitz.Rect, rotate: float) -> list[TextLine]:
    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(GET_PIXMAP_ZOOM_FOR_TEXTRACT, GET_PIXMAP_ZOOM_FOR_TEXTRACT).prerotate(rotate),
        clip=clip_rect
    )

    # Add a margin to the left and right, to help AWS Textact avoid cutting of text at the left and right edge of the
    # page, especially in multi-column page layouts.
    margin = 0  # TODO: reevaluate this param; it does not work well for ZH 267123021-bp.pdf (p2) and 268124571-bp.pdf
    irect_with_margins = fitz.IRect(-margin, 0, pixmap.width + margin, pixmap.height)
    pixmap_with_margins = fitz.Pixmap(pixmap.colorspace, irect_with_margins)
    pixmap_with_margins.clear_with(255)
    pixmap.set_origin(0, 0)
    pixmap_with_margins.copy(pixmap, pixmap.irect)
    # create a copy that is not modified by the shrinking
    pixmap_with_margins_rect = fitz.IRect(pixmap_with_margins.irect)

    # Respect resolution and file size limits of AWS Textract, otherwise an InvalidParameterException might be raised
    while pixmap_with_margins.width > 10000 or pixmap_with_margins.height > 10000:
        pixmap_with_margins.shrink(1)
    pixmap_with_margins.save(tmp_file_path)
    while os.path.getsize(tmp_file_path) >= 10 * 1024 * 1024:  # 10 MB
        pixmap_with_margins.shrink(1)
        pixmap_with_margins.save(tmp_file_path)

    document = call_textract(extractor, tmp_file_path)
    os.remove(tmp_file_path)

    # Matrix to transform Textract coordinates via Pixmap coordinates back to PyMuPDF coordinates
    transform = textract_coordinate_transform(
        clip_rect=clip_rect,
        pixmap_rect=fitz.IRect(pixmap.irect),
        pixmap_with_margin_rect=pixmap_with_margins_rect,
        rotate=rotate
    )
    return text_lines_from_document(document, transform, rotate, page.rect.height)


def backoff_hdlr(details):
    print("Backing off {wait:0.1f} seconds after {tries} tries.".format(**details))


@backoff.on_exception(backoff.expo,
                      ClientError,
                      on_backoff=backoff_hdlr,
                      base=2)
def call_textract(extractor: Textractor, tmp_file_path: str) -> t1.Document:
    j = t_call.call_textract(input_document=tmp_file_path, boto3_textract_client=extractor.textract_client)
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
