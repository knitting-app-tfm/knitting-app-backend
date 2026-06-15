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


# ---------------------------------------------------------------------------
# Yarn calculation response — used by GET /patterns/{id}/yarn-calculation
# ---------------------------------------------------------------------------


class PatternYarnSummary(BaseModel):
    label: str | None
    yarn_weight: str | None
    meters_per_unit: float | None
    grams_per_unit: float | None
    strands: int
    grams_needed: float | None


class UserYarnSummary(BaseModel):
    label: str | None
    yarn_weight: str | None
    meters_per_unit: float
    grams_per_unit: float
    strands: int


class YarnCalculationResult(BaseModel):
    grams_needed: float
    skeins_needed: int


class YarnCalculationEntry(BaseModel):
    pattern_yarn_id: UUID
    calculated: bool
    weight_warning: bool = False
    pattern_yarn: PatternYarnSummary
    user_yarn: UserYarnSummary | None = None
    result: YarnCalculationResult | None = None
    message: str | None = None


class YarnCalculationResponse(BaseModel):
    size_label: str
    yarns: list[YarnCalculationEntry]
