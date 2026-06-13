from uuid import UUID

from sqlalchemy.orm import Session

from app.models.pattern import YarnWeight
from app.models.yarn import UserYarn
from app.repositories.pattern import pattern_repository
from app.repositories.scaling import scaling_repository
from app.repositories.yarn import yarn_repository
from app.services.scaling.scaling_exceptions import ScalingConfigNotFoundError
from app.services.yarn.yarn_exceptions import (
    InvalidYarnDataError,
    PatternYarnNotFoundError,
)


class YarnService:
    def upsert_yarn(
        self,
        db: Session,
        pattern_id: UUID,
        pattern_yarn_id: UUID,
        label: str | None,
        yarn_weight: str | None,
        meters_per_unit: float,
        grams_per_unit: float,
        strands: int,
    ) -> UserYarn:
        if scaling_repository.get_by_pattern_id(db, pattern_id) is None:
            raise ScalingConfigNotFoundError("Please select a size and gauge first.")

        pattern = pattern_repository.get_by_id(db, pattern_id)
        if pattern is None or not any(
            str(y.id) == str(pattern_yarn_id) for y in pattern.yarns
        ):
            raise PatternYarnNotFoundError(
                f"Yarn {pattern_yarn_id} not found for pattern {pattern_id}"
            )

        if meters_per_unit <= 0:
            raise InvalidYarnDataError("Value must be greater than zero")
        if grams_per_unit <= 0:
            raise InvalidYarnDataError("Value must be greater than zero")
        if strands != int(strands):
            raise InvalidYarnDataError("El número de strands debe ser un número entero")
        if strands <= 0:
            raise InvalidYarnDataError("Value must be greater than zero")

        yarn_weight_enum: YarnWeight | None = None
        if yarn_weight is not None:
            try:
                yarn_weight_enum = YarnWeight(yarn_weight)
            except ValueError:
                yarn_weight_enum = None

        return yarn_repository.upsert(
            db,
            pattern_yarn_id=pattern_yarn_id,
            label=label,
            yarn_weight=yarn_weight_enum,
            meters_per_unit=meters_per_unit,
            grams_per_unit=grams_per_unit,
            strands=strands,
        )

    def get_by_pattern_id(self, db: Session, pattern_id: UUID) -> list[UserYarn]:
        return yarn_repository.get_by_pattern_id(db, pattern_id)


yarn_service = YarnService()
