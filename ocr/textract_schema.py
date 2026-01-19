"""Rich schema for Textract API responses."""

from dataclasses import dataclass
from math import isnan

from ocr.textract_api_schema import TDocument, TBlock, TBoundingBox, TPoint, TGeometry, TLine, TWord, TPage


@dataclass
class Point:
    x: float
    y: float

@dataclass
class Polygon:
    points: list[Point]

    @property
    def rotation_degrees(self) -> float:
        """
        Returns degrees as float -180.0 < x < 180.0

        In the future, we might want to read this directly from the RotationAngle field of the AWS Textract API response,
        but this new field is not yet implemented in the amazon-textract-textractor Python package.
        """
        import math
        if len(self.points) < 2:
            raise ValueError("Polygon contains less than two points.")
        point_0 = self.points[0]
        point_1 = self.points[1]
        orientation = math.degrees(math.atan2(point_1.y - point_0.y, point_1.x - point_0.x))
        return orientation

    @staticmethod
    def from_api_response(polygon: list[TPoint]) -> "Polygon":
        return Polygon(points=[Point(x=point.x, y=point.y) for point in polygon])

@dataclass
class BoundingBox:
    left: float
    top: float
    width: float
    height: float

    @staticmethod
    def from_api_response(bounding_box: TBoundingBox) -> "BoundingBox":
        return BoundingBox(
            left=bounding_box.left,
            top=bounding_box.top,
            width=bounding_box.width,
            height=bounding_box.height
        )

@dataclass
class Geometry:
    bounding_box: BoundingBox
    polygon: Polygon

    @staticmethod
    def from_api_response(geometry: TGeometry) -> "Geometry":
        return Geometry(
            bounding_box=BoundingBox.from_api_response(geometry.bounding_box),
            polygon=Polygon.from_api_response(geometry.polygon)
        )

@dataclass
class Word:
    text: str
    confidence: float
    geometry: Geometry

    @staticmethod
    def from_api_response(word: TWord) -> "Word":
        return Word(
            text=word.text,
            confidence=word.confidence,
            geometry=Geometry.from_api_response(word.geometry)
        )

@dataclass
class Line:
    text: str
    words: list[Word]
    confidence: float
    geometry: Geometry

    @staticmethod
    def from_api_response(line: TLine, id_to_block: dict[str, TBlock]) -> "Line":
        children = [id_to_block[child_id] for child_id in line.child_ids if child_id in id_to_block]
        return Line(
            text=line.text,
            words=[Word.from_api_response(child) for child in children if isinstance(child, TWord)],
            confidence=line.confidence,
            geometry=Geometry.from_api_response(line.geometry)
        )

@dataclass
class Page:
    lines: list[Line]

    @staticmethod
    def from_api_response(page: TPage, id_to_block: dict[str, TBlock]) -> "Page":
        children = [id_to_block[child_id] for child_id in page.child_ids if child_id in id_to_block]
        return Page(
            lines=[Line.from_api_response(child, id_to_block) for child in children if isinstance(child, TLine)]
        )

@dataclass
class Document:
    pages: list[Page]

    @staticmethod
    def from_api_response(response: TDocument) -> "Document":
        blocks = response.blocks
        id_to_block = {block.id: block for block in blocks}
        return Document(
            pages=[Page.from_api_response(block, id_to_block) for block in blocks if isinstance(block, TPage)]
        )
