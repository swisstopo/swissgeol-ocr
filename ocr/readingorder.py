
import pymupdf

from ocr.textline import TextLine
from ocr.util import x_overlap

class ReadingOrderBlock:
    def __init__(self, lines: list[TextLine]):
        self.lines = lines
        self.top = min([line.rect.y0 for line in lines])
        self.left = min([line.rect.x0 for line in lines])
        self.bottom = max([line.rect.y1 for line in lines])
        self.right = max([line.rect.x1 for line in lines])
        self.rect = pymupdf.Rect(self.left, self.top, self.right, self.bottom)
        self.sort_key = min([line.rect.x0 + line.rect.y0 for line in lines])

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines)


class TextLineReadingOrder:
    def __init__(self, line: TextLine):
        self.line = line

    @property
    def rect(self) -> pymupdf.Rect:
        return self.line.rect

    @property
    def x_middle(self) -> float:
        return (self.rect.x0 + self.rect.x1) / 2

    @property
    def y_middle(self) -> float:
        return (self.rect.y0 + self.rect.y1) / 2

    @property
    def top_middle(self):
        return pymupdf.Point(self.x_middle, self.rect.y0)

    @property
    def bottom_middle(self):
        return pymupdf.Point(self.x_middle, self.rect.y1)

    @property
    def sort_key(self):
        return self.rect.x0 + self.rect.y0

    def needs_to_come_before(self, other: "TextLineReadingOrder") -> bool:
        return self.rect.x0 < other.x_middle and self.rect.y0 < other.y_middle

    def distance_after(self, other: "TextLineReadingOrder") -> float:
        left = self.rect.top_left.distance_to(other.rect.bottom_left)
        middle = self.top_middle.distance_to(other.bottom_middle)
        right = self.rect.top_right.distance_to(other.rect.bottom_right)
        return min(left, middle, right)


def current_column(current_lines: list[TextLineReadingOrder], all_lines: list[TextLine]) -> pymupdf.Rect:
    other_lines = set(all_lines)
    column_rect = pymupdf.Rect()
    for reading_order_line in current_lines[::-1]:
        new_rect = column_rect.include_rect(reading_order_line.rect)
        other_lines.remove(reading_order_line.line)
        if any(other_line.rect.intersects(column_rect) for other_line in other_lines):
            break
        else:
            column_rect = new_rect

    return column_rect


def sort_lines(text_lines: list[TextLine]) -> list[ReadingOrderBlock]:
    remaining_lines = set([TextLineReadingOrder(line) for line in text_lines])
    blocks = []

    while remaining_lines:
        current_line = min(remaining_lines, key=lambda line: line.sort_key)
        remaining_lines.remove(current_line)

        must_come_before = {line for line in remaining_lines if line.needs_to_come_before(current_line)}
        if must_come_before:
            remaining_lines.add(current_line)
            current_line = min(must_come_before, key=lambda line: line.sort_key)
            remaining_lines.remove(current_line)

        current_block = [current_line.line]

        while remaining_lines:
            # TODO: deal with lines that are split into several TextLine objects, e.g. 33120.pdf p.9

            # lines that are directly below the last line, either left-aligned, right-aligned or centered
            following = {line for line in remaining_lines if line.distance_after(current_line) < 20}

            # add text lines that seem to continue the current column, even if they are further down (but not futher
            # down than the current height of the column)
            column_rect = current_column(current_block, text_lines)
            if not column_rect.is_empty:
                column_width = column_rect.width
                min_x = column_rect.x0 - 10 - 0.05 * column_width
                max_x = column_rect.x1 + 10 + 0.05 * column_width
                in_column_lines = {
                    line
                    for line in remaining_lines
                    if (line.rect.y0 + line.rect.y1) / 2 > column_rect.y1 and  # below
                        line.rect.y0 - column_rect.y1 < column_rect.height and  # not too far below
                        line.rect.x0 > min_x and
                        line.rect.x1 < max_x and
                        x_overlap(column_rect, line.rect) > 0.8 * line.rect.width
                }
                if len(in_column_lines):
                    following.add(min(in_column_lines, key=lambda line: line.rect.y0))

            if not following:
                break

            current_line = min(following, key=lambda line: line.sort_key)
            remaining_lines.remove(current_line)
            if any(line.needs_to_come_before(current_line) for line in remaining_lines):
                remaining_lines.add(current_line)
                break

            current_block.append(current_line.line)

        blocks.append(ReadingOrderBlock(current_block))
    return blocks

