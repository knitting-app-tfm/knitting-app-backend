from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserYarnUpsertRequest(BaseModel):
    label: str | None = None
    yarn_weight: str | None = None
    meters_per_unit: float
    grams_per_unit: float
    strands: int = 1


class UserYarnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pattern_yarn_id: UUID
    label: str | None
    yarn_weight: str | None
    meters_per_unit: float
    grams_per_unit: float
    strands: int
