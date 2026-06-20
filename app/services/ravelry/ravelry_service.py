import hashlib
import hmac
import time
from urllib.parse import urlencode

import firebase_admin.auth
import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.repositories.user import user_repository
from app.services.ravelry.ravelry_exceptions import RavelryAuthError

_RAVELRY_AUTH_URL = "https://www.ravelry.com/oauth2/auth"
_RAVELRY_TOKEN_URL = "https://www.ravelry.com/oauth2/token"
_RAVELRY_CURRENT_USER_URL = "https://api.ravelry.com/current_user.json"
_STATE_TTL_SECONDS = 600


def _sign_timestamp(timestamp_str: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        timestamp_str.encode(),
        hashlib.sha256,
    ).hexdigest()


def build_authorize_url() -> str:
    timestamp_str = str(int(time.time()))
    sig = _sign_timestamp(timestamp_str)
    state = f"{timestamp_str}.{sig}"
    params = urlencode(
        {
            "client_id": settings.RAVELRY_CLIENT_ID,
            "redirect_uri": settings.RAVELRY_REDIRECT_URI,
            "response_type": "code",
            "scope": "offline",
            "state": state,
        }
    )
    return f"{_RAVELRY_AUTH_URL}?{params}"


def verify_state(state: str) -> bool:
    try:
        timestamp_str, sig = state.split(".", 1)
        timestamp = int(timestamp_str)
    except (ValueError, AttributeError):
        return False

    expected_sig = _sign_timestamp(timestamp_str)
    if not hmac.compare_digest(sig, expected_sig):
        return False

    if time.time() - timestamp > _STATE_TTL_SECONDS:
        return False

    return True


def exchange_code_for_token(code: str) -> str:
    response = requests.post(
        _RAVELRY_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.RAVELRY_REDIRECT_URI,
        },
        auth=(settings.RAVELRY_CLIENT_ID, settings.RAVELRY_CLIENT_SECRET),
    )
    if not response.ok:
        raise RavelryAuthError(
            f"Token exchange failed: {response.status_code} {response.text}"
        )
    data = response.json()
    if "access_token" not in data:
        raise RavelryAuthError("Token exchange response missing access_token")
    return data["access_token"]


def get_ravelry_username(access_token: str) -> str:
    response = requests.get(
        _RAVELRY_CURRENT_USER_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise RavelryAuthError(
            f"Failed to fetch Ravelry user: {response.status_code} {response.text}"
        )
    data = response.json()
    try:
        return data["user"]["username"]
    except (KeyError, TypeError) as exc:
        raise RavelryAuthError("Unexpected response shape from Ravelry API") from exc


def login_or_create_user(db: Session, ravelry_username: str, access_token: str) -> User:
    user = user_repository.get_by_ravelry_username(db, ravelry_username)
    if user is not None:
        user.ravelry_token = access_token
        db.commit()
        db.refresh(user)
        return user

    firebase_uid = f"ravelry_{ravelry_username}"
    username = ravelry_username
    suffix = 2
    while user_repository.get_by_username(db, username) is not None:
        username = f"{ravelry_username}_{suffix}"
        suffix += 1

    return user_repository.create(
        db,
        firebase_uid=firebase_uid,
        email=None,
        username=username,
        ravelry_username=ravelry_username,
        ravelry_token=access_token,
    )


def create_firebase_custom_token(firebase_uid: str) -> str:
    token_bytes = firebase_admin.auth.create_custom_token(firebase_uid)
    return token_bytes.decode("utf-8")
