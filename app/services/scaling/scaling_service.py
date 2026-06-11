from uuid import UUID

from sqlalchemy.orm import Session

from app.models.pattern import GaugeUnit
from app.models.scaling import UserScaling
from app.repositories.pattern import pattern_repository
from app.repositories.scaling import scaling_repository
from app.services.scaling.scaling_exceptions import (
    InvalidGaugeError,
    InvalidSizeLabelError,
    InvalidSizePositionError,
    PatternNotFoundError,
)


class ScalingService:
    def upsert_size(
        self,
        db: Session,
        pattern_id: UUID,
        size_label: str,
        size_position: int,
        gauge_stitches: float,
        gauge_rows: float | None,
        gauge_size: float,
        gauge_unit: str,
        needle_size: str | None,
    ) -> UserScaling:
        pattern = pattern_repository.get_by_id(db, pattern_id)
        if pattern is None:
            raise PatternNotFoundError("Pattern not found")

        sizes = pattern.sizes or []
        if not sizes:
            size_label = "One size"
            size_position = 0
        else:
            if size_label not in sizes:
                raise InvalidSizeLabelError(
                    f"Size '{size_label}' is not available for this pattern"
                )
            if sizes.index(size_label) != size_position:
                raise InvalidSizePositionError(
                    f"Position {size_position} does not match the index of '{size_label}'"
                )

        if gauge_stitches <= 0:
            raise InvalidGaugeError("Value must be greater than zero")
        if gauge_stitches != int(gauge_stitches):
            raise InvalidGaugeError(
                "gauge_stitches must be a positive integer (no decimals)"
            )

        if gauge_rows is not None:
            if gauge_rows <= 0:
                raise InvalidGaugeError("Value must be greater than zero")
            if gauge_rows != int(gauge_rows):
                raise InvalidGaugeError(
                    "gauge_rows must be a positive integer (no decimals)"
                )

        if gauge_size <= 0:
            raise InvalidGaugeError("Value must be greater than zero")

        try:
            gauge_unit_enum = GaugeUnit(gauge_unit)
        except ValueError:
            raise InvalidGaugeError(f"Invalid gauge unit: '{gauge_unit}'")

        return scaling_repository.upsert(
            db,
            pattern_id,
            size_label,
            size_position,
            gauge_stitches,
            gauge_rows,
            gauge_size,
            gauge_unit_enum,
            needle_size,
        )

    def get_by_pattern_id(self, db: Session, pattern_id: UUID) -> UserScaling | None:
        return scaling_repository.get_by_pattern_id(db, pattern_id)


scaling_service = ScalingService()
