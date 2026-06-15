from uuid import UUID

from sqlalchemy.orm import Session

from app.models.pattern import GaugeUnit
from app.models.scaling import UserScaling


class ScalingRepository:
    def upsert(
        self,
        db: Session,
        pattern_id: UUID,
        size_label: str,
        size_position: int,
        gauge_stitches: float,
        gauge_rows: float | None,
        gauge_size: float,
        gauge_unit: GaugeUnit,
        needle_size: str | None,
    ) -> UserScaling:
        scaling = (
            db.query(UserScaling).filter(UserScaling.pattern_id == pattern_id).first()
        )
        if scaling is None:
            scaling = UserScaling(
                pattern_id=pattern_id,
                size_label=size_label,
                size_position=size_position,
                gauge_stitches=gauge_stitches,
                gauge_rows=gauge_rows,
                gauge_size=gauge_size,
                gauge_unit=gauge_unit,
                needle_size=needle_size,
            )
            db.add(scaling)
        else:
            scaling.size_label = size_label
            scaling.size_position = size_position
            scaling.gauge_stitches = gauge_stitches
            scaling.gauge_rows = gauge_rows
            scaling.gauge_size = gauge_size
            scaling.gauge_unit = gauge_unit
            scaling.needle_size = needle_size
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
