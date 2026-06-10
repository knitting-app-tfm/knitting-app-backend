import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.scaling import (
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


class TestUpsertSize:
    def test_upsert_size_valid(self, service, pattern_with_sizes):
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
                db, pattern_with_sizes.id, size_label="M", size_position=2
            )

        mock_scaling_repo.upsert.assert_called_once_with(
            db, pattern_with_sizes.id, "M", 2
        )
        assert result is mock_scaling

    def test_upsert_size_invalid_label(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(InvalidSizeLabelError):
                service.upsert_size(
                    db, pattern_with_sizes.id, size_label="XXL", size_position=0
                )

    def test_upsert_size_invalid_position(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(InvalidSizePositionError):
                service.upsert_size(
                    db, pattern_with_sizes.id, size_label="S", size_position=0
                )

    def test_upsert_size_pattern_not_found(self, service):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = None

            with pytest.raises(PatternNotFoundError):
                service.upsert_size(db, uuid.uuid4(), size_label="S", size_position=1)
