from dataclasses import dataclass

import pymupdf
from ocr.textract_schema import Line, Polygon


@dataclass
class TextWord:
    text: str
    derotated_rect: pymupdf.Rect
    orientation: float

    @staticmethod
    def from_textract(word, derotator):
        derotated_rect, orientation = derotator.derotate(word.geometry.polygon)
        return TextWord(word.text, derotated_rect, orientation)


@dataclass
class TextLine:
    text: str
    orientation: float
    derotated_rect: pymupdf.Rect
    rect: pymupdf.Rect
    confidence: float
    words: list[TextWord]

    @staticmethod
    def from_textract(line: Line, page_height: float, transform: pymupdf.Matrix):
        """

        :param line:
        :param page_height:
        :param transform: Matrix, based on rotation and clip rect, that transforms the Textract coordinates to the
                          PyMuPDF coordinates of the original page.
        """
        if not line.words:
            return []

        # assume rotation of first word applies to all words in the line
        first_word = line.words[0]
        rotate = round(first_word.geometry.polygon.rotation_degrees)

        derotator = GeometryDerotator(rotate, transform, page_height)
        derotated_rect, orientation = derotator.derotate(line.geometry.polygon)

        bbox = line.geometry.bounding_box
        textract_rect = pymupdf.Rect(bbox.left, bbox.top, bbox.left + bbox.width,
                                  bbox.top + bbox.height)
        rect = textract_rect * transform

        confidence: float = line.confidence / 100
        text = line.text

        words = [TextWord.from_textract(word, derotator) for word in line.words]

        return TextLine(text, orientation, derotated_rect, rect, confidence, words)


class GeometryDerotator:
    def __init__(self, orientation: float, transform: pymupdf.Matrix, page_height: float):
        self.orientation = orientation
        self.transform = transform
        self.page_height = page_height

    def derotate(self, polygon: Polygon) -> (pymupdf.Rect, float):
        points = polygon.points
        orientation = self.orientation

        top_left = pymupdf.Point(points[0].x, points[0].y) * self.transform
        top_right = pymupdf.Point(points[1].x, points[1].y) * self.transform
        bottom_left = pymupdf.Point(points[-1].x, points[-1].y) * self.transform
        bottom_right = pymupdf.Point(points[-2].x, points[-2].y) * self.transform
        quad = pymupdf.Quad(top_left, top_right, bottom_left, bottom_right)

        closest_multiple_of_90_deg = round(orientation / 90) * 90
        diff_to_multiple_of_90_deg = orientation - closest_multiple_of_90_deg

        if abs(diff_to_multiple_of_90_deg) < 25:
            # For small detected angles, just print text perfectly horizontally/vertically, because the detected angle
            # might be an error. Cf LGD-272, examples: title page of asset 38802 or 38808.
            orientation = closest_multiple_of_90_deg

        # rotate around the bottom-left corner of the page
        derotated_rect = quad.morph(
            pymupdf.Point(0, self.page_height),
            pymupdf.Matrix(1, 1).prerotate(-orientation)
        ).rect

        if abs(diff_to_multiple_of_90_deg) < 25:
            middle_y = (derotated_rect.top_left.y + derotated_rect.bottom_right.y) / 2
            left_x = (derotated_rect.top_left.x + derotated_rect.bottom_left.x) / 2
            right_x = (derotated_rect.top_right.x + derotated_rect.bottom_right.x) / 2
            line_height = top_left.distance_to(bottom_left)
            # use a "straightened" version of the rect that was derotated with a multiple of 90 degrees
            derotated_rect = pymupdf.Rect(left_x, middle_y - line_height / 2, right_x, middle_y + line_height / 2)

        return derotated_rect, orientation
