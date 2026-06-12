import json
from pathlib import Path

from app.core.config import settings


def save_file(content: bytes | str, subdir: str, file_uuid: str, suffix: str) -> str:
    path = Path(settings.STORAGE_BASE_PATH) / subdir / f"{file_uuid}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return f"storage/{subdir}/{file_uuid}{suffix}"


def read_parsed_json(stored_path: str) -> dict:
    try:
        path = Path(settings.STORAGE_BASE_PATH) / stored_path.removeprefix("storage/")
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_tokens_file(stored_path: str) -> list[dict]:
    try:
        path = Path(settings.STORAGE_BASE_PATH) / stored_path.removeprefix("storage/")
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def delete_file(stored_path: str) -> None:
    try:
        path = Path(settings.STORAGE_BASE_PATH) / stored_path.removeprefix("storage/")
        path.unlink(missing_ok=True)
    except Exception:
        pass
