import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.abbreviation import AbbreviationCraft, AbbreviationType


def _mock_db():
    return MagicMock()


@pytest.fixture(autouse=True)
def override_db():
    app.dependency_overrides[get_db] = _mock_db
    yield
    app.dependency_overrides.pop(get_db, None)


client = TestClient(app)


def _make_abbreviation():
    a = MagicMock()
    a.id = uuid.uuid4()
    a.abbreviation = "k"
    a.full_name = "knit"
    a.description = "Basic knit stitch"
    a.type = AbbreviationType.STITCH
    a.craft = AbbreviationCraft.KNITTING
    a.video_link = None
    return a


class TestListAbbreviations:
    def test_returns_200_with_list(self):
        abbr = _make_abbreviation()
        with patch("app.routers.abbreviation.abbreviation_service") as mock_svc:
            mock_svc.get_all.return_value = [abbr]
            response = client.get("/abbreviations")
        assert response.status_code == 200
        data = response.json()
        assert "abbreviations" in data
        assert len(data["abbreviations"]) == 1
        assert data["abbreviations"][0]["abbreviation"] == "k"

    def test_returns_empty_list_when_no_abbreviations(self):
        with patch("app.routers.abbreviation.abbreviation_service") as mock_svc:
            mock_svc.get_all.return_value = []
            response = client.get("/abbreviations")
        assert response.status_code == 200
        assert response.json()["abbreviations"] == []

    def test_passes_craft_filter_to_service(self):
        with patch("app.routers.abbreviation.abbreviation_service") as mock_svc:
            mock_svc.get_all.return_value = []
            client.get("/abbreviations?craft=KNITTING")
        call_kwargs = mock_svc.get_all.call_args
        assert call_kwargs.kwargs["craft"].value == "KNITTING"

    def test_passes_type_filter_to_service(self):
        with patch("app.routers.abbreviation.abbreviation_service") as mock_svc:
            mock_svc.get_all.return_value = []
            client.get("/abbreviations?type=STITCH")
        call_kwargs = mock_svc.get_all.call_args
        assert call_kwargs.kwargs["type"].value == "STITCH"


class TestGetAbbreviationByCode:
    def test_returns_200_when_found(self):
        abbr = _make_abbreviation()
        with patch("app.routers.abbreviation.abbreviation_service") as mock_svc:
            mock_svc.get_by_code.return_value = abbr
            response = client.get("/abbreviations/code/k")
        assert response.status_code == 200
        assert response.json()["abbreviation"] == "k"

    def test_returns_404_when_not_found(self):
        with patch("app.routers.abbreviation.abbreviation_service") as mock_svc:
            mock_svc.get_by_code.side_effect = HTTPException(
                status_code=404, detail="Abbreviation not found"
            )
            response = client.get("/abbreviations/code/unknown")
        assert response.status_code == 404


class TestGetAbbreviationById:
    def test_returns_200_when_found(self):
        abbr = _make_abbreviation()
        with patch("app.routers.abbreviation.abbreviation_service") as mock_svc:
            mock_svc.get_by_id.return_value = abbr
            response = client.get(f"/abbreviations/{abbr.id}")
        assert response.status_code == 200
        assert response.json()["full_name"] == "knit"

    def test_returns_404_when_not_found(self):
        abbr_id = uuid.uuid4()
        with patch("app.routers.abbreviation.abbreviation_service") as mock_svc:
            mock_svc.get_by_id.side_effect = HTTPException(
                status_code=404, detail="Abbreviation not found"
            )
            response = client.get(f"/abbreviations/{abbr_id}")
        assert response.status_code == 404
