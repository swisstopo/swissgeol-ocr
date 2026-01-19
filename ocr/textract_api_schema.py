"""Pydantic schema definitions for responses from the AWS Textract API.

Only field that are relevant for the current project are defined, everything else is ignored."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_pascal


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_pascal)


class TBoundingBox(Model):
    width: float
    height: float
    left: float
    top: float

class TPoint(Model):
    x: float
    y: float

class TGeometry(Model):
    bounding_box: TBoundingBox
    polygon: list[TPoint]


class TRelationship(Model):
    type: str
    ids: list[str]

class TBlock(Model):
    block_type: str
    geometry: TGeometry
    id: str
    relationships: list[TRelationship] | None = None
    confidence: float | None = None
    text: str | None = None

    @property
    def child_ids(self) -> list[str]:
        if not self.relationships:
            return []
        return [
            id
            for relationship_group in self.relationships
            if relationship_group.type == 'CHILD'
            for id in relationship_group.ids
        ]

class TDocument(Model):
    blocks: list[TBlock]
