from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScalingUpsertRequest(BaseModel):
    size_label: str
    size_position: int


class ScalingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pattern_id: UUID
    size_label: str
    size_position: int
