import uuid
from unittest.mock import MagicMock, patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.core.security import get_current_user

# Minimal app that exercises get_current_user as a dependency
_sec_app = FastAPI()
_sec_app.dependency_overrides[get_db] = lambda: MagicMock()


@_sec_app.get("/protected")
async def _protected_route(user=Depends(get_current_user)):
    return {"id": str(user.id)}


_client = TestClient(_sec_app, raise_server_exceptions=False)


class TestNoAuthHeader:
    def test_returns_401_when_no_authorization_header(self):
        response = _client.get("/protected")
        assert response.status_code == 401


class TestMalformedHeader:
    def test_returns_401_when_scheme_is_not_bearer(self):
        # HTTPBearer rejects non-Bearer schemes with 401
        response = _client.get("/protected", headers={"Authorization": "Token abc123"})
        assert response.status_code == 401

    def test_returns_401_when_no_bearer_prefix(self):
        response = _client.get(
            "/protected", headers={"Authorization": "plain-token-no-prefix"}
        )
        assert response.status_code == 401


class TestInvalidFirebaseToken:
    def test_returns_401_when_firebase_raises_exception(self):
        with patch(
            "app.core.security.verify_firebase_token",
            side_effect=Exception("Invalid Firebase token"),
        ):
            response = _client.get(
                "/protected", headers={"Authorization": "Bearer invalid_token"}
            )
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]


class TestUserNotFound:
    def test_returns_401_when_user_not_in_db(self):
        with (
            patch(
                "app.core.security.verify_firebase_token",
                return_value={"uid": "firebase-uid-999"},
            ),
            patch("app.core.security.user_repository") as mock_repo,
        ):
            mock_repo.get_by_firebase_uid.return_value = None
            response = _client.get(
                "/protected", headers={"Authorization": "Bearer valid_token"}
            )
        assert response.status_code == 401
        assert "not found" in response.json()["detail"].lower()


class TestValidToken:
    def test_returns_200_with_valid_token_and_existing_user(self):
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        with (
            patch(
                "app.core.security.verify_firebase_token",
                return_value={"uid": "firebase-uid-123"},
            ),
            patch("app.core.security.user_repository") as mock_repo,
        ):
            mock_repo.get_by_firebase_uid.return_value = mock_user
            response = _client.get(
                "/protected", headers={"Authorization": "Bearer valid_token"}
            )
        assert response.status_code == 200
        assert response.json()["id"] == str(mock_user.id)


class TestVerifyFirebaseToken:
    def test_delegates_to_firebase_auth_verify_id_token(self):
        with patch(
            "app.core.firebase.auth.verify_id_token", return_value={"uid": "abc"}
        ) as mock_verify:
            result = verify_firebase_token("my-token")
        mock_verify.assert_called_once_with("my-token")
        assert result == {"uid": "abc"}
