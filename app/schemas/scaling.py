from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
