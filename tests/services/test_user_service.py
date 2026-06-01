from unittest.mock import MagicMock, patch

import pytest
from firebase_admin.auth import EmailAlreadyExistsError

from app.services.user import UserAlreadyExistsError, UsernameTakenError, UserService


@pytest.fixture
def service():
    return UserService()


_DECODED_TOKEN = {"uid": "firebase-uid-123", "email": "user@example.com"}


class TestRegister:
    def test_creates_user_with_decoded_token_data(self, service):
        db = MagicMock()
        mock_user = MagicMock()

        with (
            patch(
                "app.services.user.verify_firebase_token", return_value=_DECODED_TOKEN
            ),
            patch("app.services.user.user_repository") as mock_repo,
        ):
            mock_repo.get_by_firebase_uid.return_value = None
            mock_repo.get_by_username.return_value = None
            mock_repo.create.return_value = mock_user

            result = service.register(db, "raw-token", "alice")

        mock_repo.create.assert_called_once_with(
            db,
            firebase_uid="firebase-uid-123",
            email="user@example.com",
            username="alice",
        )
        assert result is mock_user

    def test_raises_if_user_already_exists(self, service):
        db = MagicMock()

        with (
            patch(
                "app.services.user.verify_firebase_token", return_value=_DECODED_TOKEN
            ),
            patch("app.services.user.user_repository") as mock_repo,
        ):
            mock_repo.get_by_firebase_uid.return_value = MagicMock()

            with pytest.raises(UserAlreadyExistsError):
                service.register(db, "raw-token", "alice")

        mock_repo.create.assert_not_called()

    def test_raises_if_username_already_taken(self, service):
        db = MagicMock()

        with (
            patch(
                "app.services.user.verify_firebase_token", return_value=_DECODED_TOKEN
            ),
            patch("app.services.user.user_repository") as mock_repo,
        ):
            mock_repo.get_by_firebase_uid.return_value = None
            mock_repo.get_by_username.return_value = MagicMock()

            with pytest.raises(UsernameTakenError):
                service.register(db, "raw-token", "alice")

        mock_repo.create.assert_not_called()

    def test_passes_none_email_when_missing_from_token(self, service):
        db = MagicMock()
        decoded_no_email = {"uid": "firebase-uid-456"}

        with (
            patch(
                "app.services.user.verify_firebase_token", return_value=decoded_no_email
            ),
            patch("app.services.user.user_repository") as mock_repo,
        ):
            mock_repo.get_by_firebase_uid.return_value = None
            mock_repo.get_by_username.return_value = None
            mock_repo.create.return_value = MagicMock()

            service.register(db, "raw-token", "bob")

        mock_repo.create.assert_called_once_with(
            db,
            firebase_uid="firebase-uid-456",
            email=None,
            username="bob",
        )

    def test_propagates_firebase_verification_error(self, service):
        db = MagicMock()

        with patch(
            "app.services.user.verify_firebase_token",
            side_effect=Exception("invalid token"),
        ):
            with pytest.raises(Exception, match="invalid token"):
                service.register(db, "bad-token", "alice")


class TestRegisterWithCredentials:
    def test_creates_user_when_valid(self, service):
        db = MagicMock()
        mock_user = MagicMock()

        with (
            patch("app.services.user.user_repository") as mock_repo,
            patch(
                "app.services.user.create_firebase_user",
                return_value=("uid-123", "user@example.com"),
            ),
        ):
            mock_repo.get_by_username.return_value = None
            mock_repo.create.return_value = mock_user

            result = service.register_with_credentials(
                db, "user@example.com", "pass123", "alice"
            )

        mock_repo.create.assert_called_once_with(
            db, firebase_uid="uid-123", email="user@example.com", username="alice"
        )
        assert result is mock_user

    def test_raises_username_taken_before_calling_firebase(self, service):
        db = MagicMock()

        with (
            patch("app.services.user.user_repository") as mock_repo,
            patch("app.services.user.create_firebase_user") as mock_firebase,
        ):
            mock_repo.get_by_username.return_value = MagicMock()

            with pytest.raises(UsernameTakenError):
                service.register_with_credentials(
                    db, "user@example.com", "pass123", "alice"
                )

        mock_firebase.assert_not_called()
        mock_repo.create.assert_not_called()

    def test_raises_user_already_exists_when_firebase_email_taken(self, service):
        db = MagicMock()

        with (
            patch("app.services.user.user_repository") as mock_repo,
            patch(
                "app.services.user.create_firebase_user",
                side_effect=EmailAlreadyExistsError(
                    "email exists", cause=None, http_response=None
                ),
            ),
        ):
            mock_repo.get_by_username.return_value = None

            with pytest.raises(UserAlreadyExistsError):
                service.register_with_credentials(
                    db, "existing@example.com", "pass123", "alice"
                )

        mock_repo.create.assert_not_called()
