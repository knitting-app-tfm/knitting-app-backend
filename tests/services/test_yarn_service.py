import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.pattern import YarnWeight
from app.services.scaling.scaling_exceptions import ScalingConfigNotFoundError
from app.services.yarn import (
    InvalidYarnDataError,
    PatternYarnNotFoundError,
    UserYarnNotFoundError,
    YarnService,
)


@pytest.fixture
def service():
    return YarnService()


@pytest.fixture
def pattern_id():
    return uuid.uuid4()


@pytest.fixture
def pattern_yarn_id():
    return uuid.uuid4()


@pytest.fixture
def valid_kwargs():
    return dict(
        label="Main",
        yarn_weight="DK",
        meters_per_unit=200.0,
        grams_per_unit=100.0,
        strands=1,
    )


def _make_pattern(pattern_yarn_id):
    """Pattern mock with one yarn whose id matches pattern_yarn_id."""
    pattern = MagicMock()
    yarn = MagicMock()
    yarn.id = pattern_yarn_id
    pattern.yarns = [yarn]
    return pattern


def _make_pattern_yarn(
    py_id=None,
    *,
    grams_needed=None,
    meters_per_unit=200.0,
    grams_per_unit=100.0,
    strands=1,
    yarn_weight=YarnWeight.DK,
    label="Main",
):
    py = MagicMock()
    py.id = py_id or uuid.uuid4()
    py.grams_needed = grams_needed
    py.meters_per_unit = meters_per_unit
    py.grams_per_unit = grams_per_unit
    py.strands = strands
    py.yarn_weight = yarn_weight
    py.label = label
    return py


def _make_scaling(size_label="M", size_position=1):
    s = MagicMock()
    s.size_label = size_label
    s.size_position = size_position
    return s


