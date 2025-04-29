import pymupdf
from trp import Line

class TextWord:
    def __init__(self, text: str, derotated_rect: pymupdf.Rect, orientation: float):
        self.text = text
        self.derotated_rect = derotated_rect
        self.orientation = orientation

    @staticmethod
    def from_textract(word, derotator):
        derotated_rect, orientation = derotator.derotate(word.geometry)
        return TextWord(word.text, derotated_rect, orientation)


class TextLine:
    def __init__(self, derotated_rect: pymupdf.Rect, orientation: float, rect: pymupdf.Rect, text: str, confidence: float, words: list[TextWord]):
        self.text = text
        self.orientation = orientation
        self.derotated_rect = derotated_rect
        self.rect = rect
        self.confidence = confidence
        self.words = words

    @staticmethod
    def from_textract(line: Line, orientation: float, page_height: float, transform: pymupdf.Matrix):
        """

        :param line:
        :param orientation:
        :param page_height:
        :param transform: Matrix, based on rotation and clip rect, that transforms the Textract coordinates to the
                          PyMuPDF coordinates of the original page.
        """
        derotator = GeometryDerotator(orientation, transform, page_height)
        derotated_rect, orientation = derotator.derotate(line.geometry)

        bbox = line.geometry.boundingBox
        textract_rect = pymupdf.Rect(bbox.left, bbox.top, bbox.left + bbox.width,
                                  bbox.top + bbox.height)
        rect = textract_rect * transform

        confidence: float = line.confidence / 100
        text = line.text

        words = [TextWord.from_textract(word, derotator) for word in line.words]

        return TextLine(derotated_rect, orientation, rect, text, confidence, words)


class GeometryDerotator:
    def __init__(self, orientation: float, transform: pymupdf.Matrix, page_height: float):
        self.orientation = orientation
        self.transform = transform
        self.page_height = page_height

    def derotate(self, geometry) -> (pymupdf.Rect, float):
        polygon = geometry.polygon
        orientation = self.orientation

        top_left = pymupdf.Point(polygon[0].x, polygon[0].y) * self.transform
        top_right = pymupdf.Point(polygon[1].x, polygon[1].y) * self.transform
        bottom_left = pymupdf.Point(polygon[-1].x, polygon[-1].y) * self.transform
        bottom_right = pymupdf.Point(polygon[-2].x, polygon[-2].y) * self.transform
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
