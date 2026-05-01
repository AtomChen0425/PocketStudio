from fastapi.testclient import TestClient

from pocketStudio.main import app


def test_office_frontend_served() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "pocketStudio" in response.text
    assert "/static/app.js" in response.text


def test_static_assets_served() -> None:
    client = TestClient(app)

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert ".office-scene" in response.text
