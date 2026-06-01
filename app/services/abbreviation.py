from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.abbreviation import Abbreviation, AbbreviationCraft, AbbreviationType
from app.repositories.abbreviation import abbreviation_repository


class AbbreviationService:
    def get_all(
        self,
        db: Session,
        craft: AbbreviationCraft | None = None,
        type: AbbreviationType | None = None,
    ) -> list[Abbreviation]:
        return abbreviation_repository.get_all(db, craft=craft, type=type)

    def get_by_id(self, db: Session, abbreviation_id: UUID) -> Abbreviation:
        abbreviation = abbreviation_repository.get_by_id(db, abbreviation_id)
        if abbreviation is None:
            raise HTTPException(status_code=404, detail="Abbreviation not found")
        return abbreviation


abbreviation_service = AbbreviationService()
