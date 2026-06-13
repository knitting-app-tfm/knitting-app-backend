import math


def compute_yarn_calculation(
    pattern_yarn, user_yarn, factor_stitches, factor_rows, size_position
):
    """Returns (grams_needed, skeins_needed), or (None, None) if it cannot be calculated."""
    if (
        pattern_yarn.grams_needed is None
        or len(pattern_yarn.grams_needed) <= size_position
    ):
        return None, None
    if pattern_yarn.meters_per_unit is None or pattern_yarn.grams_per_unit is None:
        return None, None

    area_factor = factor_stitches * (
        factor_rows if factor_rows is not None else factor_stitches
    )

    grams_needed_pattern = pattern_yarn.grams_needed[size_position]
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
    skeins_needed = math.ceil(total_meters_user / user_yarn.meters_per_unit)

    return grams_needed_user, skeins_needed