class TestUpsertYarn:
    def test_upsert_yarn_valid(
        self, service, pattern_id, pattern_yarn_id, valid_kwargs
    ):
        pattern = _make_pattern(pattern_yarn_id)
        expected = MagicMock()

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.pattern_repository") as mock_pr,
            patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr,
            patch(
                "app.services.yarn.yarn_service._calculate_factors",
                return_value=(1.0, 1.0),
            ),
            patch(
                "app.services.yarn.yarn_service.compute_yarn_calculation",
                return_value=(None, None),
            ),
        ):
            mock_sr.get_by_pattern_id.return_value = MagicMock()
            mock_pr.get_by_id.return_value = pattern
            mock_yr.upsert.return_value = expected

            result = service.upsert_yarn(
                MagicMock(), pattern_id, pattern_yarn_id, **valid_kwargs
            )

        assert result is expected
        call_kwargs = mock_yr.upsert.call_args.kwargs
        assert call_kwargs["yarn_weight"] == YarnWeight.DK
        assert call_kwargs["meters_per_unit"] == 200.0
        assert call_kwargs["grams_per_unit"] == 100.0
        assert call_kwargs["strands"] == 1

    def test_upsert_yarn_stores_calculation(
        self, service, pattern_id, pattern_yarn_id, valid_kwargs
    ):
        pattern = _make_pattern(pattern_yarn_id)
        user_yarn = MagicMock()
        db = MagicMock()

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.pattern_repository") as mock_pr,
            patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr,
            patch(
                "app.services.yarn.yarn_service._calculate_factors",
                return_value=(1.0, 1.0),
            ),
            patch(
                "app.services.yarn.yarn_service.compute_yarn_calculation",
                return_value=(350.0, 2),
            ),
        ):
            mock_sr.get_by_pattern_id.return_value = MagicMock()
            mock_pr.get_by_id.return_value = pattern
            mock_yr.upsert.return_value = user_yarn

            service.upsert_yarn(db, pattern_id, pattern_yarn_id, **valid_kwargs)

        assert user_yarn.calculated_grams_needed == 350.0
        assert user_yarn.calculated_skeins_needed == 2
        db.commit.assert_called()

    def test_upsert_yarn_no_scaling(
        self, service, pattern_id, pattern_yarn_id, valid_kwargs
    ):
        with patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr:
            mock_sr.get_by_pattern_id.return_value = None

            with pytest.raises(ScalingConfigNotFoundError):
                service.upsert_yarn(
                    MagicMock(), pattern_id, pattern_yarn_id, **valid_kwargs
                )

    def test_upsert_yarn_invalid_pattern_yarn_id(
        self, service, pattern_id, pattern_yarn_id, valid_kwargs
    ):
        pattern = MagicMock()
        pattern.yarns = []  # no yarn with matching id

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.pattern_repository") as mock_pr,
        ):
            mock_sr.get_by_pattern_id.return_value = MagicMock()
            mock_pr.get_by_id.return_value = pattern

            with pytest.raises(PatternYarnNotFoundError):
                service.upsert_yarn(
                    MagicMock(), pattern_id, pattern_yarn_id, **valid_kwargs
                )

    def test_upsert_yarn_meters_zero(
        self, service, pattern_id, pattern_yarn_id, valid_kwargs
    ):
        pattern = _make_pattern(pattern_yarn_id)
        valid_kwargs["meters_per_unit"] = 0.0

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.pattern_repository") as mock_pr,
        ):
            mock_sr.get_by_pattern_id.return_value = MagicMock()
            mock_pr.get_by_id.return_value = pattern

            with pytest.raises(
                InvalidYarnDataError, match="Value must be greater than zero"
            ):
                service.upsert_yarn(
                    MagicMock(), pattern_id, pattern_yarn_id, **valid_kwargs
                )

    def test_upsert_yarn_grams_negative(
        self, service, pattern_id, pattern_yarn_id, valid_kwargs
    ):
        pattern = _make_pattern(pattern_yarn_id)
        valid_kwargs["grams_per_unit"] = -1.0

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.pattern_repository") as mock_pr,
        ):
            mock_sr.get_by_pattern_id.return_value = MagicMock()
            mock_pr.get_by_id.return_value = pattern

            with pytest.raises(
                InvalidYarnDataError, match="Value must be greater than zero"
            ):
                service.upsert_yarn(
                    MagicMock(), pattern_id, pattern_yarn_id, **valid_kwargs
                )

    def test_upsert_yarn_strands_decimal(
        self, service, pattern_id, pattern_yarn_id, valid_kwargs
    ):
        pattern = _make_pattern(pattern_yarn_id)
        valid_kwargs["strands"] = 1.5

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.pattern_repository") as mock_pr,
        ):
            mock_sr.get_by_pattern_id.return_value = MagicMock()
            mock_pr.get_by_id.return_value = pattern

            with pytest.raises(InvalidYarnDataError, match="número entero"):
                service.upsert_yarn(
                    MagicMock(), pattern_id, pattern_yarn_id, **valid_kwargs
                )

    def test_upsert_yarn_strands_zero(
        self, service, pattern_id, pattern_yarn_id, valid_kwargs
    ):
        pattern = _make_pattern(pattern_yarn_id)
        valid_kwargs["strands"] = 0

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.pattern_repository") as mock_pr,
        ):
            mock_sr.get_by_pattern_id.return_value = MagicMock()
            mock_pr.get_by_id.return_value = pattern

            with pytest.raises(
                InvalidYarnDataError, match="Value must be greater than zero"
            ):
                service.upsert_yarn(
                    MagicMock(), pattern_id, pattern_yarn_id, **valid_kwargs
                )

    def test_upsert_yarn_unknown_weight_becomes_none(
        self, service, pattern_id, pattern_yarn_id, valid_kwargs
    ):
        pattern = _make_pattern(pattern_yarn_id)
        valid_kwargs["yarn_weight"] = "CHUNKY"

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.pattern_repository") as mock_pr,
            patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr,
            patch(
                "app.services.yarn.yarn_service._calculate_factors",
                return_value=(1.0, 1.0),
            ),
            patch(
                "app.services.yarn.yarn_service.compute_yarn_calculation",
                return_value=(None, None),
            ),
        ):
            mock_sr.get_by_pattern_id.return_value = MagicMock()
            mock_pr.get_by_id.return_value = pattern
            mock_yr.upsert.return_value = MagicMock()

            service.upsert_yarn(
                MagicMock(), pattern_id, pattern_yarn_id, **valid_kwargs
            )

        assert mock_yr.upsert.call_args.kwargs["yarn_weight"] is None

    def test_upsert_yarn_none_weight_stays_none(
        self, service, pattern_id, pattern_yarn_id, valid_kwargs
    ):
        pattern = _make_pattern(pattern_yarn_id)
        valid_kwargs["yarn_weight"] = None

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.pattern_repository") as mock_pr,
            patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr,
            patch(
                "app.services.yarn.yarn_service._calculate_factors",
                return_value=(1.0, 1.0),
            ),
            patch(
                "app.services.yarn.yarn_service.compute_yarn_calculation",
                return_value=(None, None),
            ),
        ):
            mock_sr.get_by_pattern_id.return_value = MagicMock()
            mock_pr.get_by_id.return_value = pattern
            mock_yr.upsert.return_value = MagicMock()

            service.upsert_yarn(
                MagicMock(), pattern_id, pattern_yarn_id, **valid_kwargs
            )

        assert mock_yr.upsert.call_args.kwargs["yarn_weight"] is None


