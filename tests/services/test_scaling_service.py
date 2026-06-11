import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.scaling import (
    InvalidGaugeError,
    InvalidSizeLabelError,
    InvalidSizePositionError,
    PatternNotFoundError,
    ScalingService,
)


@pytest.fixture
def service():
    return ScalingService()


@pytest.fixture
def pattern_with_sizes():
    pattern = MagicMock()
    pattern.id = uuid.uuid4()
    pattern.sizes = ["XS", "S", "M", "L"]
    return pattern


@pytest.fixture
def one_size_pattern():
    pattern = MagicMock()
    pattern.id = uuid.uuid4()
    pattern.sizes = []
    return pattern


@pytest.fixture
def valid_gauge():
    return {
        "gauge_stitches": 20.0,
        "gauge_rows": 28.0,
        "gauge_size": 10.0,
        "gauge_unit": "CM",
        "needle_size": "4mm",
    }


class TestUpsertSize:
    def test_upsert_size_valid(self, service, pattern_with_sizes, valid_gauge):
        db = MagicMock()
        mock_scaling = MagicMock()

        with (
            patch(
                "app.services.scaling.scaling_service.pattern_repository"
            ) as mock_pattern_repo,
            patch(
                "app.services.scaling.scaling_service.scaling_repository"
            ) as mock_scaling_repo,
        ):
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes
            mock_scaling_repo.upsert.return_value = mock_scaling

            result = service.upsert_size(
                db,
                pattern_with_sizes.id,
                size_label="M",
                size_position=2,
                **valid_gauge,
            )

        assert result is mock_scaling

    def test_upsert_size_invalid_label(self, service, pattern_with_sizes, valid_gauge):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(InvalidSizeLabelError):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="XXL",
                    size_position=0,
                    **valid_gauge,
                )

    def test_upsert_size_invalid_position(
        self, service, pattern_with_sizes, valid_gauge
    ):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(InvalidSizePositionError):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="S",
                    size_position=0,
                    **valid_gauge,
                )

    def test_upsert_size_pattern_not_found(self, service, valid_gauge):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = None

            with pytest.raises(PatternNotFoundError):
                service.upsert_size(
                    db, uuid.uuid4(), size_label="S", size_position=1, **valid_gauge
                )

    def test_upsert_size_one_size_uses_canonical_values(
        self, service, one_size_pattern, valid_gauge
    ):
        db = MagicMock()
        mock_scaling = MagicMock()

        with (
            patch(
                "app.services.scaling.scaling_service.pattern_repository"
            ) as mock_pattern_repo,
            patch(
                "app.services.scaling.scaling_service.scaling_repository"
            ) as mock_scaling_repo,
        ):
            mock_pattern_repo.get_by_id.return_value = one_size_pattern
            mock_scaling_repo.upsert.return_value = mock_scaling

            result = service.upsert_size(
                db,
                one_size_pattern.id,
                size_label="anything",
                size_position=99,
                **valid_gauge,
            )

        assert result is mock_scaling

    def test_upsert_size_one_size_none_sizes_uses_canonical_values(
        self, service, valid_gauge
    ):
        db = MagicMock()
        pattern = MagicMock()
        pattern.id = uuid.uuid4()
        pattern.sizes = None
        mock_scaling = MagicMock()

        with (
            patch(
                "app.services.scaling.scaling_service.pattern_repository"
            ) as mock_pattern_repo,
            patch(
                "app.services.scaling.scaling_service.scaling_repository"
            ) as mock_scaling_repo,
        ):
            mock_pattern_repo.get_by_id.return_value = pattern
            mock_scaling_repo.upsert.return_value = mock_scaling

            service.upsert_size(
                db, pattern.id, size_label="S", size_position=1, **valid_gauge
            )

        mock_scaling_repo.upsert.assert_called_once()
        call_args = mock_scaling_repo.upsert.call_args
        assert call_args.args[2] == "One size"
        assert call_args.args[3] == 0


class TestUpsertGauge:
    def test_upsert_gauge_valid(self, service, pattern_with_sizes):
        db = MagicMock()
        mock_scaling = MagicMock()

        with (
            patch(
                "app.services.scaling.scaling_service.pattern_repository"
            ) as mock_pattern_repo,
            patch(
                "app.services.scaling.scaling_service.scaling_repository"
            ) as mock_scaling_repo,
        ):
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes
            mock_scaling_repo.upsert.return_value = mock_scaling

            result = service.upsert_size(
                db,
                pattern_with_sizes.id,
                size_label="M",
                size_position=2,
                gauge_stitches=20.0,
                gauge_rows=28.0,
                gauge_size=10.0,
                gauge_unit="CM",
                needle_size="4mm",
            )

        assert result is mock_scaling

    def test_upsert_gauge_stitches_decimal(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(InvalidGaugeError):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="M",
                    size_position=2,
                    gauge_stitches=20.5,
                    gauge_rows=28.0,
                    gauge_size=10.0,
                    gauge_unit="CM",
                    needle_size=None,
                )

    def test_upsert_gauge_rows_decimal(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(InvalidGaugeError):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="M",
                    size_position=2,
                    gauge_stitches=20.0,
                    gauge_rows=28.5,
                    gauge_size=10.0,
                    gauge_unit="CM",
                    needle_size=None,
                )

    def test_upsert_gauge_zero_value(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(
                InvalidGaugeError, match="Value must be greater than zero"
            ):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="M",
                    size_position=2,
                    gauge_stitches=0.0,
                    gauge_rows=28.0,
                    gauge_size=10.0,
                    gauge_unit="CM",
                    needle_size=None,
                )

    def test_upsert_gauge_negative_value(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(
                InvalidGaugeError, match="Value must be greater than zero"
            ):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="M",
                    size_position=2,
                    gauge_stitches=20.0,
                    gauge_rows=28.0,
                    gauge_size=-5.0,
                    gauge_unit="CM",
                    needle_size=None,
                )

    def test_upsert_gauge_invalid_unit(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(InvalidGaugeError):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="M",
                    size_position=2,
                    gauge_stitches=20.0,
                    gauge_rows=28.0,
                    gauge_size=10.0,
                    gauge_unit="YARDS",
                    needle_size=None,
                )
