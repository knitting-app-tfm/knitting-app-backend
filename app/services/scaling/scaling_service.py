from uuid import UUID

from sqlalchemy.orm import Session

from app.models.scaling import UserScaling
from app.repositories.pattern import pattern_repository
from app.repositories.scaling import scaling_repository
from app.services.scaling.scaling_exceptions import (
    InvalidSizeLabelError,
    InvalidSizePositionError,
    PatternNotFoundError,
)


class ScalingService:
    def upsert_size(
        self, db: Session, pattern_id: UUID, size_label: str, size_position: int
    ) -> UserScaling:
        pattern = pattern_repository.get_by_id(db, pattern_id)
        if pattern is None:
            raise PatternNotFoundError("Pattern not found")

        sizes = pattern.sizes or []
        if size_label not in sizes:
            raise InvalidSizeLabelError(
                f"Size '{size_label}' is not available for this pattern"
            )
        if sizes.index(size_label) != size_position:
            raise InvalidSizePositionError(
                f"Position {size_position} does not match the index of '{size_label}'"
            )

        return scaling_repository.upsert(db, pattern_id, size_label, size_position)

    def get_by_pattern_id(self, db: Session, pattern_id: UUID) -> UserScaling | None:
        return scaling_repository.get_by_pattern_id(db, pattern_id)


scaling_service = ScalingService()
