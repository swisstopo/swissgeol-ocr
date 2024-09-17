import fitz
from util.readingorder import sort_lines, TextLine
from util.textract import combine_text_lines, textract, clip_rects, MAX_DIMENSION_POINTS
from textractor import Textractor
from uuid import uuid4


class OCR:
    def __init__(
            self,
            textractor: Textractor,
            confidence_threshold: float,
            page: fitz.Page,
            doc_copy: fitz.Document,
            ignore_rects: list[fitz.Rect],
            tmp_path_prefix: str
    ):
        self.textractor = textractor
        self.confidence_threshold = confidence_threshold
        self.page = page
        self.doc_copy = doc_copy
        self.page_copy = doc_copy[0]
        self.ignore_rects = ignore_rects
        self.tmp_path_prefix = tmp_path_prefix

    def tmp_file_path(self, extension: str) -> str:
        return "{}_{}.{}".format(self.tmp_path_prefix, uuid4(), extension)

    def apply_ocr(self, clip_rect: fitz.Rect):
        """Apply OCR with double page workaround and vertical check"""
        text_lines = self._ocr_text_lines(clip_rect, rotate=0)

        if ((self.page.rect.height < MAX_DIMENSION_POINTS and self.page.rect.width < MAX_DIMENSION_POINTS) and (
                len(text_lines) > 30
        ) and all(
                not self._intersects_middle(line.rect, line.confidence) for line in text_lines
        )):
            print("  Double page workaround")
            page_rect = self.page.rect

            left_clip_rect = (page_rect * fitz.Matrix(0.5, 1))
            left_text_lines = self._ocr_text_lines(left_clip_rect, rotate=0)
            lines_to_draw = self.apply_vertical_check(left_text_lines, left_clip_rect)

            right_clip_rect = (page_rect * fitz.Matrix(0.5, 1).pretranslate(page_rect.width, 0))
            right_text_lines = self._ocr_text_lines(right_clip_rect, rotate=0)
            lines_to_draw.extend(self.apply_vertical_check(right_text_lines, right_clip_rect))

            return lines_to_draw
        else:
            return self.apply_vertical_check(text_lines, clip_rect)

    def apply_vertical_check(self, text_lines: list[TextLine], clip_rect: fitz.Rect):
        lines_to_draw, processed_rects, vertical_detected = (
            get_ocr_lines(text_lines, self.ignore_rects, self.confidence_threshold, detect_vertical=True)
        )

        if vertical_detected:
            print("  Potential vertical text detected. Running OCR again with horizontal text masked.")
            for rect in processed_rects:
                self.page_copy.draw_rect(
                    rect * self.page.derotation_matrix,
                    width=0,
                    fill=fitz.utils.getColor("white")
                )
            vertical_text_lines = self._ocr_text_lines(clip_rect, rotate=90)
            vertical_draw_lines, _, _ = (
                get_ocr_lines(vertical_text_lines, self.ignore_rects, self.confidence_threshold, detect_vertical=False)
            )
            lines_to_draw.extend(vertical_draw_lines)
        return lines_to_draw

    def _ocr_text_lines(self, clip_rect: fitz.Rect, rotate: float) -> list[TextLine]:
        text_lines = []
        final_clip_rects = clip_rects(clip_rect)
        for final_clip_rect in final_clip_rects:
            new_lines = textract(self.doc_copy, self.textractor, self.tmp_file_path("pdf"), final_clip_rect, rotate)
            text_lines = combine_text_lines(text_lines, new_lines)
        return text_lines

    def _intersects_middle(self, line_rect: fitz.Rect, confidence: float) -> bool:
        page_middle = (self.page.rect.x0 + self.page.rect.x1) / 2
        return confidence > self.confidence_threshold and not(line_rect.x0 > page_middle or line_rect.x1 < page_middle)


def get_ocr_lines(
        text_lines: list[TextLine],
        ignore_rects: list[fitz.Rect],
        confidence_threshold: float,
        detect_vertical: bool = True
) -> (list[TextLine], list[fitz.Rect], bool):
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
