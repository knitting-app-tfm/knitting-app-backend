from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_200_with_message():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Knitting App API running"}
