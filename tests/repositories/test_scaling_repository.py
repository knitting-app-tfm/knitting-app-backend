import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.scaling import UserScaling
from app.repositories.scaling import ScalingRepository


@pytest.fixture
def db():
    mock = MagicMock(spec=Session)
    query_mock = MagicMock()
    mock.query.return_value = query_mock
    query_mock.filter.return_value = query_mock
    return mock, query_mock


@pytest.fixture
def repo():
    return ScalingRepository()


class TestUpsert:
    def test_creates_new_scaling_when_none_exists(self, repo, db):
        session, query_mock = db
        pattern_id = uuid.uuid4()
        query_mock.first.return_value = None

        repo.upsert(session, pattern_id, "M", 2)

        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert isinstance(added, UserScaling)
        assert added.pattern_id == pattern_id
        assert added.size_label == "M"
        assert added.size_position == 2

    def test_updates_existing_scaling_without_adding(self, repo, db):
        session, query_mock = db
        existing = MagicMock(spec=UserScaling)
        query_mock.first.return_value = existing

        repo.upsert(session, uuid.uuid4(), "L", 3)

        session.add.assert_not_called()
        assert existing.size_label == "L"
        assert existing.size_position == 3

    def test_commits_and_refreshes(self, repo, db):
        session, query_mock = db
        query_mock.first.return_value = None

        repo.upsert(session, uuid.uuid4(), "S", 1)

        session.commit.assert_called_once()
        session.refresh.assert_called_once()

    def test_returns_scaling(self, repo, db):
        session, query_mock = db
        query_mock.first.return_value = None

        result = repo.upsert(session, uuid.uuid4(), "XS", 0)

        assert isinstance(result, UserScaling)


class TestGetByPatternId:
    def test_returns_scaling_when_found(self, repo, db):
        session, query_mock = db
        pattern_id = uuid.uuid4()
        expected = MagicMock(spec=UserScaling)
        query_mock.first.return_value = expected

        result = repo.get_by_pattern_id(session, pattern_id)

        session.query.assert_called_once_with(UserScaling)
        assert result is expected

    def test_returns_none_when_not_found(self, repo, db):
        session, query_mock = db
        query_mock.first.return_value = None

        result = repo.get_by_pattern_id(session, uuid.uuid4())

        assert result is None
