from app.models.pattern import GaugeUnit, Pattern
from app.models.scaling import UserScaling

_INCH_TO_CM: float = 2.54


def _gauge_density(stitches: float, size: float, unit: GaugeUnit) -> float:
    """Return stitches (or rows) per cm."""
    size_cm = size * _INCH_TO_CM if unit == GaugeUnit.INCH else size
    return stitches / size_cm


def _calculate_factors(
    pattern: Pattern, user_scaling: UserScaling
) -> tuple[float, float | None]:
    """Return (factor_stitches, factor_rows) for gauge scaling."""
    pattern_stitch_density = _gauge_density(
        pattern.gauge_stitches, pattern.gauge_size, pattern.gauge_unit
    )
    user_stitch_density = _gauge_density(
        user_scaling.gauge_stitches,
        user_scaling.gauge_size,
        user_scaling.gauge_unit,
    )
    factor_stitches = pattern_stitch_density / user_stitch_density

    factor_rows: float | None = None
    if user_scaling.gauge_rows and pattern.gauge_rows:
        pattern_row_density = _gauge_density(
            pattern.gauge_rows, pattern.gauge_size, pattern.gauge_unit
        )
        user_row_density = _gauge_density(
            user_scaling.gauge_rows,
            user_scaling.gauge_size,
            user_scaling.gauge_unit,
        )
        factor_rows = pattern_row_density / user_row_density

    return factor_stitches, factor_rows
