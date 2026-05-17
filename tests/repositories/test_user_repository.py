from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user import UserRepository


class TestUserRepositoryCreate:
    def test_calls_db_operations_in_correct_order(self):
        db = MagicMock(spec=Session)
        repo = UserRepository()

        repo.create(db, firebase_uid="uid123", email="a@b.com", username="alice")

        method_names = [c[0] for c in db.method_calls]
        assert method_names.index("add") < method_names.index("commit")
        assert method_names.index("commit") < method_names.index("refresh")

    def test_create_sets_correct_fields(self):
        db = MagicMock(spec=Session)
        repo = UserRepository()

        repo.create(db, firebase_uid="uid123", email="a@b.com", username="alice")

        added_user: User = db.add.call_args[0][0]
        assert added_user.firebase_uid == "uid123"
        assert added_user.email == "a@b.com"
        assert added_user.username == "alice"

    def test_create_returns_refreshed_user(self):
        db = MagicMock(spec=Session)
        repo = UserRepository()
        db.refresh.side_effect = lambda u: None

        repo.create(db, firebase_uid="uid123", email=None, username="bob")

        db.refresh.assert_called_once()


class TestUserRepositoryGetByFirebaseUid:
    def test_returns_user_when_found(self):
        db = MagicMock(spec=Session)
        repo = UserRepository()
        mock_user = MagicMock(spec=User)
        db.query.return_value.filter.return_value.first.return_value = mock_user

        result = repo.get_by_firebase_uid(db, "uid123")

        assert result is mock_user

    def test_returns_none_when_not_found(self):
        db = MagicMock(spec=Session)
        repo = UserRepository()
        db.query.return_value.filter.return_value.first.return_value = None

        result = repo.get_by_firebase_uid(db, "uid_unknown")

        assert result is None


class TestUserRepositoryGetByUsername:
    def test_returns_user_when_found(self):
        db = MagicMock(spec=Session)
        repo = UserRepository()
        mock_user = MagicMock(spec=User)
        db.query.return_value.filter.return_value.first.return_value = mock_user

        result = repo.get_by_username(db, "alice")

        assert result is mock_user

    def test_returns_none_when_not_found(self):
        db = MagicMock(spec=Session)
        repo = UserRepository()
        db.query.return_value.filter.return_value.first.return_value = None

        result = repo.get_by_username(db, "unknown_user")

        assert result is None
