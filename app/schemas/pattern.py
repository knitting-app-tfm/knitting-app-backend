from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.pattern import (
    CraftType,
    GaugeUnit,
    PatternSource,
    PatternStatus,
    YarnWeight,
)


class ErrorResponse(BaseModel):
    detail: str


class PatternYarnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pattern_id: UUID
    label: str | None
    yarn_weight: YarnWeight | None
    meters_per_unit: float | None
    grams_per_unit: float | None
    grams_needed: list[float] | None
    strands: int


class PatternYarnRequest(BaseModel):
    label: str | None = None
    yarn_weight: YarnWeight | None = None
    meters_per_unit: float | None = None
    grams_per_unit: float | None = None
    grams_needed: list[float] | None = None
    strands: int = 1


class PatternYarnPrefillItem(BaseModel):
    """Yarn entry for the prefill response: id/pattern_id are absent for IMPORTED patterns."""

    id: UUID | None = None
    pattern_id: UUID | None = None
    label: str | None = None
    yarn_weight: YarnWeight | None = None
    meters_per_unit: float | None = None
    grams_per_unit: float | None = None
    grams_needed: list[float] | None = None
    strands: int = 1


class PatternResponse(BaseModel):
    """Response after import or confirm — contains only what is stored in the DB."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    title: str | None
    craft: CraftType | None
    status: PatternStatus
    source: PatternSource
    cover_image_path: str | None
    original_file_path: str
    parsed_json_path: str | None
    gauge_stitches: float | None
    gauge_rows: float | None
    gauge_size: float | None
    gauge_unit: GaugeUnit | None
    needle_size: str | None
    sizes: list[str]
    created_at: datetime
    updated_at: datetime | None
    yarns: list[PatternYarnResponse]

    @field_validator("sizes", mode="before")
    @classmethod
    def normalize_sizes(cls, v: list[str] | None) -> list[str]:
        return v if v is not None else []


class PatternDetailResponse(BaseModel):
    """Full prefill response for the confirmation form.

    For IMPORTED patterns, editable fields come from parsed_json on disk.
    For CONFIRMED patterns, they come from the DB.
    """

    id: UUID
    user_id: UUID | None
    status: PatternStatus
    source: PatternSource
    original_file_path: str
    parsed_json_path: str | None
    cover_image_path: str | None
    created_at: datetime
    updated_at: datetime | None
    title: str | None = None
    craft: CraftType | None = None
    gauge_stitches: float | None = None
    gauge_rows: float | None = None
    gauge_size: float | None = None
    gauge_unit: GaugeUnit | None = None
    needle_size: str | None = None
    sizes: list[str] = []
    yarns: list[PatternYarnPrefillItem] = []


# ---------------------------------------------------------------------------
# Token schemas — used by POST /patterns/{id}/translate
# ---------------------------------------------------------------------------


class TextSegment(BaseModel):
    """One line of source text with its formatting metadata, as extracted from the file."""

    text: str
    bold: bool
    italic: bool
    font_size: float | None


class TextToken(BaseModel):
    type: Literal["text"]
    value: str


class SizeGroupToken(BaseModel):
    type: Literal["size_group"]
    values: list[int | float]
    unit: str | None
    scalable: bool


class AbbreviationToken(BaseModel):
    type: Literal["abbreviation"]
    code: str
    translated: bool
    full_name: str | None
    quantity: int | None = None


class NumberToken(BaseModel):
    type: Literal["number"]
    value: float
    unit: str | None
    scalable: bool


Token = Annotated[
    TextToken | SizeGroupToken | AbbreviationToken | NumberToken,
    Field(discriminator="type"),
]


class LineTokens(BaseModel):
    """One line from the pattern, with its tokens. Empty lines have tokens=[]."""

    line: int
    bold: bool
    italic: bool
    font_size: float | None
    tokens: list[Token]
