from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.pattern import PatternResponse
from app.services.pattern import (
    FileTooLargeError,
    InvalidFileTypeError,
    pattern_service,
)

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.post("/import/pdf", response_model=PatternResponse, status_code=201)
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
