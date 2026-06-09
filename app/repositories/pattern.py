from uuid import UUID

from sqlalchemy.orm import Session

from app.models.pattern import Pattern, PatternStatus, PatternYarn


class PatternRepository:
    def create(self, db: Session, yarns_data: list[dict], **pattern_kwargs) -> Pattern:
        pattern = Pattern(**pattern_kwargs)
        db.add(pattern)
        db.flush()

        for yarn_data in yarns_data:
            yarn = PatternYarn(pattern_id=pattern.id, **yarn_data)
            db.add(yarn)

        db.commit()
        db.refresh(pattern)
        return pattern

    def get_by_id(self, db: Session, pattern_id: UUID) -> Pattern | None:
        return db.get(Pattern, pattern_id)

    def get_by_user_id(self, db: Session, user_id: UUID) -> list[Pattern]:
        return db.query(Pattern).filter(Pattern.user_id == user_id).all()

    def update(
        self, db: Session, pattern: Pattern, yarns_data: list[dict], **pattern_kwargs
    ) -> Pattern:
        for key, value in pattern_kwargs.items():
            setattr(pattern, key, value)

        for yarn in list(pattern.yarns):
            db.delete(yarn)
        db.flush()

        for yarn_data in yarns_data:
            yarn = PatternYarn(pattern_id=pattern.id, **yarn_data)
            db.add(yarn)

        db.commit()
        db.refresh(pattern)
        return pattern

    def set_tokenized(
        self, db: Session, pattern: Pattern, tokens_file_path: str
    ) -> Pattern:
        """Update only the tokens path and status to TOKENIZED."""
        pattern.tokens_file_path = tokens_file_path
        pattern.status = PatternStatus.TOKENIZED
        db.commit()
        db.refresh(pattern)
        return pattern


pattern_repository = PatternRepository()
