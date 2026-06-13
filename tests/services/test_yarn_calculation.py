import math
from unittest.mock import MagicMock

import pytest

from app.services.scaling.yarn_calculation import compute_yarn_calculation


def _make_pattern_yarn(
    *,
    grams_needed=None,
    meters_per_unit=200.0,
    grams_per_unit=100.0,
    strands=1,
):
    py = MagicMock()
    py.grams_needed = grams_needed
    py.meters_per_unit = meters_per_unit
    py.grams_per_unit = grams_per_unit
    py.strands = strands
    return py


def _make_user_yarn(*, meters_per_unit=200.0, grams_per_unit=100.0, strands=1):
    uy = MagicMock()
    uy.meters_per_unit = meters_per_unit
    uy.grams_per_unit = grams_per_unit
    uy.strands = strands
    return uy


class TestComputeYarnCalculation:
    def test_basic_same_yarn(self):
        # identical yarn, factor 1.0 → result equals pattern values at position
        py = _make_pattern_yarn(
            grams_needed=[200.0, 350.0],
            meters_per_unit=200.0,
            grams_per_unit=100.0,
            strands=1,
        )
        uy = _make_user_yarn(meters_per_unit=200.0, grams_per_unit=100.0, strands=1)

        grams, skeins = compute_yarn_calculation(py, uy, 1.0, 1.0, 1)

        # total_meters_pattern = 350/100*200 = 700; area_factor=1*1=1; user same → grams=350, skeins=ceil(700/200)=4
        assert grams == pytest.approx(350.0)
        assert skeins == 4

    def test_with_stitch_and_row_factors(self):
        # area_factor = 1.2 * 0.9 = 1.08
        py = _make_pattern_yarn(
            grams_needed=[350.0], meters_per_unit=200.0, grams_per_unit=100.0, strands=1
        )
        uy = _make_user_yarn(meters_per_unit=200.0, grams_per_unit=100.0, strands=1)

        grams, skeins = compute_yarn_calculation(py, uy, 1.2, 0.9, 0)

        # total_meters_pattern = 700; scaled = 700*1.08 = 756; grams = 756/200*100 = 378
        assert grams == pytest.approx(378.0, abs=0.01)
        assert skeins == math.ceil(756.0 / 200.0)  # 4

    def test_factor_rows_none_uses_factor_stitches_squared(self):
        # factor_rows=None → area_factor = 1.2 * 1.2 = 1.44
        py = _make_pattern_yarn(
            grams_needed=[350.0], meters_per_unit=200.0, grams_per_unit=100.0, strands=1
        )
        uy = _make_user_yarn(meters_per_unit=200.0, grams_per_unit=100.0, strands=1)

        grams, skeins = compute_yarn_calculation(py, uy, 1.2, None, 0)

        # total_meters_pattern = 700; scaled = 700*1.44 = 1008; grams = 1008/200*100 = 504
        assert grams == pytest.approx(504.0, abs=0.01)
        assert skeins == math.ceil(1008.0 / 200.0)  # 6

    def test_different_strands(self):
        # pattern uses 2 strands, user uses 1 → meters_per_strand halved
        py = _make_pattern_yarn(
            grams_needed=[350.0], meters_per_unit=200.0, grams_per_unit=100.0, strands=2
        )
        uy = _make_user_yarn(meters_per_unit=200.0, grams_per_unit=100.0, strands=1)

        grams, skeins = compute_yarn_calculation(py, uy, 1.0, 1.0, 0)

        # total_meters_pattern=700; scaled=700; meters_per_strand=700/2=350; user=350*1=350
        # grams=350/200*100=175; skeins=ceil(350/200)=2
        assert grams == pytest.approx(175.0)
        assert skeins == 2

    def test_different_yarn_density(self):
        # user yarn: 300m/100g vs pattern 200m/100g
        py = _make_pattern_yarn(
            grams_needed=[350.0], meters_per_unit=200.0, grams_per_unit=100.0, strands=1
        )
        uy = _make_user_yarn(meters_per_unit=300.0, grams_per_unit=100.0, strands=1)

        grams, skeins = compute_yarn_calculation(py, uy, 1.0, 1.0, 0)

        # total_meters_user=700; grams=700/300*100≈233.3; skeins=ceil(700/300)=3
        assert grams == pytest.approx(700.0 / 300.0 * 100.0, abs=0.01)
        assert skeins == 3

    def test_grams_needed_none_returns_none(self):
        py = _make_pattern_yarn(grams_needed=None)
        uy = _make_user_yarn()

        result = compute_yarn_calculation(py, uy, 1.0, 1.0, 0)

        assert result == (None, None)

    def test_size_position_out_of_range_returns_none(self):
        py = _make_pattern_yarn(grams_needed=[350.0])  # only one size
        uy = _make_user_yarn()

        result = compute_yarn_calculation(py, uy, 1.0, 1.0, 5)

        assert result == (None, None)

    def test_pattern_yarn_missing_meters_returns_none(self):
        py = _make_pattern_yarn(grams_needed=[350.0], meters_per_unit=None)
        uy = _make_user_yarn()

        result = compute_yarn_calculation(py, uy, 1.0, 1.0, 0)

        assert result == (None, None)

    def test_pattern_yarn_missing_grams_per_unit_returns_none(self):
        py = _make_pattern_yarn(grams_needed=[350.0], grams_per_unit=None)
        uy = _make_user_yarn()

        result = compute_yarn_calculation(py, uy, 1.0, 1.0, 0)

        assert result == (None, None)

    def test_size_position_selects_correct_value(self):
        py = _make_pattern_yarn(
            grams_needed=[200.0, 350.0, 500.0],
            meters_per_unit=200.0,
            grams_per_unit=100.0,
            strands=1,
        )
        uy = _make_user_yarn(meters_per_unit=200.0, grams_per_unit=100.0, strands=1)

        grams_l, _ = compute_yarn_calculation(py, uy, 1.0, 1.0, 2)

        # size_position=2 → grams_needed=500
        assert grams_l == pytest.approx(500.0)

    def test_skeins_ceil(self):
        # Total meters = 201, skein = 200m → needs 2 skeins
        py = _make_pattern_yarn(
            grams_needed=[100.5],
            meters_per_unit=200.0,
            grams_per_unit=100.0,
            strands=1,
        )
        uy = _make_user_yarn(meters_per_unit=200.0, grams_per_unit=100.0, strands=1)

        # total_meters_pattern = 100.5/100*200 = 201; area_factor=1 → total_user=201
        _, skeins = compute_yarn_calculation(py, uy, 1.0, 1.0, 0)

        assert skeins == 2