class TestGetByPatternId:
    def test_get_yarns_by_pattern(self, service, pattern_id):
        yarns = [MagicMock(), MagicMock()]

        with patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr:
            mock_yr.get_by_pattern_id.return_value = yarns

            result = service.get_by_pattern_id(MagicMock(), pattern_id)

        mock_yr.get_by_pattern_id.assert_called_once()
        assert result is yarns

    def test_get_yarns_returns_empty_list_when_none_found(self, service, pattern_id):
        with patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr:
            mock_yr.get_by_pattern_id.return_value = []

            result = service.get_by_pattern_id(MagicMock(), pattern_id)

        assert result == []


class TestGetCalculations:
    def _make_user_yarn_with_calc(
        self,
        pattern_yarn,
        *,
        calculated_grams_needed=350.0,
        calculated_skeins_needed=2,
        yarn_weight=YarnWeight.DK,
    ):
        uy = MagicMock()
        uy.pattern_yarn = pattern_yarn
        uy.calculated_grams_needed = calculated_grams_needed
        uy.calculated_skeins_needed = calculated_skeins_needed
        uy.yarn_weight = yarn_weight
        uy.label = "My yarn"
        uy.meters_per_unit = 200.0
        uy.grams_per_unit = 100.0
        uy.strands = 1
        return uy

    def test_get_calculations_basic(self, service, pattern_id):
        py_id = uuid.uuid4()
        pattern_yarn = _make_pattern_yarn(
            py_id, grams_needed=[200.0, 350.0], yarn_weight=YarnWeight.DK
        )
        user_yarn = self._make_user_yarn_with_calc(pattern_yarn)
        scaling = _make_scaling(size_label="M", size_position=1)

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr,
        ):
            mock_sr.get_by_pattern_id.return_value = scaling
            mock_yr.get_by_pattern_id.return_value = [user_yarn]

            result = service.get_calculations(MagicMock(), pattern_id)

        assert result["size_label"] == "M"
        entry = result["yarns"][0]
        assert entry["calculated"] is True
        assert entry["weight_warning"] is False
        assert entry["pattern_yarn"]["grams_needed"] == 350.0
        assert entry["result"]["grams_needed"] == 350.0
        assert entry["result"]["skeins_needed"] == 2

    def test_get_calculations_missing_grams_needed(self, service, pattern_id):
        py_id = uuid.uuid4()
        pattern_yarn = _make_pattern_yarn(py_id, grams_needed=None)
        user_yarn = self._make_user_yarn_with_calc(
            pattern_yarn, calculated_grams_needed=None, calculated_skeins_needed=None
        )
        scaling = _make_scaling()

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr,
        ):
            mock_sr.get_by_pattern_id.return_value = scaling
            mock_yr.get_by_pattern_id.return_value = [user_yarn]

            result = service.get_calculations(MagicMock(), pattern_id)

        entry = result["yarns"][0]
        assert entry["calculated"] is False
        assert "does not specify" in entry["message"]

    def test_get_calculations_weight_warning(self, service, pattern_id):
        py_id = uuid.uuid4()
        pattern_yarn = _make_pattern_yarn(
            py_id, grams_needed=[350.0], yarn_weight=YarnWeight.DK
        )
        user_yarn = self._make_user_yarn_with_calc(
            pattern_yarn, yarn_weight=YarnWeight.ARAN
        )
        scaling = _make_scaling(size_position=0)

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr,
        ):
            mock_sr.get_by_pattern_id.return_value = scaling
            mock_yr.get_by_pattern_id.return_value = [user_yarn]

            result = service.get_calculations(MagicMock(), pattern_id)

        assert result["yarns"][0]["weight_warning"] is True

    def test_get_calculations_no_scaling(self, service, pattern_id):
        with patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr:
            mock_sr.get_by_pattern_id.return_value = None

            with pytest.raises(ScalingConfigNotFoundError, match="size and gauge"):
                service.get_calculations(MagicMock(), pattern_id)

    def test_get_calculations_incomplete_pattern_yarn_data(self, service, pattern_id):
        # Lines 147-151: grams_needed exists but meters_per_unit or grams_per_unit is None
        py_id = uuid.uuid4()
        pattern_yarn = _make_pattern_yarn(
            py_id, grams_needed=[300.0], meters_per_unit=None, grams_per_unit=None
        )
        user_yarn = self._make_user_yarn_with_calc(
            pattern_yarn, calculated_grams_needed=None, calculated_skeins_needed=None
        )
        scaling = _make_scaling(size_position=0)

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr,
        ):
            mock_sr.get_by_pattern_id.return_value = scaling
            mock_yr.get_by_pattern_id.return_value = [user_yarn]

            result = service.get_calculations(MagicMock(), pattern_id)

        entry = result["yarns"][0]
        assert entry["calculated"] is False
        assert "incomplete" in entry["message"].lower()

    def test_get_calculations_unavailable_when_data_present_but_no_calc(
        self, service, pattern_id
    ):
        # Line 153: grams_needed exists, pattern yarn data is complete, but no calculated value
        # This path is reached when calculated_grams_needed is None despite data being present
        py_id = uuid.uuid4()
        pattern_yarn = _make_pattern_yarn(
            py_id,
            grams_needed=[300.0],
            meters_per_unit=200.0,
            grams_per_unit=100.0,
        )
        user_yarn = self._make_user_yarn_with_calc(
            pattern_yarn, calculated_grams_needed=None, calculated_skeins_needed=None
        )
        scaling = _make_scaling(size_position=0)

        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr,
        ):
            mock_sr.get_by_pattern_id.return_value = scaling
            mock_yr.get_by_pattern_id.return_value = [user_yarn]

            result = service.get_calculations(MagicMock(), pattern_id)

        entry = result["yarns"][0]
        assert entry["calculated"] is False
        assert entry["message"] == "Calculation is not available."

    def test_get_calculations_no_user_yarns(self, service, pattern_id):
        with (
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr,
        ):
            mock_sr.get_by_pattern_id.return_value = _make_scaling()
            mock_yr.get_by_pattern_id.return_value = []

            with pytest.raises(UserYarnNotFoundError, match="yarn data"):
                service.get_calculations(MagicMock(), pattern_id)
