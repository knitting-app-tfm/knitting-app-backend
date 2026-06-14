import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.services.scaling.scaling_exceptions import ScalingConfigNotFoundError
from app.services.yarn import InvalidYarnDataError, PatternYarnNotFoundError, UserYarnNotFoundError


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

_YARN_BODY = {
    "label": "Main",
    "yarn_weight": "DK",
    "meters_per_unit": 200.0,
    "grams_per_unit": 100.0,
    "strands": 1,
}


def _make_user_yarn():
    y = MagicMock()
    y.id = uuid.uuid4()
    y.pattern_yarn_id = uuid.uuid4()
    y.label = "Main"
    y.yarn_weight = None
    y.meters_per_unit = 200.0
    y.grams_per_unit = 100.0
    y.strands = 1
    return y


def _make_yarn_calculation():
    return {"size_label": "M", "yarns": []}


class TestUpsertYarn:
    def test_returns_200_on_success(self):
        pattern_id = uuid.uuid4()
        yarn_id = uuid.uuid4()
        user_yarn = _make_user_yarn()
        with patch("app.routers.yarn.yarn_service") as mock_svc:
            mock_svc.upsert_yarn.return_value = user_yarn
            response = client.put(
                f"/patterns/{pattern_id}/yarns/{yarn_id}", json=_YARN_BODY
            )
        assert response.status_code == 200
        data = response.json()
        assert data["meters_per_unit"] == 200.0
        assert data["strands"] == 1

    def test_returns_400_on_invalid_yarn_data(self):
        pattern_id = uuid.uuid4()
        yarn_id = uuid.uuid4()
        with patch("app.routers.yarn.yarn_service") as mock_svc:
            mock_svc.upsert_yarn.side_effect = InvalidYarnDataError("Invalid data")
            response = client.put(
                f"/patterns/{pattern_id}/yarns/{yarn_id}", json=_YARN_BODY
            )
        assert response.status_code == 400

    def test_returns_400_when_no_scaling_config(self):
        pattern_id = uuid.uuid4()
        yarn_id = uuid.uuid4()
        with patch("app.routers.yarn.yarn_service") as mock_svc:
            mock_svc.upsert_yarn.side_effect = ScalingConfigNotFoundError("No scaling")
            response = client.put(
                f"/patterns/{pattern_id}/yarns/{yarn_id}", json=_YARN_BODY
            )
        assert response.status_code == 400

    def test_returns_404_when_yarn_not_found(self):
        pattern_id = uuid.uuid4()
        yarn_id = uuid.uuid4()
        with patch("app.routers.yarn.yarn_service") as mock_svc:
            mock_svc.upsert_yarn.side_effect = PatternYarnNotFoundError("Yarn not found")
            response = client.put(
                f"/patterns/{pattern_id}/yarns/{yarn_id}", json=_YARN_BODY
            )
        assert response.status_code == 404

    def test_returns_401_when_not_authenticated(self):
        pattern_id = uuid.uuid4()
        yarn_id = uuid.uuid4()
        app.dependency_overrides.pop(get_current_user, None)
        try:
            response = client.put(
                f"/patterns/{pattern_id}/yarns/{yarn_id}", json=_YARN_BODY
            )
        finally:
            app.dependency_overrides[get_current_user] = _mock_current_user
        assert response.status_code == 401


class TestListYarns:
    def test_returns_200_with_list(self):
        pattern_id = uuid.uuid4()
        user_yarn = _make_user_yarn()
        with patch("app.routers.yarn.yarn_service") as mock_svc:
            mock_svc.get_by_pattern_id.return_value = [user_yarn]
            response = client.get(f"/patterns/{pattern_id}/yarns")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["meters_per_unit"] == 200.0

    def test_returns_empty_list_when_none(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.yarn.yarn_service") as mock_svc:
            mock_svc.get_by_pattern_id.return_value = []
            response = client.get(f"/patterns/{pattern_id}/yarns")
        assert response.status_code == 200
        assert response.json() == []


class TestGetYarnCalculation:
    def test_returns_200_on_success(self):
        pattern_id = uuid.uuid4()
        result = _make_yarn_calculation()
        with patch("app.routers.yarn.yarn_service") as mock_svc:
            mock_svc.get_calculations.return_value = result
            response = client.get(f"/patterns/{pattern_id}/yarn-calculation")
        assert response.status_code == 200
        assert response.json()["size_label"] == "M"

    def test_returns_400_when_no_scaling_config(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.yarn.yarn_service") as mock_svc:
            mock_svc.get_calculations.side_effect = ScalingConfigNotFoundError("No scaling")
            response = client.get(f"/patterns/{pattern_id}/yarn-calculation")
        assert response.status_code == 400

    def test_returns_400_when_no_user_yarn_data(self):
        pattern_id = uuid.uuid4()
        with patch("app.routers.yarn.yarn_service") as mock_svc:
            mock_svc.get_calculations.side_effect = UserYarnNotFoundError("No yarn data")
            response = client.get(f"/patterns/{pattern_id}/yarn-calculation")
        assert response.status_code == 400
