from math import ceil
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.pattern import YarnWeight
from app.models.yarn import UserYarn
from app.repositories.pattern import pattern_repository
from app.repositories.scaling import scaling_repository
from app.repositories.yarn import yarn_repository
from app.services.scaling.gauge_factors import _calculate_factors
from app.services.scaling.scaling_exceptions import (
    PatternNotFoundError,
    ScalingConfigNotFoundError,
)
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

    def calculate_yarn(self, db: Session, pattern_id: UUID) -> dict:
        pattern = pattern_repository.get_by_id(db, pattern_id)
        if pattern is None:
            raise PatternNotFoundError("Pattern not found")

        user_scaling = scaling_repository.get_by_pattern_id(db, pattern_id)
        if user_scaling is None:
            raise ScalingConfigNotFoundError("Please select a size and gauge first.")

        user_yarns = yarn_repository.get_by_pattern_id(db, pattern_id)
        if not user_yarns:
            raise UserYarnNotFoundError("Please enter your yarn data first.")

        factor_stitches, factor_rows = _calculate_factors(pattern, user_scaling)
        area_factor = factor_stitches * (
            factor_rows if factor_rows is not None else factor_stitches
        )

        user_yarn_map: dict[str, UserYarn] = {
            str(uy.pattern_yarn_id): uy for uy in user_yarns
        }

        yarns = []
        for pattern_yarn in pattern.yarns:
            user_yarn = user_yarn_map.get(str(pattern_yarn.id))

            pattern_yarn_summary = {
                "label": pattern_yarn.label,
                "yarn_weight": pattern_yarn.yarn_weight,
                "meters_per_unit": pattern_yarn.meters_per_unit,
                "grams_per_unit": pattern_yarn.grams_per_unit,
                "strands": pattern_yarn.strands,
                "grams_needed": None,
            }

            entry: dict = {
                "pattern_yarn_id": str(pattern_yarn.id),
                "calculated": False,
                "weight_warning": False,
                "pattern_yarn": pattern_yarn_summary,
                "user_yarn": None,
                "result": None,
                "message": None,
            }

            if user_yarn is None:
                entry["message"] = "No yarn data provided for this yarn."
                yarns.append(entry)
                continue

            entry["user_yarn"] = {
                "label": user_yarn.label,
                "yarn_weight": user_yarn.yarn_weight,
                "meters_per_unit": user_yarn.meters_per_unit,
                "grams_per_unit": user_yarn.grams_per_unit,
                "strands": user_yarn.strands,
            }

            if not pattern_yarn.grams_needed:
                entry["message"] = (
                    "This pattern does not specify how much yarn is needed."
                )
                yarns.append(entry)
                continue

            if (
                pattern_yarn.meters_per_unit is None
                or pattern_yarn.grams_per_unit is None
            ):
                entry["message"] = "Pattern yarn data is incomplete."
                yarns.append(entry)
                continue

            grams_needed_pattern = pattern_yarn.grams_needed[user_scaling.size_position]
            pattern_yarn_summary["grams_needed"] = grams_needed_pattern

            total_meters_pattern = (
                grams_needed_pattern
                / pattern_yarn.grams_per_unit
                * pattern_yarn.meters_per_unit
            )
            total_meters_scaled = total_meters_pattern * area_factor
            meters_per_strand = total_meters_scaled / pattern_yarn.strands
            total_meters_user = meters_per_strand * user_yarn.strands
            grams_needed_user = (
                total_meters_user / user_yarn.meters_per_unit * user_yarn.grams_per_unit
            )
            skeins_needed = ceil(total_meters_user / user_yarn.meters_per_unit)

            weight_warning = (
                pattern_yarn.yarn_weight is not None
                and user_yarn.yarn_weight is not None
                and pattern_yarn.yarn_weight != user_yarn.yarn_weight
            )

            entry["calculated"] = True
            entry["weight_warning"] = weight_warning
            entry["result"] = {
                "grams_needed": round(grams_needed_user, 1),
                "skeins_needed": skeins_needed,
            }
            yarns.append(entry)

        return {
            "size_label": user_scaling.size_label,
            "yarns": yarns,
        }


yarn_service = YarnService()
