import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.pattern import YarnWeight
from app.models.yarn import UserYarn
from app.repositories.yarn import YarnRepository


@pytest.fixture
def repo():
    return YarnRepository()


@pytest.fixture
def db():
    mock = MagicMock(spec=Session)
    query_mock = MagicMock()
    mock.query.return_value = query_mock
    query_mock.filter.return_value = query_mock
    query_mock.join.return_value = query_mock
    return mock, query_mock


class TestUpsert:
    def test_creates_new_yarn_when_none_exists(self, repo, db):
        session, query_mock = db
        pattern_yarn_id = uuid.uuid4()
        query_mock.first.return_value = None

        repo.upsert(
            session,
            pattern_yarn_id=pattern_yarn_id,
            label="Main",
            yarn_weight=YarnWeight.DK,
            meters_per_unit=200.0,
            grams_per_unit=100.0,
            strands=1,
        )

        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert isinstance(added, UserYarn)
        assert added.pattern_yarn_id == pattern_yarn_id
        assert added.label == "Main"
        assert added.yarn_weight == YarnWeight.DK
        assert added.meters_per_unit == 200.0
        assert added.grams_per_unit == 100.0
        assert added.strands == 1
        session.commit.assert_called_once()
        session.refresh.assert_called_once()

    def test_updates_existing_yarn(self, repo, db):
        session, query_mock = db
        existing = MagicMock(spec=UserYarn)
        query_mock.first.return_value = existing

        repo.upsert(
            session,
            pattern_yarn_id=uuid.uuid4(),
            label="Updated",
            yarn_weight=YarnWeight.ARAN,
            meters_per_unit=150.0,
            grams_per_unit=80.0,
            strands=2,
        )

        assert existing.label == "Updated"
        assert existing.yarn_weight == YarnWeight.ARAN
        assert existing.meters_per_unit == 150.0
        assert existing.grams_per_unit == 80.0
        assert existing.strands == 2
        session.add.assert_not_called()
        session.commit.assert_called_once()

    def test_upsert_with_none_weight(self, repo, db):
        session, query_mock = db
        query_mock.first.return_value = None

        repo.upsert(
            session,
            pattern_yarn_id=uuid.uuid4(),
            label=None,
            yarn_weight=None,
            meters_per_unit=100.0,
            grams_per_unit=50.0,
            strands=1,
        )

        added = session.add.call_args[0][0]
        assert added.yarn_weight is None
        assert added.label is None


class TestGetByPatternYarnId:
    def test_returns_yarn_when_found(self, repo, db):
        session, query_mock = db
        pattern_yarn_id = uuid.uuid4()
        expected = MagicMock(spec=UserYarn)
        query_mock.first.return_value = expected

        result = repo.get_by_pattern_yarn_id(session, pattern_yarn_id)

        assert result is expected

    def test_returns_none_when_not_found(self, repo, db):
        session, query_mock = db
        query_mock.first.return_value = None

        result = repo.get_by_pattern_yarn_id(session, uuid.uuid4())

        assert result is None


class TestGetByPatternId:
    def test_returns_all_yarns_for_pattern(self, repo, db):
        session, query_mock = db
        pattern_id = uuid.uuid4()
        yarns = [MagicMock(spec=UserYarn), MagicMock(spec=UserYarn)]
        query_mock.all.return_value = yarns

        result = repo.get_by_pattern_id(session, pattern_id)

        session.query.assert_called_once_with(UserYarn)
        query_mock.join.assert_called_once()
        assert result is yarns

    def test_returns_empty_list_when_no_yarns(self, repo, db):
        session, query_mock = db
        query_mock.all.return_value = []

        result = repo.get_by_pattern_id(session, uuid.uuid4())

        assert result == []
