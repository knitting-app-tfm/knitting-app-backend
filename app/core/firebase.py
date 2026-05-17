from pathlib import Path

import firebase_admin
from firebase_admin import auth, credentials

from app.core.config import settings

_PROJECT_ROOT = Path(__file__).parent.parent.parent

_path = Path(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
if not _path.is_absolute():
    _path = _PROJECT_ROOT / _path

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(credentials.Certificate(str(_path)))


def verify_firebase_token(token: str) -> dict:
    return auth.verify_id_token(token)
