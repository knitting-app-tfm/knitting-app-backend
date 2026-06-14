import datetime
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.pattern import CraftType, GaugeUnit, PatternSource, PatternStatus
from app.services.pattern import (
    EmptyTextError,
    EmptyTitleError,
    FileTooLargeError,
    InvalidFileTypeError,
    PatternNotConfirmedError,
)


def _mock_db():
    return MagicMock()


def _make_mock_user():
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = "test@test.com"
    u.username = "testuser"
    return u


_MOCK_USER = _make_mock_user()


def _mock_current_user():
    return _MOCK_USER


@pytest.fixture(autouse=True)
def override_deps():
    app.dependency_overrides[get_db] = _mock_db
    app.dependency_overrides[get_current_user] = _mock_current_user
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)


def _make_pattern():
    p = MagicMock()
    p.id = uuid.uuid4()
    p.user_id = uuid.uuid4()
    p.title = "Test Pattern"
    p.craft = CraftType.KNITTING
    p.status = PatternStatus.CONFIRMED
    p.source = PatternSource.TEXT
    p.cover_image_path = None
    p.original_file_path = "storage/original/test.txt"
    p.parsed_json_path = None
    p.gauge_stitches = None
    p.gauge_rows = None
    p.gauge_size = None
    p.gauge_unit = None
    p.needle_size = None
    p.sizes = []
    p.created_at = datetime.datetime.now()
    p.updated_at = None
    p.yarns = []
    return p


def _make_prefill_data(pattern_id=None):
    return {
        "id": pattern_id or uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "status": PatternStatus.CONFIRMED,
        "source": PatternSource.TEXT,
        "original_file_path": "storage/original/test.txt",
        "parsed_json_path": None,
        "cover_image_path": None,
        "created_at": datetime.datetime.now(),
        "updated_at": None,
        "title": "Test Pattern",
        "craft": CraftType.KNITTING,
        "gauge_stitches": 22.0,
        "gauge_rows": None,
        "gauge_size": 10.0,
        "gauge_unit": GaugeUnit.CM,
        "needle_size": "4mm",
        "sizes": [],
        "yarns": [],
    }


def _make_line_tokens():
    return {
        "line": 1,
        "bold": False,
        "italic": False,
        "font_size": None,
        "tokens": [{"type": "text", "value": "Cast on 20 stitches"}],
    }


class TestListPatterns:
    def test_returns_200_with_list(self):
        pattern = _make_pattern()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.get_by_user_id.return_value = [pattern]
            response = client.get("/patterns")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Test Pattern"

    def test_returns_empty_list_when_no_patterns(self):
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.get_by_user_id.return_value = []
            response = client.get("/patterns")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_401_when_not_authenticated(self):
        app.dependency_overrides.pop(get_current_user, None)
        try:
            response = client.get("/patterns")
        finally:
            app.dependency_overrides[get_current_user] = _mock_current_user
        assert response.status_code == 401


