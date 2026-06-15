import json
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.pattern import CraftType, GaugeUnit
from app.models.user import User
from app.schemas.pattern import (
    ErrorResponse,
    LineTokens,
    PatternDetailResponse,
    PatternResponse,
)
from app.services.pattern import (
    EmptyTextError,
    EmptyTitleError,
    FileTooLargeError,
    InvalidFileTypeError,
    PatternNotConfirmedError,
    pattern_service,
)

router = APIRouter(prefix="/patterns", tags=["patterns"])

_404 = {404: {"model": ErrorResponse, "description": "Pattern not found"}}
_422 = {
    422: {
        "model": ErrorResponse,
        "description": "Validation error (e.g. empty title or text)",
    }
}
_413 = {413: {"model": ErrorResponse, "description": "File exceeds the 10 MB limit"}}
_415 = {415: {"model": ErrorResponse, "description": "File is not a PDF"}}


@router.get(
    "",
    response_model=list[PatternResponse],
    summary="List patterns for the authenticated user",
    description="Returns all patterns belonging to the authenticated user.",
)
def list_patterns(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PatternResponse]:
    patterns = pattern_service.get_by_user_id(db, current_user.id)
    return [PatternResponse.model_validate(p) for p in patterns]


@router.post(
    "/{pattern_id}/translate",
    response_model=list[LineTokens],
    responses={
        **_404,
        400: {"model": ErrorResponse, "description": "Pattern not yet confirmed"},
    },
    summary="Translate pattern into tokens",
    description=(
        "Tokenizes the pattern text and translates abbreviations. "
        "On first call (CONFIRMED), tokenizes and caches the result on disk, then advances "
        "status to TOKENIZED. Subsequent calls reuse the cached file. "
        "Abbreviation tokens are always resolved against the DB at call time."
    ),
)
def translate_pattern(
    pattern_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LineTokens]:
    try:
        result = pattern_service.translate(db, pattern_id)
    except PatternNotConfirmedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return [LineTokens.model_validate(lt) for lt in result]


@router.get(
    "/{pattern_id}",
    response_model=PatternDetailResponse,
    responses=_404,
    summary="Get pattern by ID",
    description=(
        "Returns pattern metadata for the confirmation form. "
        "For IMPORTED patterns, editable fields are read from the parsed_json on disk. "
        "For CONFIRMED patterns, all fields come from the database."
    ),
)
def get_pattern(
    pattern_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatternDetailResponse:
    data = pattern_service.get_prefill(db, pattern_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return PatternDetailResponse.model_validate(data)


@router.put(
    "/{pattern_id}/confirm",
    response_model=PatternResponse,
    responses={**_404, **_422},
    summary="Confirm pattern metadata",
    description=(
        "Updates the pattern with the user-confirmed metadata, sets status to CONFIRMED, "
        "and optionally saves a cover image."
    ),
)
async def confirm_pattern(
    pattern_id: UUID,
    title: str = Form(...),
    craft: CraftType = Form(...),
    gauge_stitches: float | None = Form(None),
    gauge_rows: float | None = Form(None),
    gauge_size: float | None = Form(None),
    gauge_unit: GaugeUnit | None = Form(None),
    needle_size: str | None = Form(None),
    sizes: str = Form("[]"),
    yarns: str = Form("[]"),
    cover_image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatternResponse:
    pattern = pattern_service.get_by_id(db, pattern_id)
    if pattern is None:
        raise HTTPException(status_code=404, detail="Pattern not found")

    cover_bytes = None
    cover_suffix = ".jpg"
    if cover_image is not None:
        cover_bytes = await cover_image.read()
        cover_suffix = Path(cover_image.filename or "").suffix or ".jpg"

    def _parse_json_list(value: str) -> list:
        if not value or not value.strip():
            return []
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return [item.strip() for item in value.split(",") if item.strip()]

    try:
        confirmed = pattern_service.confirm(
            db,
            pattern,
            title=title,
            craft=craft,
            gauge_stitches=gauge_stitches,
            gauge_rows=gauge_rows,
            gauge_size=gauge_size,
            gauge_unit=gauge_unit,
            needle_size=needle_size,
            sizes=_parse_json_list(sizes),
            yarns_data=_parse_json_list(yarns),
            cover_bytes=cover_bytes,
            cover_suffix=cover_suffix,
        )
    except EmptyTitleError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PatternResponse.model_validate(confirmed)


@router.post(
    "/import/pdf",
    response_model=PatternResponse,
    status_code=201,
    responses={**_413, **_415},
    summary="Import pattern from PDF",
    description=(
        "Uploads a PDF file containing a knitting pattern. "
        "The text is extracted from the PDF and processed by the LLM to produce a structured pattern."
    ),
)
async def import_pattern_from_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatternResponse:
    content = await file.read()
    try:
        pattern = pattern_service.import_from_pdf(
            db, content, file.content_type, current_user.id
        )
    except InvalidFileTypeError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except FileTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e))
    return PatternResponse.model_validate(pattern)


@router.post(
    "/import/text",
    response_model=PatternResponse,
    status_code=201,
    responses=_422,
    summary="Import pattern from plain text",
    description=(
        "Receives a knitting pattern as plain text and processes it with the LLM "
        "to produce a structured pattern."
    ),
)
def import_pattern_from_text(
    text: str = Body(media_type="text/plain"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatternResponse:
    try:
        pattern = pattern_service.import_from_text(db, text, current_user.id)
    except EmptyTextError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return PatternResponse.model_validate(pattern)
