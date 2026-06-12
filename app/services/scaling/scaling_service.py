from uuid import UUID

from sqlalchemy.orm import Session

from app.models.pattern import GaugeUnit, PatternStatus
from app.models.scaling import UserScaling
from app.repositories.pattern import pattern_repository
from app.repositories.scaling import scaling_repository
from app.services.pattern import pattern_storage
from app.services.scaling.scaling_exceptions import (
    InvalidGaugeError,
    InvalidSizeLabelError,
    InvalidSizePositionError,
    PatternNotFoundError,
    PatternNotTokenizedError,
    ScalingConfigNotFoundError,
)

_STITCH_UNITS: frozenset[str] = frozenset({"stitches", "stitch", "sts", "st"})
_ROW_UNITS: frozenset[str] = frozenset({"rows", "row", "rounds", "round"})
_SCALABLE_UNITS: frozenset[str] = _STITCH_UNITS | _ROW_UNITS


def _scale_token(
    token: dict,
    size_position: int,
    num_sizes: int,
    factor_stitches: float,
    factor_rows: float | None,
) -> tuple[dict, bool]:
    """Returns (scaled_token, rows_warning)."""
    token_type = token["type"]

    if token_type == "size_group":
        values: list = token["values"]
        unit: str | None = token.get("unit")
        unit_lower = unit.lower() if unit else None

        # A leading bare number shifts all size values by 1
        offset = 1 if (num_sizes > 0 and len(values) == num_sizes + 1) else 0
        idx = size_position + offset
        extracted = values[idx] if idx < len(values) else values[-1]

        scaled = False
        rows_warning = False
        if unit_lower in _STITCH_UNITS:
            extracted = round(extracted * factor_stitches)
            scaled = True
        elif unit_lower in _ROW_UNITS:
            if factor_rows is not None:
                extracted = round(extracted * factor_rows)
                scaled = True
            else:
                rows_warning = True

        new_token: dict = {
            "type": "number",
            "value": extracted,
            "unit": unit,
            "scalable": unit_lower in _SCALABLE_UNITS if unit_lower else False,
            "scaled": scaled,
        }
        if rows_warning:
            new_token["rows_warning"] = True
        return new_token, rows_warning

    if token_type == "number":
        unit = token.get("unit")
        unit_lower = unit.lower() if unit else None
        value = token["value"]

        if unit_lower in _STITCH_UNITS:
            return {
                **token,
                "value": round(value * factor_stitches),
                "scaled": True,
            }, False
        if unit_lower in _ROW_UNITS:
            if factor_rows is not None:
                return {
                    **token,
                    "value": round(value * factor_rows),
                    "scaled": True,
                }, False
            return {**token, "scaled": False, "rows_warning": True}, True
        return {**token, "scaled": False}, False

    # text, abbreviation — pass through unchanged
    return token, False


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

    def scale_pattern(self, db: Session, pattern_id: UUID) -> dict:
        pattern = pattern_repository.get_by_id(db, pattern_id)
        if pattern is None:
            raise PatternNotFoundError("Pattern not found")
        if pattern.status != PatternStatus.TOKENIZED:
            raise PatternNotTokenizedError("Pattern must be translated before scaling")

        user_scaling = scaling_repository.get_by_pattern_id(db, pattern_id)
        if user_scaling is None:
            raise ScalingConfigNotFoundError(
                "No scaling configuration found. Please select a size and gauge first."
            )

        lines = pattern_storage.read_tokens_file(f"storage/tokens/{pattern_id}.json")

        factor_stitches = pattern.gauge_stitches / user_scaling.gauge_stitches
        factor_rows = (
            pattern.gauge_rows / user_scaling.gauge_rows
            if user_scaling.gauge_rows
            else None
        )

        num_sizes = len(pattern.sizes) if pattern.sizes else 0
        size_position = user_scaling.size_position

        rows_warning = False
        scaled_lines = []
        for line in lines:
            scaled_tokens = []
            for token in line.get("tokens", []):
                scaled_token, token_rows_warning = _scale_token(
                    token, size_position, num_sizes, factor_stitches, factor_rows
                )
                if token_rows_warning:
                    rows_warning = True
                scaled_tokens.append(scaled_token)
            scaled_lines.append({**line, "tokens": scaled_tokens})

        return {
            "rows_warning": rows_warning,
            "size_label": user_scaling.size_label,
            "lines": scaled_lines,
        }


scaling_service = ScalingService()
