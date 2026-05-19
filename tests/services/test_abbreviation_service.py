import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.abbreviation import Abbreviation, AbbreviationCraft, AbbreviationType
from app.services.abbreviation import AbbreviationService


@pytest.fixture
def service():
    return AbbreviationService()


class TestGetAll:
    def test_returns_repository_result(self, service):
        db = MagicMock()
        expected = [MagicMock(spec=Abbreviation)]

        with patch("app.services.abbreviation.abbreviation_repository") as mock_repo:
            mock_repo.get_all.return_value = expected

            result = service.get_all(db)

        assert result is expected
        mock_repo.get_all.assert_called_once_with(db, craft=None, type=None)

    def test_passes_craft_filter_to_repository(self, service):
        db = MagicMock()

        with patch("app.services.abbreviation.abbreviation_repository") as mock_repo:
            mock_repo.get_all.return_value = []

            service.get_all(db, craft=AbbreviationCraft.KNITTING)

        mock_repo.get_all.assert_called_once_with(
            db, craft=AbbreviationCraft.KNITTING, type=None
        )

    def test_passes_type_filter_to_repository(self, service):
        db = MagicMock()

        with patch("app.services.abbreviation.abbreviation_repository") as mock_repo:
            mock_repo.get_all.return_value = []

            service.get_all(db, type=AbbreviationType.STITCH)

        mock_repo.get_all.assert_called_once_with(
            db, craft=None, type=AbbreviationType.STITCH
        )

    def test_passes_both_filters_to_repository(self, service):
        db = MagicMock()

        with patch("app.services.abbreviation.abbreviation_repository") as mock_repo:
            mock_repo.get_all.return_value = []

            service.get_all(
                db, craft=AbbreviationCraft.CROCHET, type=AbbreviationType.DECREASE
            )

        mock_repo.get_all.assert_called_once_with(
            db, craft=AbbreviationCraft.CROCHET, type=AbbreviationType.DECREASE
        )


class TestGetById:
    def test_returns_abbreviation_when_found(self, service):
        db = MagicMock()
        abbreviation_id = uuid.uuid4()
        mock_abbreviation = MagicMock(spec=Abbreviation)

        with patch("app.services.abbreviation.abbreviation_repository") as mock_repo:
            mock_repo.get_by_id.return_value = mock_abbreviation

            result = service.get_by_id(db, abbreviation_id)

        assert result is mock_abbreviation
        mock_repo.get_by_id.assert_called_once_with(db, abbreviation_id)

    def test_raises_404_when_not_found(self, service):
        db = MagicMock()

        with patch("app.services.abbreviation.abbreviation_repository") as mock_repo:
            mock_repo.get_by_id.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                service.get_by_id(db, uuid.uuid4())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Abbreviation not found"
