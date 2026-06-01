from unittest.mock import MagicMock, patch

import pytest
from firebase_admin.auth import EmailAlreadyExistsError

from app.services.firebase_auth import create_firebase_user


def _mock_user_record(uid: str, email: str | None) -> MagicMock:
    record = MagicMock()
    record.uid = uid
    record.email = email
    return record


class TestCreateFirebaseUser:
    def test_returns_uid_and_email_on_success(self):
        mock_record = _mock_user_record("firebase-uid-123", "user@example.com")

        with patch(
            "app.services.firebase_auth.auth.create_user", return_value=mock_record
        ):
            uid, email = create_firebase_user("user@example.com", "password123")

        assert uid == "firebase-uid-123"
        assert email == "user@example.com"

    def test_returns_none_email_when_firebase_has_no_email(self):
        mock_record = _mock_user_record("firebase-uid-456", None)

        with patch(
            "app.services.firebase_auth.auth.create_user", return_value=mock_record
        ):
            uid, email = create_firebase_user("user@example.com", "password123")

        assert uid == "firebase-uid-456"
        assert email is None

    def test_propagates_email_already_exists_error(self):
        with patch(
            "app.services.firebase_auth.auth.create_user",
            side_effect=EmailAlreadyExistsError(
                "Email already exists", cause=None, http_response=None
            ),
        ):
            with pytest.raises(EmailAlreadyExistsError):
                create_firebase_user("existing@example.com", "password123")
