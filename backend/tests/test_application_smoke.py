import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_openapi_schema_loads():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema.get("paths"), "No API routes registered"


def test_health_endpoints():
    for path in ("/api/health", "/api/v1/health"):
        response = client.get(path)
        if response.status_code == 404:
            continue
        assert response.status_code < 500, (
            f"{path} returned HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )


def test_registered_get_routes_do_not_crash():
    schema = client.get("/openapi.json").json()
    failures = []

    for path, methods in schema.get("paths", {}).items():
        if "get" not in methods:
            continue

        # Substitute harmless synthetic IDs; do not send write requests.
        url = path
        for parameter in methods["get"].get("parameters", []):
            if parameter.get("in") == "path":
                name = parameter["name"]
                value = "SYN-0001"
                if name.endswith("_id") and name != "patient_id":
                    value = "1"
                url = url.replace("{" + name + "}", value)

        response = client.get(url)
        if response.status_code >= 500:
            failures.append(
                f"GET {url} -> HTTP {response.status_code}: "
                f"{response.text[:160]}"
            )

    assert not failures, "\n".join(failures)
