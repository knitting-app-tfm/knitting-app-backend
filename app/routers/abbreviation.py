from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.abbreviation import AbbreviationCraft, AbbreviationType
from app.schemas.abbreviation import AbbreviationListResponse, AbbreviationResponse
from app.schemas.pattern import ErrorResponse
from app.services.abbreviation import abbreviation_service

router = APIRouter(prefix="/abbreviations", tags=["abbreviations"])

_404 = {404: {"model": ErrorResponse, "description": "Abbreviation not found"}}


@router.get(
    "",
    response_model=AbbreviationListResponse,
    summary="List abbreviations",
    description=(
        "Returns all knitting and crochet abbreviations in the dictionary. "
        "Optionally filter by `craft` (KNITTING or CROCHET) and/or `type` "
        "(STITCH, DECREASE, INCREASE, etc.)."
    ),
)
def list_abbreviations(
    craft: AbbreviationCraft | None = None,
    type: AbbreviationType | None = None,
    db: Session = Depends(get_db),
) -> AbbreviationListResponse:
    abbreviations = abbreviation_service.get_all(db, craft=craft, type=type)
    return AbbreviationListResponse(abbreviations=abbreviations)


@router.get(
    "/{abbreviation_id}",
    response_model=AbbreviationResponse,
    responses=_404,
    summary="Get abbreviation by ID",
    description="Returns the full detail of a single abbreviation by its UUID.",
)
def get_abbreviation(
    abbreviation_id: UUID,
    db: Session = Depends(get_db),
) -> AbbreviationResponse:
    return abbreviation_service.get_by_id(db, abbreviation_id)
