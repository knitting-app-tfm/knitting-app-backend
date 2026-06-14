import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.services.scaling import (
    InvalidGaugeError,
    InvalidSizeLabelError,
    InvalidSizePositionError,
    PatternNotFoundError,
    PatternNotTokenizedError,
    ScalingConfigNotFoundError,
)


def _mock_db():
    return MagicMock()


def _mock_current_user():
    u = MagicMock()
    u.id = uuid.uuid4()
    return u


@pytest.fixture(autouse=True)
def override_deps():
    app.dependency_overrides[get_db] = _mock_db
    app.dependency_overrides[get_current_user] = _mock_current_user
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)

_SCALING_BODY = {
    "size_label": "M",
    "size_position": 1,
    "gauge_stitches": 22.0,
    "gauge_rows": 28.0,
    "gauge_size": 10.0,
    "gauge_unit": "CM",
    "needle_size": "4mm",
}


def _make_scaling():
    s = MagicMock()
    s.id = uuid.uuid4()
    s.pattern_id = uuid.uuid4()
    s.size_label = "M"
    s.size_position = 1
    s.gauge_stitches = 22.0
    s.gauge_rows = 28.0
    s.gauge_size = 10.0
    s.gauge_unit = "CM"
    s.needle_size = "4mm"
    return s


def _make_scaled_response():
    return {"rows_warning": False, "size_label": "M", "lines": []}


class TestUpsertScaling:
    def test_returns_200_on_success(self):
        pattern_id = uuid.uuid4()
        scaling = _make_scaling()
        with patch("app.routers.scaling.scaling_service") as mock_svc:
            mock_svc.upsert_size.return_value = scaling
            response = client.put(f"/patterns/{pattern_id}/scaling", json=_SCALING_BODY)
        assert response.status_code == 200
        data = response.json()
        assert data["size_label"] == "M"
        assert data["gauge_stitches"] == 22.0

    def test_returns_404_when_pattern_not_found(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.scaling.scaling_service") as mock_svc:
            mock_svc.upsert_size.side_effect = PatternNotFoundError("Pattern not found")
            response = client.put(f"/patterns/{pattern_id}/scaling", json=_SCALING_BODY)
        assert response.status_code == 404

    def test_returns_400_on_invalid_size_label(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.scaling.scaling_service") as mock_svc:
            mock_svc.upsert_size.side_effect = InvalidSizeLabelError("Invalid size label")
            response = client.put(f"/patterns/{pattern_id}/scaling", json=_SCALING_BODY)
        assert response.status_code == 400

    def test_returns_400_on_invalid_size_position(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.scaling.scaling_service") as mock_svc:
            mock_svc.upsert_size.side_effect = InvalidSizePositionError("Invalid position")
            response = client.put(f"/patterns/{pattern_id}/scaling", json=_SCALING_BODY)
        assert response.status_code == 400

    def test_returns_400_on_invalid_gauge(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.scaling.scaling_service") as mock_svc:
            mock_svc.upsert_size.side_effect = InvalidGaugeError("Invalid gauge")
            response = client.put(f"/patterns/{pattern_id}/scaling", json=_SCALING_BODY)
        assert response.status_code == 400

    def test_returns_401_when_not_authenticated(self):
        pattern_id = uuid.uuid4()
        app.dependency_overrides.pop(get_current_user, None)
        try:
            response = client.put(f"/patterns/{pattern_id}/scaling", json=_SCALING_BODY)
        finally:
            app.dependency_overrides[get_current_user] = _mock_current_user
        assert response.status_code == 401


class TestGetScaling:
    def test_returns_200_when_found(self):
        pattern_id = uuid.uuid4()
        scaling = _make_scaling()
        with patch("app.routers.scaling.scaling_service") as mock_svc:
            mock_svc.get_by_pattern_id.return_value = scaling
            response = client.get(f"/patterns/{pattern_id}/scaling")
        assert response.status_code == 200
        assert response.json()["size_label"] == "M"

    def test_returns_200_with_null_when_not_set(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.scaling.scaling_service") as mock_svc:
            mock_svc.get_by_pattern_id.return_value = None
            response = client.get(f"/patterns/{pattern_id}/scaling")
        assert response.status_code == 200
        assert response.json() is None


class TestGetScaledPattern:
    def test_returns_200_on_success(self):
        pattern_id = uuid.uuid4()
        result = _make_scaled_response()
        with patch("app.routers.scaling.scaling_service") as mock_svc:
            mock_svc.scale_pattern.return_value = result
            response = client.get(f"/patterns/{pattern_id}/scaled")
        assert response.status_code == 200
        data = response.json()
        assert data["size_label"] == "M"
        assert data["rows_warning"] is False

    def test_returns_404_when_pattern_not_found(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.scaling.scaling_service") as mock_svc:
            mock_svc.scale_pattern.side_effect = PatternNotFoundError("Not found")
            response = client.get(f"/patterns/{pattern_id}/scaled")
        assert response.status_code == 404

    def test_returns_400_when_not_tokenized(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.scaling.scaling_service") as mock_svc:
            mock_svc.scale_pattern.side_effect = PatternNotTokenizedError("Not tokenized")
            response = client.get(f"/patterns/{pattern_id}/scaled")
        assert response.status_code == 400

    def test_returns_400_when_no_scaling_config(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.scaling.scaling_service") as mock_svc:
            mock_svc.scale_pattern.side_effect = ScalingConfigNotFoundError("No scaling")
            response = client.get(f"/patterns/{pattern_id}/scaled")
        assert response.status_code == 400
