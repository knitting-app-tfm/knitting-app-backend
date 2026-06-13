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


# ---------------------------------------------------------------------------
# Helpers for calculate_yarn tests
# ---------------------------------------------------------------------------


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


def _make_user_yarn(
    pattern_yarn_id,
    *,
    meters_per_unit=180.0,
    grams_per_unit=100.0,
    strands=1,
    yarn_weight=YarnWeight.DK,
    label="My yarn",
):
    uy = MagicMock()
    uy.pattern_yarn_id = pattern_yarn_id
    uy.meters_per_unit = meters_per_unit
    uy.grams_per_unit = grams_per_unit
    uy.strands = strands
    uy.yarn_weight = yarn_weight
    uy.label = label
    return uy


def _make_scaling(size_label="M", size_position=1):
    s = MagicMock()
    s.size_label = size_label
    s.size_position = size_position
    return s


class TestCalculateYarn:
    def _run(self, service, pattern_id, pattern, scaling, user_yarns, factors):
        with (
            patch("app.services.yarn.yarn_service.pattern_repository") as mock_pr,
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr,
            patch(
                "app.services.yarn.yarn_service._calculate_factors",
                return_value=factors,
            ),
        ):
            mock_pr.get_by_id.return_value = pattern
            mock_sr.get_by_pattern_id.return_value = scaling
            mock_yr.get_by_pattern_id.return_value = user_yarns
            return service.calculate_yarn(MagicMock(), pattern_id)

    def test_calculate_yarn_basic(self, service, pattern_id):
        py_id = uuid.uuid4()
        pattern_yarn = _make_pattern_yarn(
            py_id,
            grams_needed=[200.0, 350.0, 450.0],
            meters_per_unit=200.0,
            grams_per_unit=100.0,
            strands=1,
        )
        pattern = MagicMock()
        pattern.yarns = [pattern_yarn]
        scaling = _make_scaling(size_label="M", size_position=1)
        user_yarn = _make_user_yarn(
            py_id, meters_per_unit=200.0, grams_per_unit=100.0, strands=1
        )

        result = self._run(
            service, pattern_id, pattern, scaling, [user_yarn], (1.0, 1.0)
        )

        assert result["size_label"] == "M"
        entry = result["yarns"][0]
        assert entry["calculated"] is True
        assert entry["weight_warning"] is False
        assert entry["pattern_yarn"]["grams_needed"] == 350.0
        assert entry["result"]["grams_needed"] == 350.0
        assert entry["result"]["skeins_needed"] == 4  # ceil(700/200) = 4

    def test_calculate_yarn_with_row_gauge(self, service, pattern_id):
        py_id = uuid.uuid4()
        pattern_yarn = _make_pattern_yarn(
            py_id,
            grams_needed=[200.0, 350.0],
            meters_per_unit=200.0,
            grams_per_unit=100.0,
            strands=1,
        )
        pattern = MagicMock()
        pattern.yarns = [pattern_yarn]
        scaling = _make_scaling(size_position=1)
        user_yarn = _make_user_yarn(
            py_id, meters_per_unit=200.0, grams_per_unit=100.0, strands=1
        )

        # area_factor = 1.2 * 0.9 = 1.08
        result = self._run(
            service, pattern_id, pattern, scaling, [user_yarn], (1.2, 0.9)
        )

        entry = result["yarns"][0]
        assert entry["calculated"] is True
        # total_meters_pattern = 350/100*200 = 700; scaled = 700*1.08 = 756; grams = 756/200*100 = 378
        assert entry["result"]["grams_needed"] == pytest.approx(378.0, abs=0.5)
        assert entry["result"]["skeins_needed"] == 4  # ceil(756/200) = 4

    def test_calculate_yarn_without_row_gauge(self, service, pattern_id):
        py_id = uuid.uuid4()
        pattern_yarn = _make_pattern_yarn(
            py_id,
            grams_needed=[200.0, 350.0],
            meters_per_unit=200.0,
            grams_per_unit=100.0,
            strands=1,
        )
        pattern = MagicMock()
        pattern.yarns = [pattern_yarn]
        scaling = _make_scaling(size_position=1)
        user_yarn = _make_user_yarn(
            py_id, meters_per_unit=200.0, grams_per_unit=100.0, strands=1
        )

        # factor_rows is None → area_factor = 1.2 * 1.2 = 1.44
        result = self._run(
            service, pattern_id, pattern, scaling, [user_yarn], (1.2, None)
        )

        entry = result["yarns"][0]
        assert entry["calculated"] is True
        # total_meters_pattern = 700; scaled = 700*1.44 = 1008; grams = 1008/200*100 = 504
        assert entry["result"]["grams_needed"] == pytest.approx(504.0, abs=0.5)
        assert entry["result"]["skeins_needed"] == 6  # ceil(1008/200) = 6

    def test_calculate_yarn_different_strands(self, service, pattern_id):
        py_id = uuid.uuid4()
        pattern_yarn = _make_pattern_yarn(
            py_id,
            grams_needed=[350.0],
            meters_per_unit=200.0,
            grams_per_unit=100.0,
            strands=2,
        )
        pattern = MagicMock()
        pattern.yarns = [pattern_yarn]
        scaling = _make_scaling(size_position=0)
        # user knits with 1 strand instead of 2
        user_yarn = _make_user_yarn(
            py_id, meters_per_unit=200.0, grams_per_unit=100.0, strands=1
        )

        result = self._run(
            service, pattern_id, pattern, scaling, [user_yarn], (1.0, 1.0)
        )

        entry = result["yarns"][0]
        assert entry["calculated"] is True
        # total_meters_pattern = 350/100*200 = 700; scaled = 700; meters_per_strand = 700/2 = 350
        # total_meters_user = 350*1 = 350; grams = 350/200*100 = 175
        assert entry["result"]["grams_needed"] == pytest.approx(175.0, abs=0.5)
        assert entry["result"]["skeins_needed"] == 2  # ceil(350/200) = 2

    def test_calculate_yarn_weight_warning(self, service, pattern_id):
        py_id = uuid.uuid4()
        pattern_yarn = _make_pattern_yarn(
            py_id, grams_needed=[350.0], yarn_weight=YarnWeight.DK
        )
        pattern = MagicMock()
        pattern.yarns = [pattern_yarn]
        scaling = _make_scaling(size_position=0)
        user_yarn = _make_user_yarn(py_id, yarn_weight=YarnWeight.ARAN)

        result = self._run(
            service, pattern_id, pattern, scaling, [user_yarn], (1.0, 1.0)
        )

        assert result["yarns"][0]["weight_warning"] is True

    def test_calculate_yarn_missing_grams_needed(self, service, pattern_id):
        py_id = uuid.uuid4()
        pattern_yarn = _make_pattern_yarn(py_id, grams_needed=None)
        pattern = MagicMock()
        pattern.yarns = [pattern_yarn]
        scaling = _make_scaling()
        user_yarn = _make_user_yarn(py_id)

        result = self._run(
            service, pattern_id, pattern, scaling, [user_yarn], (1.0, 1.0)
        )

        entry = result["yarns"][0]
        assert entry["calculated"] is False
        assert "does not specify" in entry["message"]

    def test_calculate_yarn_no_user_yarn_for_pattern_yarn(self, service, pattern_id):
        py_id = uuid.uuid4()
        pattern_yarn = _make_pattern_yarn(py_id, grams_needed=[350.0])
        pattern = MagicMock()
        pattern.yarns = [pattern_yarn]
        scaling = _make_scaling()
        # user_yarn belongs to a different pattern_yarn_id
        other_user_yarn = _make_user_yarn(uuid.uuid4())

        result = self._run(
            service, pattern_id, pattern, scaling, [other_user_yarn], (1.0, 1.0)
        )

        entry = result["yarns"][0]
        assert entry["calculated"] is False
        assert "No yarn data provided" in entry["message"]

    def test_calculate_yarn_no_scaling(self, service, pattern_id):
        pattern = MagicMock()

        with (
            patch("app.services.yarn.yarn_service.pattern_repository") as mock_pr,
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
        ):
            mock_pr.get_by_id.return_value = pattern
            mock_sr.get_by_pattern_id.return_value = None

            with pytest.raises(ScalingConfigNotFoundError, match="size and gauge"):
                service.calculate_yarn(MagicMock(), pattern_id)

    def test_calculate_yarn_no_user_yarns_at_all(self, service, pattern_id):
        pattern = MagicMock()
        scaling = _make_scaling()

        with (
            patch("app.services.yarn.yarn_service.pattern_repository") as mock_pr,
            patch("app.services.yarn.yarn_service.scaling_repository") as mock_sr,
            patch("app.services.yarn.yarn_service.yarn_repository") as mock_yr,
        ):
            mock_pr.get_by_id.return_value = pattern
            mock_sr.get_by_pattern_id.return_value = scaling
            mock_yr.get_by_pattern_id.return_value = []

            with pytest.raises(UserYarnNotFoundError, match="yarn data"):
                service.calculate_yarn(MagicMock(), pattern_id)
