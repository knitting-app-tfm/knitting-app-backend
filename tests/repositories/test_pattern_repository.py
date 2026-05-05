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
        assert all(y.pattern_id == pattern.id for y in yarns)
