from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

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
    grams_needed: float | None
    strands: int


class PatternYarnRequest(BaseModel):
    label: str | None = None
    yarn_weight: YarnWeight | None = None
    meters_per_unit: float | None = None
    grams_per_unit: float | None = None
    grams_needed: float | None = None
    strands: int = 1


class PatternYarnPrefillItem(BaseModel):
    """Yarn entry for the prefill response: id/pattern_id are absent for IMPORTED patterns."""

    id: UUID | None = None
    pattern_id: UUID | None = None
    label: str | None = None
    yarn_weight: YarnWeight | None = None
    meters_per_unit: float | None = None
    grams_per_unit: float | None = None
    grams_needed: float | None = None
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
    ravelry_pattern_id: str | None
    original_file_path: str
    parsed_json_path: str | None
    tokens_file_path: str | None
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
    tokens_file_path: str | None
    cover_image_path: str | None
    ravelry_pattern_id: str | None
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
