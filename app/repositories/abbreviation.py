from uuid import UUID

from sqlalchemy.orm import Session

from app.models.abbreviation import Abbreviation, AbbreviationCraft, AbbreviationType


class AbbreviationRepository:
    def get_all(
        self,
        db: Session,
        craft: AbbreviationCraft | None = None,
        type: AbbreviationType | None = None,
    ) -> list[Abbreviation]:
        query = db.query(Abbreviation)
        if craft is not None:
            query = query.filter(Abbreviation.craft == craft)
        if type is not None:
            query = query.filter(Abbreviation.type == type)
        return query.all()

    def get_by_id(self, db: Session, abbreviation_id: UUID) -> Abbreviation | None:
        return db.get(Abbreviation, abbreviation_id)


abbreviation_repository = AbbreviationRepository()
