from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_KML = Path(__file__).parent / "sample.kml"


def upload_sample_kml():
    with open(SAMPLE_KML, "rb") as file:
        response = client.post(
            "/api/files/",
            files={"file": ("sample.kml", file, "application/vnd.google-earth.kml+xml")}
        )

    assert response.status_code == 201
    return response.json()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_kml():
    data = upload_sample_kml()

    assert data["filename"] == "sample.kml"
    assert data["feature_count"] == 3
    assert data["crs"] is not None
    assert data["status"] == "COMPLETED"


def test_file_information():
    data = upload_sample_kml()
    file_id = data["id"]

    response = client.get(f"/api/files/{file_id}")

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == file_id
    assert data["feature_count"] == 3
    assert data["status"] == "COMPLETED"


def test_measurements():
    data = upload_sample_kml()
    file_id = data["id"]

    response = client.get(f"/api/files/{file_id}/measurements/")

    assert response.status_code == 200

    data = response.json()
    assert data["feature_count"] == 3

    measurements = data["measurements"]

    assert len(measurements) == 3

    polygon = next(item for item in measurements if item["geometry_type"] == "Polygon")
    line = next(item for item in measurements if item["geometry_type"] == "LineString")
    point = next(item for item in measurements if item["geometry_type"] == "Point")

    assert polygon["measurement"] is not None
    assert polygon["measurement"] > 0
    assert polygon["measurement_unit"] == "square_meters"

    assert line["measurement"] is not None
    assert line["measurement"] > 0
    assert line["measurement_unit"] == "meters"

    assert point["measurement"] is None
    assert point["measurement_unit"] is None


def test_invalid_file():
    response = client.post(
        "/api/files/",
        files={"file": ("test.txt", b"invalid file", "text/plain")}
    )

    assert response.status_code == 400


def test_missing_file():
    response = client.get("/api/files/non-existent-id")
    assert response.status_code == 404


def test_missing_measurements():
    response = client.get("/api/files/non-existent-id/measurements/")
    assert response.status_code == 404