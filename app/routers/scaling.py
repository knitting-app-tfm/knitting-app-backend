from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.pattern import ErrorResponse
from app.schemas.scaling import ScalingResponse, ScalingUpsertRequest
from app.services.scaling import (
    InvalidGaugeError,
    InvalidSizeLabelError,
    InvalidSizePositionError,
    PatternNotFoundError,
    scaling_service,
)

router = APIRouter(prefix="/patterns", tags=["scaling"])

_404 = {404: {"model": ErrorResponse, "description": "Pattern not found"}}
_400 = {
    400: {
        "model": ErrorResponse,
        "description": "Invalid size label, position, or gauge",
    }
}


@router.put(
    "/{pattern_id}/scaling",
    response_model=ScalingResponse,
    responses={**_404, **_400},
    summary="Upsert size selection for a pattern",
    description="Sets or updates the selected size and gauge for a pattern.",
)
def upsert_scaling(
    pattern_id: UUID,
    body: ScalingUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScalingResponse:
    try:
        scaling = scaling_service.upsert_size(
            db,
            pattern_id,
            body.size_label,
            body.size_position,
            body.gauge_stitches,
            body.gauge_rows,
            body.gauge_size,
            body.gauge_unit,
            body.needle_size,
        )
    except PatternNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvalidSizeLabelError, InvalidSizePositionError, InvalidGaugeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ScalingResponse.model_validate(scaling)


@router.get(
    "/{pattern_id}/scaling",
    response_model=ScalingResponse | None,
    responses=_404,
    summary="Get current size selection for a pattern",
    description="Returns the currently selected size for a pattern, or null if none has been set.",
)
def get_scaling(
    pattern_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScalingResponse | None:
    scaling = scaling_service.get_by_pattern_id(db, pattern_id)
    if scaling is None:
        return None
    return ScalingResponse.model_validate(scaling)
