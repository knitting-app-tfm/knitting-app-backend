from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.pattern import PatternResponse
from app.services.pattern import (
    EmptyTextError,
    FileTooLargeError,
    InvalidFileTypeError,
    pattern_service,
)

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.post(
    "/import/pdf",
    response_model=PatternResponse,
    status_code=201,
    summary="Import pattern from PDF",
    description=(
        "Uploads a PDF file containing a knitting pattern. "
        "The text is extracted from the PDF and processed by the LLM to produce a structured pattern."
    ),
)
async def import_pattern_from_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> PatternResponse:
    content = await file.read()
    try:
        pattern = pattern_service.import_from_pdf(db, content, file.content_type)
    except InvalidFileTypeError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except FileTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e))
    return PatternResponse.model_validate(pattern)


@router.post(
    "/import/text",
    response_model=PatternResponse,
    status_code=201,
    summary="Import pattern from plain text",
    description=(
        "Receives a knitting pattern as plain text and processes it with the LLM "
        "to produce a structured pattern."
    ),
)
def import_pattern_from_text(
    text: str = Body(media_type="text/plain"),
    db: Session = Depends(get_db),
) -> PatternResponse:
    try:
        pattern = pattern_service.import_from_text(db, text)
    except EmptyTextError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return PatternResponse.model_validate(pattern)
