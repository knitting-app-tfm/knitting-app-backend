from uuid import UUID

from sqlalchemy.orm import Session

from app.models.scaling import UserScaling


class ScalingRepository:
    def upsert(
        self, db: Session, pattern_id: UUID, size_label: str, size_position: int
    ) -> UserScaling:
        scaling = (
            db.query(UserScaling).filter(UserScaling.pattern_id == pattern_id).first()
        )
        if scaling is None:
            scaling = UserScaling(
                pattern_id=pattern_id,
                size_label=size_label,
                size_position=size_position,
            )
            db.add(scaling)
        else:
            scaling.size_label = size_label
            scaling.size_position = size_position
        db.commit()
        db.refresh(scaling)
        return scaling

    def get_by_pattern_id(self, db: Session, pattern_id: UUID) -> UserScaling | None:
        return (
            db.query(UserScaling).filter(UserScaling.pattern_id == pattern_id).first()
        )

    def delete_by_pattern_id(self, db: Session, pattern_id: UUID) -> None:
        scaling = (
            db.query(UserScaling).filter(UserScaling.pattern_id == pattern_id).first()
        )
        if scaling is not None:
            db.delete(scaling)
            db.commit()


scaling_repository = ScalingRepository()
