from sqlalchemy.orm import Session

from app.models.pattern import Pattern, PatternYarn


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


pattern_repository = PatternRepository()
