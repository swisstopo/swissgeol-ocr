import logging

import pymupdf

from ocr import Mask
from ocr.crop import downscale_images_x2
from ocr.readingorder import sort_lines
from ocr.textline import TextLine
from ocr.textract import combine_text_lines, textract, clip_rects, MAX_DIMENSION_POINTS
from mypy_boto3_textract import TextractClient as Textractor
from uuid import uuid4
from pathlib import Path
import os


def process_page(
        doc: pymupdf.Document,
        page: pymupdf.Page,
        extractor: Textractor,
        tmp_path_prefix: str,
        confidence_threshold: float,
        mask: Mask | None = None
):
    if mask is None:
        mask = Mask(page)

    page.clean_contents()

    # create a single-page PDF document that can be modified if necessary, before being sent to AWS Textract
    textract_doc = pymupdf.Document()
    textract_doc.insert_pdf(doc, from_page=page.number, to_page=page.number)
    textract_doc_path = OCR.tmp_file_path(tmp_path_prefix, "pdf")

    ten_mb = 10 * 1024 * 1024  # 10 MB
    textract_doc.save(textract_doc_path, deflate=True, garbage=3, use_objstms=1)

    for iteration in range(10):
        page_size = os.path.getsize(textract_doc_path)
        if page_size < ten_mb:
            break
        logging.info(f"  Page size is {page_size / 1024 / 1024:.2f} MB, trying to downscale images.")
        # We only reduce the image resolution in the temporary PDF file that is used for AWS Textact, not in the
        # original PDF file.
        downscale_successful = downscale_images_x2(textract_doc, page_index=0)
        if downscale_successful:
            textract_doc.save(textract_doc_path, deflate=True, garbage=3, use_objstms=1)
        else:
            logging.info(f"  Downscale images was unsuccessful.")
            break

    if os.path.getsize(textract_doc_path) < ten_mb:
        page_ocr = OCR(
            textractor=extractor,
            confidence_threshold=confidence_threshold,
            textract_doc_path=textract_doc_path,
            mask=mask,
            tmp_path_prefix=tmp_path_prefix
        )
        lines_to_draw = page_ocr.apply_ocr()
        os.remove(textract_doc_path)
        logging.info("  {} new lines found".format(len(lines_to_draw)))
        return lines_to_draw
    else:
        logging.info("  Could not reduce page size to below 10MB. Skipping page.")
        return []


class OCR:
    def __init__(
            self,
            textractor: Textractor,
            confidence_threshold: float,
            textract_doc_path: Path,
            mask: Mask,
            tmp_path_prefix: str
    ):
        self.textractor = textractor
        self.confidence_threshold = confidence_threshold
        # single-page PDF document that will be sent to AWS Textract
        self.textract_doc_path = textract_doc_path
        with pymupdf.Document(textract_doc_path) as doc:
            self.page_rect = doc[0].rect
        self.mask = mask
        self.tmp_path_prefix = tmp_path_prefix

    @staticmethod
    def tmp_file_path(tmp_path_prefix, extension: str) -> Path:
        return Path("{}_{}.{}".format(tmp_path_prefix, uuid4(), extension))

    def apply_ocr(self):
        """Apply OCR."""
        text_lines = self._ocr_text_lines()

        draw_lines = []
        for reading_order_block in sort_lines(text_lines):
            lines = reading_order_block.lines

            line_confidence_values = [line.confidence for line in lines]
            avg_confidence = sum(line_confidence_values) / len(line_confidence_values)
            if avg_confidence < self.confidence_threshold:
                # if the block has a low overall confidence (e.g. handwritten text) then individual lines are only included
                # when they have a very high confidence.
                line_confidence_threshold = (1 + self.confidence_threshold) / 2
            else:
                # otherwise, we are flexible and allow anything that is not too far below the avg confidence
                line_confidence_threshold = avg_confidence / 2

            for line in lines:
                if not self.mask.intersects(line.rect):
                    if line.confidence > line_confidence_threshold:
                        draw_lines.append(line)

        return draw_lines

    def _ocr_text_lines(self) -> list[TextLine]:
        text_lines = []
        final_clip_rects = clip_rects(self.page_rect)
        for final_clip_rect in final_clip_rects:
            new_lines = textract(
                self.textract_doc_path,
                self.textractor,
                self.tmp_file_path(self.tmp_path_prefix, "pdf"),
                final_clip_rect
            )
            text_lines = combine_text_lines(text_lines, new_lines)
        return text_lines
