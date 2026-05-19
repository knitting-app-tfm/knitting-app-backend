import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.pattern import (
    CraftType,
    Pattern,
    PatternSource,
    PatternStatus,
    PatternYarn,
)
from app.repositories.pattern import PatternRepository


@pytest.fixture
def db():
    return MagicMock(spec=Session)


@pytest.fixture
def repo():
    return PatternRepository()


@pytest.fixture
def pattern_kwargs():
    return {
        "title": "Test Pattern",
        "craft": CraftType.KNITTING,
        "source": PatternSource.PDF,
        "status": PatternStatus.IMPORTED,
        "original_file_path": "storage/original/test.pdf",
    }


class TestPatternRepositoryCreate:
    def test_calls_db_operations_in_correct_order(self, repo, db, pattern_kwargs):
        repo.create(db, yarns_data=[], **pattern_kwargs)

        method_names = [c[0] for c in db.method_calls]
        assert method_names.index("flush") > method_names.index("add")
        assert method_names.index("commit") > method_names.index("flush")
        assert method_names.index("refresh") > method_names.index("commit")

    def test_create_without_yarns_adds_only_pattern(self, repo, db, pattern_kwargs):
        result = repo.create(db, yarns_data=[], **pattern_kwargs)

        assert db.add.call_count == 1
        added = db.add.call_args[0][0]
        assert isinstance(added, Pattern)
        assert added.title == "Test Pattern"
        assert isinstance(result, Pattern)

    def test_create_with_yarns_adds_pattern_and_all_yarns(
        self, repo, db, pattern_kwargs
    ):
        yarns_data = [
            {"label": "Main Color", "strands": 1},
            {"label": "Contrast Color", "strands": 2},
        ]

        repo.create(db, yarns_data=yarns_data, **pattern_kwargs)

        assert db.add.call_count == 3  # 1 Pattern + 2 PatternYarn
        added_objects = [c[0][0] for c in db.add.call_args_list]
        pattern = added_objects[0]
        yarns = added_objects[1:]
        assert isinstance(pattern, Pattern)
        assert all(isinstance(y, PatternYarn) for y in yarns)
        assert all(y.pattern_id is pattern.id for y in yarns)


class TestPatternRepositoryGetById:
    def test_delegates_to_db_get(self, repo, db):
        pattern_id = uuid.uuid4()
        repo.get_by_id(db, pattern_id)
        db.get.assert_called_once_with(Pattern, pattern_id)


class TestPatternRepositoryUpdate:
    def test_calls_db_operations_in_correct_order(self, repo, db):
        old_yarn = MagicMock()
        pattern = MagicMock()
        pattern.id = uuid.uuid4()
        pattern.yarns = [old_yarn]

        repo.update(db, pattern, yarns_data=[{"strands": 1}], title="Test")

        method_names = [c[0] for c in db.method_calls]
        assert method_names.index("delete") < method_names.index("flush")
        assert method_names.index("flush") < method_names.index("add")
        assert method_names.index("add") < method_names.index("commit")
        assert method_names.index("commit") < method_names.index("refresh")

    def test_updates_pattern_fields(self, repo, db):
        pattern = MagicMock()
        pattern.yarns = []

        repo.update(db, pattern, yarns_data=[], title="Updated Title", sizes=["M", "L"])

        assert pattern.title == "Updated Title"
        assert pattern.sizes == ["M", "L"]

    def test_deletes_old_yarns_and_creates_new_ones(self, repo, db):
        old_yarn = MagicMock()
        pattern = MagicMock()
        pattern.id = uuid.uuid4()
        pattern.yarns = [old_yarn]

        repo.update(db, pattern, yarns_data=[{"label": "New Yarn", "strands": 2}])

        db.delete.assert_called_once_with(old_yarn)
        assert db.add.call_count == 1
        new_yarn = db.add.call_args[0][0]
        assert isinstance(new_yarn, PatternYarn)
        assert new_yarn.label == "New Yarn"
        assert new_yarn.strands == 2
