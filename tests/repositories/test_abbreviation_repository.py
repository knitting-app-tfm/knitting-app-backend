import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.abbreviation import Abbreviation, AbbreviationCraft, AbbreviationType
from app.repositories.abbreviation import AbbreviationRepository


@pytest.fixture
def db():
    mock = MagicMock(spec=Session)
    query_mock = MagicMock()
    mock.query.return_value = query_mock
    query_mock.filter.return_value = query_mock
    return mock, query_mock


@pytest.fixture
def repo():
    return AbbreviationRepository()


class TestGetAll:
    def test_returns_all_when_no_filters(self, repo, db):
        session, query_mock = db
        expected = [MagicMock(spec=Abbreviation), MagicMock(spec=Abbreviation)]
        query_mock.all.return_value = expected

        result = repo.get_all(session)

        assert result == expected
        query_mock.filter.assert_not_called()

    def test_applies_craft_filter(self, repo, db):
        session, query_mock = db
        query_mock.all.return_value = []

        repo.get_all(session, craft=AbbreviationCraft.KNITTING)

        query_mock.filter.assert_called_once()

    def test_applies_type_filter(self, repo, db):
        session, query_mock = db
        query_mock.all.return_value = []

        repo.get_all(session, type=AbbreviationType.STITCH)

        query_mock.filter.assert_called_once()

    def test_applies_both_filters(self, repo, db):
        session, query_mock = db
        query_mock.all.return_value = []

        repo.get_all(
            session, craft=AbbreviationCraft.CROCHET, type=AbbreviationType.DECREASE
        )

        assert query_mock.filter.call_count == 2

    def test_returns_empty_list_when_no_results(self, repo, db):
        session, query_mock = db
        query_mock.all.return_value = []

        result = repo.get_all(session)

        assert result == []


class TestGetById:
    def test_returns_abbreviation_when_found(self, repo):
        db = MagicMock(spec=Session)
        abbreviation_id = uuid.uuid4()
        mock_abbreviation = MagicMock(spec=Abbreviation)
        db.get.return_value = mock_abbreviation

        result = repo.get_by_id(db, abbreviation_id)

        db.get.assert_called_once_with(Abbreviation, abbreviation_id)
        assert result is mock_abbreviation

    def test_returns_none_when_not_found(self, repo):
        db = MagicMock(spec=Session)
        db.get.return_value = None

        result = repo.get_by_id(db, uuid.uuid4())

        assert result is None
