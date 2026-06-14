import datetime
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.schemas.auth import FirebaseRegisterRequest
from app.services.user import UserAlreadyExistsError, UsernameTakenError


def _mock_db():
    return MagicMock()


def _make_user():
    u = MagicMock()
    u.id = uuid.uuid4()
    u.firebase_uid = "firebase-uid-123"
    u.email = "test@test.com"
    u.username = "testuser"
    u.created_at = datetime.datetime.now()
    return u


def _mock_current_user():
    return _make_user()


@pytest.fixture(autouse=True)
def override_deps():
    app.dependency_overrides[get_db] = _mock_db
    app.dependency_overrides[get_current_user] = _mock_current_user
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)


class TestFirebaseRegister:
    def test_returns_201_on_success(self):
        user = _make_user()
        with patch("app.routers.auth.user_service") as mock_svc:
            mock_svc.register_with_credentials.return_value = user
            response = client.post(
                "/auth/firebase/register",
                json={"email": "new@test.com", "password": "secret123", "username": "newuser"},
            )
        assert response.status_code == 201
        assert response.json()["username"] == "testuser"

    def test_returns_409_on_duplicate_email(self):
        with patch("app.routers.auth.user_service") as mock_svc:
            mock_svc.register_with_credentials.side_effect = UserAlreadyExistsError(
                "Email already registered"
            )
            response = client.post(
                "/auth/firebase/register",
                json={"email": "existing@test.com", "password": "secret123", "username": "u"},
            )
        assert response.status_code == 409

    def test_returns_409_on_taken_username(self):
        with patch("app.routers.auth.user_service") as mock_svc:
            mock_svc.register_with_credentials.side_effect = UsernameTakenError(
                "Username already taken"
            )
            response = client.post(
                "/auth/firebase/register",
                json={"email": "new@test.com", "password": "secret123", "username": "taken"},
            )
        assert response.status_code == 409


class TestGetMe:
    def test_returns_200_when_authenticated(self):
        response = client.get("/auth/me")
        assert response.status_code == 200
        assert response.json()["username"] == "testuser"
        assert response.json()["email"] == "test@test.com"

    def test_returns_401_when_no_auth_token(self):
        app.dependency_overrides.pop(get_current_user, None)
        try:
            response = client.get("/auth/me")
        finally:
            app.dependency_overrides[get_current_user] = _mock_current_user
        assert response.status_code == 401


class TestFirebaseRegisterRequestSchema:
    def test_raises_validation_error_for_invalid_email(self):
        with pytest.raises(ValidationError) as exc_info:
            FirebaseRegisterRequest(email="not-an-email", password="secret123", username="user")
        errors = exc_info.value.errors()
        assert any("email" in str(e).lower() or "invalid" in str(e).lower() for e in errors)

    def test_accepts_valid_email(self):
        req = FirebaseRegisterRequest(email="valid@example.com", password="secret123", username="user")
        assert req.email == "valid@example.com"


class TestRegister:
    def test_returns_201_on_success(self):
        user = _make_user()
        with patch("app.routers.auth.user_service") as mock_svc:
            mock_svc.register.return_value = user
            response = client.post(
                "/auth/register",
                json={"firebase_token": "token123", "username": "newuser"},
            )
        assert response.status_code == 201
        assert response.json()["firebase_uid"] == "firebase-uid-123"

    def test_returns_409_on_duplicate_email(self):
        with patch("app.routers.auth.user_service") as mock_svc:
            mock_svc.register.side_effect = UserAlreadyExistsError("Email already registered")
            response = client.post(
                "/auth/register",
                json={"firebase_token": "token123", "username": "newuser"},
            )
        assert response.status_code == 409

    def test_returns_409_on_taken_username(self):
        with patch("app.routers.auth.user_service") as mock_svc:
            mock_svc.register.side_effect = UsernameTakenError("Username already taken")
            response = client.post(
                "/auth/register",
                json={"firebase_token": "token123", "username": "taken"},
            )
        assert response.status_code == 409
