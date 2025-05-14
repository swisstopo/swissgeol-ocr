import pymupdf

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
        ignore_rects: list[pymupdf.Rect] | None = None
):
    if ignore_rects is None:
        ignore_rects = []

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
        print(f"  Page size is {page_size / 1024 / 1024:.2f} MB, trying to downscale images.")
        # We only reduce the image resolution in the temporary PDF file that is used for AWS Textact, not in the
        # original PDF file.
        downscale_images_x2(textract_doc, page_index=0)
        textract_doc.save(textract_doc_path, deflate=True, garbage=3, use_objstms=1)

    if os.path.getsize(textract_doc_path) < ten_mb:
        page_ocr = OCR(
            textractor=extractor,
            confidence_threshold=confidence_threshold,
            textract_doc_path=textract_doc_path,
            ignore_rects=ignore_rects,
            tmp_path_prefix=tmp_path_prefix
        )
        lines_to_draw = page_ocr.apply_ocr(clip_rect=page.rect)
        os.remove(textract_doc_path)
        print("  {} new lines found".format(len(lines_to_draw)))
        return lines_to_draw
    else:
        print("  Could not reduce page size to below 10MB. Skipping page.")
        return []


class OCR:
    def __init__(
            self,
            textractor: Textractor,
            confidence_threshold: float,
            textract_doc_path: Path,
            ignore_rects: list[pymupdf.Rect],
            tmp_path_prefix: str
    ):
        self.textractor = textractor
        self.confidence_threshold = confidence_threshold
        # single-page PDF document that will be sent to AWS Textract
        self.textract_doc_path = textract_doc_path
        with pymupdf.Document(textract_doc_path) as doc:
            self.page_rect = doc[0].rect
        self.ignore_rects = ignore_rects
        self.tmp_path_prefix = tmp_path_prefix

    @staticmethod
    def tmp_file_path(tmp_path_prefix, extension: str) -> Path:
        return Path("{}_{}.{}".format(tmp_path_prefix, uuid4(), extension))

    def apply_ocr(self, clip_rect: pymupdf.Rect):
        """Apply OCR with double page workaround and vertical check"""
        text_lines = self._ocr_text_lines(clip_rect, rotate=0)

        if ((self.page_rect.height < MAX_DIMENSION_POINTS and self.page_rect.width < MAX_DIMENSION_POINTS) and (
                len(text_lines) > 30
        ) and all(
                not self._intersects_middle(line.rect, line.confidence) for line in text_lines
        )):
            print("  Double page workaround")
            page_rect = self.page_rect

            left_clip_rect = (page_rect * pymupdf.Matrix(0.5, 1))
            left_text_lines = self._ocr_text_lines(left_clip_rect, rotate=0)
            lines_to_draw = self.apply_vertical_check(left_text_lines, left_clip_rect)

            right_clip_rect = (page_rect * pymupdf.Matrix(0.5, 1).pretranslate(page_rect.width, 0))
            right_text_lines = self._ocr_text_lines(right_clip_rect, rotate=0)
            lines_to_draw.extend(self.apply_vertical_check(right_text_lines, right_clip_rect))

            return lines_to_draw
        else:
            return self.apply_vertical_check(text_lines, clip_rect)

    def apply_vertical_check(self, text_lines: list[TextLine], clip_rect: pymupdf.Rect):
        lines_to_draw, processed_rects, vertical_detected = (
            get_ocr_lines(text_lines, self.ignore_rects, self.confidence_threshold, detect_vertical=True)
        )

        if vertical_detected:
            print("  Potential vertical text detected. Running OCR again with horizontal text masked.")
            for rect in processed_rects:
                with pymupdf.Document(self.textract_doc_path) as doc:
                    page = doc[0]
                    page.draw_rect(
                        rect * page.derotation_matrix,
                        width=0,
                        fill=pymupdf.utils.getColor("white")
                    )
                    doc.saveIncr()
            vertical_text_lines = self._ocr_text_lines(clip_rect, rotate=90)
            vertical_draw_lines, _, _ = (
                get_ocr_lines(vertical_text_lines, self.ignore_rects, self.confidence_threshold, detect_vertical=False)
            )
            lines_to_draw.extend(vertical_draw_lines)
        return lines_to_draw

    def _ocr_text_lines(self, clip_rect: pymupdf.Rect, rotate: float) -> list[TextLine]:
        text_lines = []
        final_clip_rects = clip_rects(clip_rect)
        for final_clip_rect in final_clip_rects:
            new_lines = textract(
                self.textract_doc_path,
                self.textractor,
                self.tmp_file_path(self.tmp_path_prefix, "pdf"),
                final_clip_rect,
                rotate
            )
            text_lines = combine_text_lines(text_lines, new_lines)
        return text_lines

    def _intersects_middle(self, line_rect: pymupdf.Rect, confidence: float) -> bool:
        page_middle = (self.page_rect.x0 + self.page_rect.x1) / 2
        return confidence > self.confidence_threshold and not(line_rect.x0 > page_middle or line_rect.x1 < page_middle)


def get_ocr_lines(
        text_lines: list[TextLine],
        ignore_rects: list[pymupdf.Rect],
        confidence_threshold: float,
        detect_vertical: bool = True
) -> (list[TextLine], list[pymupdf.Rect], bool):
    draw_lines = []
    processed_rects = []
    vertical_detected = False
    for reading_order_block in sort_lines(text_lines):
        line_confidence_values = [line.confidence for line in reading_order_block.lines]
        avg_confidence = sum(line_confidence_values) / len(line_confidence_values)
        if avg_confidence < confidence_threshold:
            # if the block has a low overall confidence (e.g. handwritten text) then individual lines are only included
            # when they have a very high confidence.
            line_confidence_threshold = (1 + confidence_threshold) / 2
        else:
            # otherwise, we are flexible and allow anything that is not too far below the avg confidence
            line_confidence_threshold = avg_confidence / 2

        for line in reading_order_block.lines:
            if not any(line.rect.intersects(ignore_rect) for ignore_rect in ignore_rects):
                if detect_vertical:
                    if line.rect.height > line.rect.width and len(line.text) > 2:
                        vertical_detected = True
                    else:
                        if line.confidence > line_confidence_threshold:
                            processed_rects.append(line.rect)
                            draw_lines.append(line)
                        elif line.rect.width > line.rect.height and len(line.text) > 2:
                            # consider a clearly horizontal rect to be processed, even if the confidence is low
                            processed_rects.append(line.rect)
                else:
                    if line.confidence > line_confidence_threshold:
                        draw_lines.append(line)

    return draw_lines, processed_rects, vertical_detected
