import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.pattern import YarnWeight
from app.services.scaling.scaling_exceptions import ScalingConfigNotFoundError
from app.services.yarn import (
    InvalidYarnDataError,
    PatternYarnNotFoundError,
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
        assert call_kwargs["pattern_yarn_id"] == pattern_yarn_id
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
