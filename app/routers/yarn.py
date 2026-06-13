from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.pattern import ErrorResponse
from app.schemas.yarn import UserYarnResponse, UserYarnUpsertRequest
from app.services.scaling.scaling_exceptions import ScalingConfigNotFoundError
from app.services.yarn import (
    InvalidYarnDataError,
    PatternYarnNotFoundError,
    yarn_service,
)

router = APIRouter(prefix="/patterns", tags=["yarns"])

_404 = {404: {"model": ErrorResponse, "description": "Yarn not found for this pattern"}}
_400 = {
    400: {
        "model": ErrorResponse,
        "description": "Invalid yarn data or no scaling config",
    }
}


@router.put(
    "/{pattern_id}/yarns/{pattern_yarn_id}",
    response_model=UserYarnResponse,
    responses={**_404, **_400},
    summary="Upsert user yarn for a pattern yarn",
    description="Saves or updates the user's yarn data for a specific pattern yarn entry.",
)
def upsert_yarn(
    pattern_id: UUID,
    pattern_yarn_id: UUID,
    body: UserYarnUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserYarnResponse:
    try:
        yarn = yarn_service.upsert_yarn(
            db,
            pattern_id=pattern_id,
            pattern_yarn_id=pattern_yarn_id,
            label=body.label,
            yarn_weight=body.yarn_weight,
            meters_per_unit=body.meters_per_unit,
            grams_per_unit=body.grams_per_unit,
            strands=body.strands,
        )
    except ScalingConfigNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PatternYarnNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidYarnDataError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return UserYarnResponse.model_validate(yarn)


@router.get(
    "/{pattern_id}/yarns",
    response_model=list[UserYarnResponse],
    summary="List user yarns for a pattern",
    description="Returns all user yarn entries for the given pattern. Empty list if no scaling config exists.",
)
def list_yarns(
    pattern_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserYarnResponse]:
    yarns = yarn_service.get_by_pattern_id(db, pattern_id)
    return [UserYarnResponse.model_validate(y) for y in yarns]
