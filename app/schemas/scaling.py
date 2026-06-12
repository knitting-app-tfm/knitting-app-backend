from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pattern import AbbreviationToken, TextToken


class ScalingUpsertRequest(BaseModel):
    size_label: str
    size_position: int
    gauge_stitches: float
    gauge_rows: float | None = None
    gauge_size: float
    gauge_unit: str
    needle_size: str | None = None


class ScalingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pattern_id: UUID
    size_label: str
    size_position: int
    gauge_stitches: float
    gauge_rows: float | None
    gauge_size: float
    gauge_unit: str
    needle_size: str | None


# ---------------------------------------------------------------------------
# Scaled pattern response — used by GET /patterns/{id}/scaled
# ---------------------------------------------------------------------------


class ScaledNumberToken(BaseModel):
    type: Literal["number"]
    value: int | float
    unit: str | None
    scalable: bool
    scaled: bool
    rows_warning: bool = False


ScaledToken = Annotated[
    TextToken | AbbreviationToken | ScaledNumberToken,
    Field(discriminator="type"),
]


class ScaledLineTokens(BaseModel):
    line: int
    bold: bool
    italic: bool
    font_size: float | None
    tokens: list[ScaledToken]


class ScaledPatternResponse(BaseModel):
    rows_warning: bool
    size_label: str
    lines: list[ScaledLineTokens]