class TestGetPattern:
    def test_returns_200_when_found(self):
        pattern_id = uuid.uuid4()
        data = _make_prefill_data(pattern_id)
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.get_prefill.return_value = data
            response = client.get(f"/patterns/{pattern_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Test Pattern"

    def test_returns_404_when_not_found(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.get_prefill.return_value = None
            response = client.get(f"/patterns/{pattern_id}")
        assert response.status_code == 404


class TestImportFromPdf:
    def test_returns_201_on_success(self):
        pattern = _make_pattern()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.import_from_pdf.return_value = pattern
            response = client.post(
                "/patterns/import/pdf",
                files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")},
            )
        assert response.status_code == 201
        assert response.json()["title"] == "Test Pattern"

    def test_returns_415_on_invalid_file_type(self):
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.import_from_pdf.side_effect = InvalidFileTypeError("Only PDF allowed")
            response = client.post(
                "/patterns/import/pdf",
                files={"file": ("test.txt", b"not a pdf", "text/plain")},
            )
        assert response.status_code == 415

    def test_returns_413_on_file_too_large(self):
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.import_from_pdf.side_effect = FileTooLargeError("File too large")
            response = client.post(
                "/patterns/import/pdf",
                files={"file": ("big.pdf", b"%PDF-1.4", "application/pdf")},
            )
        assert response.status_code == 413

    def test_returns_401_when_not_authenticated(self):
        app.dependency_overrides.pop(get_current_user, None)
        try:
            response = client.post(
                "/patterns/import/pdf",
                files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
            )
        finally:
            app.dependency_overrides[get_current_user] = _mock_current_user
        assert response.status_code == 401


class TestImportFromText:
    def test_returns_201_on_success(self):
        pattern = _make_pattern()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.import_from_text.return_value = pattern
            response = client.post(
                "/patterns/import/text",
                content="cast on 20 stitches",
                headers={"Content-Type": "text/plain"},
            )
        assert response.status_code == 201

    def test_returns_422_on_empty_text(self):
        # Must send non-empty content so FastAPI's body validation passes and
        # the route handler is actually reached (empty body is rejected by FastAPI
        # before the handler runs).
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.import_from_text.side_effect = EmptyTextError("Text cannot be empty")
            response = client.post(
                "/patterns/import/text",
                content="   ",
                headers={"Content-Type": "text/plain"},
            )
        assert response.status_code == 422


class TestConfirmPattern:
    def test_returns_200_on_success(self):
        pattern = _make_pattern()
        pattern_id = uuid.uuid4()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.get_by_id.return_value = pattern
            mock_svc.confirm.return_value = pattern
            response = client.put(
                f"/patterns/{pattern_id}/confirm",
                data={"title": "My Pattern", "craft": "KNITTING", "sizes": "[]", "yarns": "[]"},
            )
        assert response.status_code == 200

    def test_returns_404_when_pattern_not_found(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.get_by_id.return_value = None
            response = client.put(
                f"/patterns/{pattern_id}/confirm",
                data={"title": "My Pattern", "craft": "KNITTING"},
            )
        assert response.status_code == 404

    def test_returns_422_on_empty_title(self):
        # Whitespace-only title passes FastAPI's Form validation (non-empty string)
        # but is rejected by the service → EmptyTitleError → 422.
        # An actually empty string ("") is rejected by FastAPI before the handler runs.
        pattern = _make_pattern()
        pattern_id = uuid.uuid4()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.get_by_id.return_value = pattern
            mock_svc.confirm.side_effect = EmptyTitleError("Title cannot be empty")
            response = client.put(
                f"/patterns/{pattern_id}/confirm",
                data={"title": "   ", "craft": "KNITTING"},
            )
        assert response.status_code == 422

    def test_returns_400_on_value_error_from_confirm(self):
        pattern = _make_pattern()
        pattern_id = uuid.uuid4()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.get_by_id.return_value = pattern
            mock_svc.confirm.side_effect = ValueError("grams_needed must have one value per size")
            response = client.put(
                f"/patterns/{pattern_id}/confirm",
                data={"title": "My Pattern", "craft": "KNITTING"},
            )
        assert response.status_code == 400

    def test_cover_image_bytes_read_when_file_provided(self):
        pattern = _make_pattern()
        pattern_id = uuid.uuid4()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.get_by_id.return_value = pattern
            mock_svc.confirm.return_value = pattern
            response = client.put(
                f"/patterns/{pattern_id}/confirm",
                data={"title": "My Pattern", "craft": "KNITTING"},
                files={"cover_image": ("cover.jpg", b"fake image data", "image/jpeg")},
            )
        assert response.status_code == 200
        cover_bytes = mock_svc.confirm.call_args.kwargs["cover_bytes"]
        assert cover_bytes == b"fake image data"

    def test_whitespace_sizes_string_treated_as_empty_list(self):
        # Starlette treats a truly empty form value ("") as "not sent" and uses
        # the default "[]". Whitespace-only ("   ") IS passed through, hits the
        # `not value.strip()` branch in _parse_json_list, and returns [].
        pattern = _make_pattern()
        pattern_id = uuid.uuid4()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.get_by_id.return_value = pattern
            mock_svc.confirm.return_value = pattern
            response = client.put(
                f"/patterns/{pattern_id}/confirm",
                data={"title": "My Pattern", "craft": "KNITTING", "sizes": "   "},
            )
        assert response.status_code == 200
        assert mock_svc.confirm.call_args.kwargs["sizes"] == []

    def test_csv_sizes_parsed_when_not_valid_json(self):
        pattern = _make_pattern()
        pattern_id = uuid.uuid4()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.get_by_id.return_value = pattern
            mock_svc.confirm.return_value = pattern
            response = client.put(
                f"/patterns/{pattern_id}/confirm",
                data={"title": "My Pattern", "craft": "KNITTING", "sizes": "S, M, L"},
            )
        assert response.status_code == 200
        assert mock_svc.confirm.call_args.kwargs["sizes"] == ["S", "M", "L"]


class TestTranslatePattern:
    def test_returns_200_on_success(self):
        pattern_id = uuid.uuid4()
        line_tokens = [_make_line_tokens()]
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.translate.return_value = line_tokens
            response = client.post(f"/patterns/{pattern_id}/translate")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["line"] == 1

    def test_returns_400_when_not_confirmed(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.translate.side_effect = PatternNotConfirmedError(
                "Pattern must be confirmed before translating"
            )
            response = client.post(f"/patterns/{pattern_id}/translate")
        assert response.status_code == 400

    def test_returns_404_when_pattern_not_found(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.pattern.pattern_service") as mock_svc:
            mock_svc.translate.return_value = None
            response = client.post(f"/patterns/{pattern_id}/translate")
        assert response.status_code == 404
