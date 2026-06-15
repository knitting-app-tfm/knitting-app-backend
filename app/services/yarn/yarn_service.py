from uuid import UUID

from sqlalchemy.orm import Session

from app.models.pattern import YarnWeight
from app.models.yarn import UserYarn
from app.repositories.pattern import pattern_repository
from app.repositories.scaling import scaling_repository
from app.repositories.yarn import yarn_repository
from app.services.scaling.gauge_factors import _calculate_factors
from app.services.scaling.scaling_exceptions import ScalingConfigNotFoundError
from app.services.scaling.yarn_calculation import compute_yarn_calculation
from app.services.yarn.yarn_exceptions import (
    InvalidYarnDataError,
    PatternYarnNotFoundError,
    UserYarnNotFoundError,
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
        user_scaling = scaling_repository.get_by_pattern_id(db, pattern_id)
        if user_scaling is None:
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

        user_yarn = yarn_repository.upsert(
            db,
            pattern_yarn_id=pattern_yarn_id,
            label=label,
            yarn_weight=yarn_weight_enum,
            meters_per_unit=meters_per_unit,
            grams_per_unit=grams_per_unit,
            strands=strands,
        )

        pattern_yarn_obj = next(
            y for y in pattern.yarns if str(y.id) == str(pattern_yarn_id)
        )
        factor_stitches, factor_rows = _calculate_factors(pattern, user_scaling)
        grams, skeins = compute_yarn_calculation(
            pattern_yarn_obj,
            user_yarn,
            factor_stitches,
            factor_rows,
            user_scaling.size_position,
        )
        user_yarn.calculated_grams_needed = grams
        user_yarn.calculated_skeins_needed = skeins
        db.commit()
        db.refresh(user_yarn)
        return user_yarn

    def get_by_pattern_id(self, db: Session, pattern_id: UUID) -> list[UserYarn]:
        return yarn_repository.get_by_pattern_id(db, pattern_id)

    def get_calculations(self, db: Session, pattern_id: UUID) -> dict:
        user_scaling = scaling_repository.get_by_pattern_id(db, pattern_id)
        if user_scaling is None:
            raise ScalingConfigNotFoundError("Please select a size and gauge first.")

        user_yarns = yarn_repository.get_by_pattern_id(db, pattern_id)
        if not user_yarns:
            raise UserYarnNotFoundError("Please enter your yarn data first.")

        yarns = []
        for user_yarn in user_yarns:
            pattern_yarn = user_yarn.pattern_yarn
            grams_needed_at_size = (
                pattern_yarn.grams_needed[user_scaling.size_position]
                if pattern_yarn.grams_needed
                and len(pattern_yarn.grams_needed) > user_scaling.size_position
                else None
            )
            calculated = user_yarn.calculated_grams_needed is not None
            weight_warning = (
                pattern_yarn.yarn_weight is not None
                and user_yarn.yarn_weight is not None
                and pattern_yarn.yarn_weight != user_yarn.yarn_weight
            )

            entry: dict = {
                "pattern_yarn_id": str(pattern_yarn.id),
                "calculated": calculated,
                "weight_warning": weight_warning,
                "pattern_yarn": {
                    "label": pattern_yarn.label,
                    "yarn_weight": pattern_yarn.yarn_weight,
                    "meters_per_unit": pattern_yarn.meters_per_unit,
                    "grams_per_unit": pattern_yarn.grams_per_unit,
                    "strands": pattern_yarn.strands,
                    "grams_needed": grams_needed_at_size,
                },
                "user_yarn": {
                    "label": user_yarn.label,
                    "yarn_weight": user_yarn.yarn_weight,
                    "meters_per_unit": user_yarn.meters_per_unit,
                    "grams_per_unit": user_yarn.grams_per_unit,
                    "strands": user_yarn.strands,
                },
                "result": None,
                "message": None,
            }

            if calculated:
                entry["result"] = {
                    "grams_needed": round(user_yarn.calculated_grams_needed, 1),
                    "skeins_needed": user_yarn.calculated_skeins_needed,
                }
            elif not pattern_yarn.grams_needed:
                entry["message"] = (
                    "This pattern does not specify how much yarn is needed."
                )
            elif (
                pattern_yarn.meters_per_unit is None
                or pattern_yarn.grams_per_unit is None
            ):
                entry["message"] = "Pattern yarn data is incomplete."
            else:
                entry["message"] = "Calculation is not available."

            yarns.append(entry)

        return {"size_label": user_scaling.size_label, "yarns": yarns}


yarn_service = YarnService()
