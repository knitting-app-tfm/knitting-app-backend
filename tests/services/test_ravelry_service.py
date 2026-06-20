import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.ravelry.ravelry_exceptions import RavelryAuthError
from app.services.ravelry.ravelry_service import (
    build_authorize_url,
    create_firebase_custom_token,
    exchange_code_for_token,
    get_ravelry_username,
    login_or_create_user,
    verify_state,
    _sign_timestamp,
)


class TestBuildAuthorizeUrl:
    def test_build_authorize_url_contains_expected_params(self):
        url = build_authorize_url()
        assert "https://www.ravelry.com/oauth2/auth" in url
        assert "client_id=test-ravelry-client-id" in url
        assert "redirect_uri=" in url
        assert "response_type=code" in url
        assert "scope=offline" in url
        assert "state=" in url


class TestVerifyState:
    def test_verify_state_valid(self):
        timestamp_str = str(int(time.time()))
        sig = _sign_timestamp(timestamp_str)
        state = f"{timestamp_str}.{sig}"
        assert verify_state(state) is True

    def test_verify_state_expired(self):
        old_timestamp = str(int(time.time()) - 700)
        sig = _sign_timestamp(old_timestamp)
        state = f"{old_timestamp}.{sig}"
        assert verify_state(state) is False

    def test_verify_state_tampered(self):
        timestamp_str = str(int(time.time()))
        state = f"{timestamp_str}.invalidsignature"
        assert verify_state(state) is False

    def test_verify_state_malformed(self):
        assert verify_state("notvalidatall") is False

    def test_verify_state_empty(self):
        assert verify_state("") is False


class TestExchangeCodeForToken:
    def test_exchange_code_for_token_success(self):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"access_token": "ravelry-token-abc"}

        with patch(
            "app.services.ravelry.ravelry_service.requests.post",
            return_value=mock_response,
        ):
            token = exchange_code_for_token("auth-code-123")

        assert token == "ravelry-token-abc"

    def test_exchange_code_for_token_failure(self):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch(
            "app.services.ravelry.ravelry_service.requests.post",
            return_value=mock_response,
        ):
            with pytest.raises(RavelryAuthError):
                exchange_code_for_token("bad-code")

    def test_exchange_code_for_token_missing_access_token(self):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"token_type": "Bearer"}

        with patch(
            "app.services.ravelry.ravelry_service.requests.post",
            return_value=mock_response,
        ):
            with pytest.raises(RavelryAuthError):
                exchange_code_for_token("code-123")


class TestGetRavelryUsername:
    def test_get_ravelry_username_success(self):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"user": {"username": "knitter42"}}

        with patch(
            "app.services.ravelry.ravelry_service.requests.get",
            return_value=mock_response,
        ):
            username = get_ravelry_username("some-token")

        assert username == "knitter42"

    def test_get_ravelry_username_failure(self):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with patch(
            "app.services.ravelry.ravelry_service.requests.get",
            return_value=mock_response,
        ):
            with pytest.raises(RavelryAuthError):
                get_ravelry_username("bad-token")

    def test_get_ravelry_username_unexpected_shape(self):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {}

        with patch(
            "app.services.ravelry.ravelry_service.requests.get",
            return_value=mock_response,
        ):
            with pytest.raises(RavelryAuthError):
                get_ravelry_username("some-token")


class TestLoginOrCreateUser:
    def test_login_or_create_user_existing_updates_token(self):
        db = MagicMock()
        existing_user = MagicMock()

        with patch("app.services.ravelry.ravelry_service.user_repository") as mock_repo:
            mock_repo.get_by_ravelry_username.return_value = existing_user

            result = login_or_create_user(db, "knitter42", "new-token")

        assert result is existing_user
        assert existing_user.ravelry_token == "new-token"
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(existing_user)

    def test_login_or_create_user_new_creates_user(self):
        db = MagicMock()
        new_user = MagicMock()

        with patch("app.services.ravelry.ravelry_service.user_repository") as mock_repo:
            mock_repo.get_by_ravelry_username.return_value = None
            mock_repo.get_by_username.return_value = None
            mock_repo.create.return_value = new_user

            result = login_or_create_user(db, "knitter42", "token-xyz")

        mock_repo.create.assert_called_once_with(
            db,
            firebase_uid="ravelry_knitter42",
            email=None,
            username="knitter42",
            ravelry_username="knitter42",
            ravelry_token="token-xyz",
        )
        assert result is new_user

    def test_login_or_create_user_username_collision_appends_suffix(self):
        db = MagicMock()
        new_user = MagicMock()
        existing_username_user = MagicMock()

        with patch("app.services.ravelry.ravelry_service.user_repository") as mock_repo:
            mock_repo.get_by_ravelry_username.return_value = None
            mock_repo.get_by_username.side_effect = [existing_username_user, None]
            mock_repo.create.return_value = new_user

            result = login_or_create_user(db, "knitter42", "token-xyz")

        mock_repo.create.assert_called_once_with(
            db,
            firebase_uid="ravelry_knitter42",
            email=None,
            username="knitter42_2",
            ravelry_username="knitter42",
            ravelry_token="token-xyz",
        )
        assert result is new_user


class TestCreateFirebaseCustomToken:
    def test_create_firebase_custom_token(self):
        with patch(
            "app.services.ravelry.ravelry_service.firebase_admin.auth"
        ) as mock_auth:
            mock_auth.create_custom_token.return_value = b"firebase-custom-token"

            token = create_firebase_custom_token("ravelry_knitter42")

        assert token == "firebase-custom-token"
        mock_auth.create_custom_token.assert_called_once_with("ravelry_knitter42")
