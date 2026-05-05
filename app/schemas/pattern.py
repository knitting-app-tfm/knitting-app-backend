from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.pattern import (
    CraftType,
    GaugeUnit,
    PatternSource,
    PatternStatus,
    YarnWeight,
)


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


class PatternResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    title: str
    craft: CraftType
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
    created_at: datetime
    updated_at: datetime | None
    yarns: list[PatternYarnResponse]
