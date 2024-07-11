import fitz
from trp import Line


class TextWord:
    def __init__(self, text: str, derotated_rect: fitz.Rect, orientation: float):
        self.text = text
        self.derotated_rect = derotated_rect
        self.orientation = orientation


class TextLine:
    def __init__(self, line: Line, orientation: float, page_height: float, transform: fitz.Matrix):
        """

        :param line:
        :param orientation:
        :param page_height:
        :param transform: Matrix, based on rotation and clip rect, that transforms the Textract coordinates to the
                          PyMuPDF coordinates of the original page.
        """
        self.line = line
        self.text = line.text
        self.confidence: float = line.confidence / 100
        self.transform = transform
        self.page_height = page_height
        self.orientation = orientation

        self.derotated_rect, self.orientation = self._derotate_geometry(line.geometry)

        bbox = line.geometry.boundingBox
        textract_rect = fitz.Rect(bbox.left, bbox.top, bbox.left + bbox.width,
                                  bbox.top + bbox.height)
        self.rect = textract_rect * transform

    def _derotate_geometry(self, geometry) -> (fitz.Rect, float):
        polygon = geometry.polygon
        orientation = self.orientation

        top_left = fitz.Point(polygon[0].x, polygon[0].y) * self.transform
        top_right = fitz.Point(polygon[1].x, polygon[1].y) * self.transform
        bottom_left = fitz.Point(polygon[-1].x, polygon[-1].y) * self.transform
        bottom_right = fitz.Point(polygon[-2].x, polygon[-2].y) * self.transform
        quad = fitz.Quad(top_left, top_right, bottom_left, bottom_right)

        closest_multiple_of_90_deg = round(orientation / 90) * 90
        diff_to_multiple_of_90_deg = orientation - closest_multiple_of_90_deg

        if abs(diff_to_multiple_of_90_deg) < 25:
            # For small detected angles, just print text perfectly horizontally/vertically, because the detected angle
            # might be an error. Cf LGD-272, examples: title page of asset 38802 or 38808.
            orientation = closest_multiple_of_90_deg

        # rotate around the bottom-left corner of the page
        derotated_rect = quad.morph(
            fitz.Point(0, self.page_height),
            fitz.Matrix(1, 1).prerotate(-orientation)
        ).rect

        if abs(diff_to_multiple_of_90_deg) < 25:
            middle_y = (derotated_rect.top_left.y + derotated_rect.bottom_right.y) / 2
            left_x = (derotated_rect.top_left.x + derotated_rect.bottom_left.x) / 2
            right_x = (derotated_rect.top_right.x + derotated_rect.bottom_right.x) / 2
            line_height = top_left.distance_to(bottom_left)
            # use a "straightened" version of the rect that was derotated with a multiple of 90 degrees
            derotated_rect = fitz.Rect(left_x, middle_y - line_height / 2, right_x, middle_y + line_height / 2)

        return derotated_rect, orientation


    def _create_word(self, word):
        derotated_rect, orientation = self._derotate_geometry(word.geometry)
        return TextWord(word.text, derotated_rect, orientation)

    def words(self):
        return [self._create_word(word) for word in self.line.words]


class ReadingOrderBlock:
    def __init__(self, lines: list[TextLine]):
        self.lines = lines
        self.top = min([line.rect.y0 for line in lines])
        self.left = min([line.rect.x0 for line in lines])
        self.bottom = max([line.rect.y1 for line in lines])
        self.right = max([line.rect.x1 for line in lines])
        self.rect = fitz.Rect(self.left, self.top, self.right, self.bottom)
        self.sort_key = self.top + self.left


def overlaps(line, line2) -> bool:
    vertical_margin = 15
    ref_rect = fitz.Rect(line.rect.x0, line.rect.y0 - vertical_margin, line.rect.x1, line.rect.y1 + vertical_margin)
    return ref_rect.intersects(line2.rect)


def adjacent_lines(lines: list[TextLine]) -> list[set[int]]:
    result = [set() for _ in lines]
    for index, line in enumerate(lines):
        for index2, line2 in enumerate(lines):
            if index2 > index:
                if overlaps(line, line2):
                    result[index].add(index2)
                    result[index2].add(index)
    return result


def apply_transitive_closure(data: list[set[int]]) -> bool:
    found_new_relation = False
    for index, adjacent_indices in enumerate(data):
        new_adjacent_indices = set()
        for adjacent_index in adjacent_indices:
            new_adjacent_indices.update(
                new_index
                for new_index in data[adjacent_index]
                if new_index not in data[index]
            )

        for new_adjacent_index in new_adjacent_indices:
            data[index].add(new_adjacent_index)
            data[new_adjacent_index].add(index)
            found_new_relation = True
    return found_new_relation


def select_blocks_from_position(
        last_block: ReadingOrderBlock | None,
        remaining_blocks: set[ReadingOrderBlock]
) -> (list[ReadingOrderBlock], set[ReadingOrderBlock]):
    if last_block is None:
        next_block = min(remaining_blocks, key=lambda block: block.sort_key)
    else:
        below_blocks = {block for block in remaining_blocks if block.top > last_block.bottom}
        if len(below_blocks) == 0:
            return [], remaining_blocks
        else:
            next_block = min(below_blocks, key=lambda block: block.rect.top_left.distance_to(last_block.rect.bottom_left))

    remaining_blocks.remove(next_block)
    blocks_above_next_block = {
        block
        for block in remaining_blocks
        if block.bottom < next_block.top and block.left < next_block.right
    }
    selected_blocks = select_blocks(blocks_above_next_block)
    remaining_blocks.difference_update(selected_blocks)
    selected_blocks.append(next_block)
    return selected_blocks, remaining_blocks


def select_blocks(blocks: set[ReadingOrderBlock]) -> list[ReadingOrderBlock]:
    remaining_blocks = blocks.copy()
    sorted_blocks = []

    while len(remaining_blocks) > 0:
        # Select a first block, then try to read from top to bottom, but always ensure that any text that is above a
        # newly selected block, comes first.
        new_selected_blocks, remaining_blocks = select_blocks_from_position(None, remaining_blocks)

        while len(new_selected_blocks) > 0:
            last_selected_block = new_selected_blocks[-1]
            sorted_blocks.extend(new_selected_blocks)

            new_selected_blocks, remaining_blocks = select_blocks_from_position(last_selected_block, remaining_blocks)

    return sorted_blocks


def sort_lines(text_lines: list[TextLine]) -> list[ReadingOrderBlock]:
    data = adjacent_lines(text_lines)

    while apply_transitive_closure(data):
        # apply transitive closure until the method returns false (nothing changes anymore; closure reached)
        pass

    blocks: list[ReadingOrderBlock] = []
    remaining_indices = {index for index, _ in enumerate(data)}
    for index, adjacent_indices in enumerate(data):
        if index in remaining_indices:
            selected_indices = adjacent_indices
            selected_indices.add(index)
            blocks.append(ReadingOrderBlock(
                [text_lines[selected_index] for selected_index in sorted(list(selected_indices))]
            ))
            remaining_indices.difference_update(selected_indices)

    blocks.sort(key=lambda block: block.sort_key)

    sorted_blocks = select_blocks(set(blocks))
    return sorted_blocks
