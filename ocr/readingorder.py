from dataclasses import dataclass

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

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines)


class TextLineReadingOrder:
    def __init__(self, line: TextLine):
        self.line = line
        self.geometry = ReadingOrderGeometry(line.rect)


class ReadingOrderGeometry:
    def __init__(self, rect: pymupdf.Rect):
        self.rect = rect

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
        """Sort bounding boxes from top to bottom and from left to right; top-to-bottom having a stronger influence."""
        return self.rect.x0 + 2 * self.rect.y0

    def needs_to_come_before(self, other: "ReadingOrderGeometry") -> bool:
        return (self.x_middle < other.x_middle and self.y_middle <= other.y_middle) or (
            self.x_middle <= other.x_middle and self.y_middle < other.y_middle
        ) or (
            self.x_middle < other.rect.x0 and (self.y_middle < other.rect.y1 or self.rect.y0 < other.y_middle)
        ) or (
            self.y_middle < other.rect.y0 and (self.x_middle < other.rect.x1 or self.rect.x0 < other.x_middle)
        )

    def distance_after(self, other: "ReadingOrderGeometry") -> float:
        left = self.rect.top_left.distance_to(other.rect.bottom_left)
        middle = self.top_middle.distance_to(other.bottom_middle)
        right = self.rect.top_right.distance_to(other.rect.bottom_right)
        return min(left, middle, right)


@dataclass
class ReadingOrderColumn:
    rect: pymupdf.Rect
    bottom_of_first_line: float
    top_of_last_line: float

    def add_line_before(self, line: TextLine) -> "ReadingOrderColumn":
        return ReadingOrderColumn(
            rect=pymupdf.Rect(self.rect).include_rect(line.rect),
            bottom_of_first_line=line.rect.y1,
            top_of_last_line=self.top_of_last_line
        )

    def is_interrupted_by(self, rect: pymupdf.Rect) -> bool:
        y_middle = (rect.y0 + rect.y1) / 2
        return rect.intersects(self.rect) and self.bottom_of_first_line < y_middle < self.top_of_last_line

    def can_be_extended_by(self, geometry: ReadingOrderGeometry) -> bool:
        column_width = self.rect.width
        min_x = self.rect.x0 - 10 - 0.1 * column_width
        max_x = self.rect.x1 + 10 + 0.1 * column_width
        return (
            geometry.y_middle > self.top_of_last_line and  # below
            geometry.rect.y0 - self.rect.y1 < self.rect.height and  # not too far below
            geometry.rect.x0 > min_x and
            geometry.rect.x1 < max_x and
            x_overlap(self.rect, geometry.rect) > 0.8 * geometry.rect.width
        )

    def is_accurately_extended_by(self, geometry: ReadingOrderGeometry) -> bool:
        return self.can_be_extended_by(geometry) and x_overlap(self.rect, geometry.rect) > 0.8 * self.rect.width and (
            self.rect.y1 < geometry.rect.y1  #strictly below
        )

    @classmethod
    def current_column(
            cls,
            current_line: TextLineReadingOrder,
            preceding_lines: list[TextLineReadingOrder],
            all_lines: set[TextLineReadingOrder]
    ) -> "ReadingOrderColumn":
        other_lines = all_lines.copy()
        other_lines.remove(current_line)
        column = ReadingOrderColumn(
            rect=current_line.geometry.rect,
            bottom_of_first_line=current_line.geometry.rect.y1,
            top_of_last_line=current_line.geometry.rect.y0
        )
        accurate_extension_count = sum(
            1 for line in other_lines if column.is_accurately_extended_by(line.geometry)
        )
        for line in preceding_lines[::-1]:
            print("- ", line.line.text)
            new_column = column.add_line_before(line.line)
            other_lines.remove(line)
            new_accurate_extension_count = sum(
                1 for line in other_lines if column.is_accurately_extended_by(line.geometry)
            )
            if any(new_column.is_interrupted_by(other_line.geometry.rect) for other_line in other_lines):
                print("interr")
                break
            if new_accurate_extension_count < accurate_extension_count:
                print("acc")
                break
            else:
                column = new_column

        return column


def starting_line_for_next_block(remaining_lines: set[TextLineReadingOrder]) -> None | TextLineReadingOrder:
    candidate_lines = remaining_lines.copy()
    selected_line = None
    while candidate_lines:
        selected_line = min(candidate_lines, key=lambda line: line.geometry.sort_key)
        candidate_lines.remove(selected_line)
        candidate_lines = {
            line for line in candidate_lines if line.geometry.needs_to_come_before(selected_line.geometry)
        }
    return selected_line


def sort_lines(text_lines: list[TextLine]) -> list[ReadingOrderBlock]:
    all_lines = {TextLineReadingOrder(line) for line in text_lines}
    remaining_lines = all_lines.copy()
    blocks = []

    while remaining_lines:
        current_line = starting_line_for_next_block(remaining_lines)
        remaining_lines.remove(current_line)
        current_block = [current_line]

        while remaining_lines:
            next_line = None

            print()
            print(current_line.line.text)
            # add text lines that seem to continue the current column, even if they are further down (but not futher
            # down than the current height of the column)
            column = ReadingOrderColumn.current_column(current_line, current_block[:-1], all_lines)
            in_column_lines = {line for line in remaining_lines if column.can_be_extended_by(line.geometry)}
            if len(in_column_lines):
                print([l.line.text for l in in_column_lines])
                highest_following = min(in_column_lines, key=lambda line: line.geometry.rect.y0)
                candidates = {
                    line for line in in_column_lines
                    if line.geometry.needs_to_come_before(highest_following.geometry)
                }
                candidates.add(highest_following)
                next_line = min(candidates, key=lambda line: line.geometry.rect.x0)

            if not next_line:
                # lines that are directly below the last line, either left-aligned, right-aligned or centered
                following = {line for line in remaining_lines if line.geometry.distance_after(current_line.geometry) < 20}
                if len(following):
                    next_line = min(following, key=lambda line: line.geometry.rect.y0)

            if not next_line:
                break

            current_line = next_line
            remaining_lines.remove(current_line)

            print("check", current_line.line.rect)
            if any(line.geometry.needs_to_come_before(current_line.geometry) for line in remaining_lines):
                print("break!", [line.line.rect for line in remaining_lines if line.geometry.needs_to_come_before(current_line.geometry)])
                remaining_lines.add(current_line)
                break

            current_block.append(current_line)

        blocks.append(ReadingOrderBlock([line.line for line in current_block]))
    return blocks

