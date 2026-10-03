import os
import uuid
from datetime import datetime, timezone

import pytest

os.environ["SHELFSENSE_API_KEY"] = "test-key-0123456789abcdef"
os.environ["SHELFSENSE_DB"] = ":memory:"
os.environ["SHELFSENSE_LLM_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

HEADERS = {"X-Api-Key": os.environ["SHELFSENSE_API_KEY"]}


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def scan(barcode: str, price: int | None, confidence: float = 0.95, client_id: str | None = None) -> dict:
    return {
        "client_id": client_id or str(uuid.uuid4()),
        "device_id": "handheld-demo",
        "store_id": "CHI-042",
        "barcode": barcode,
        "shelf_price_cents": price,
        "ocr_raw_text": "" if price is None else f"${price / 100:.2f}",
        "ocr_confidence": confidence,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def test_rejects_missing_api_key(client):
    response = client.post("/api/v1/scans", json={"scans": [scan("049000028911", 699)]})
    assert response.status_code == 401


def test_classifies_match_mismatch_unknown_and_recapture(client):
    body = {
        "scans": [
            scan("049000028911", 699),
            scan("036000291452", 299),
            scan("999999999999", 100),
            scan("078742370217", 389, confidence=0.3),
        ]
    }
    response = client.post("/api/v1/scans", json=body, headers=HEADERS)
    assert response.status_code == 200
    statuses = [r["status"] for r in response.json()["results"]]
    assert statuses == ["MATCH", "MISMATCH", "UNKNOWN_SKU", "NEEDS_RECAPTURE"]


def test_retry_with_same_client_id_is_idempotent(client):
    payload = scan("036000291452", 299, client_id="retry-0000-0001")
    first = client.post("/api/v1/scans", json={"scans": [payload]}, headers=HEADERS).json()
    second = client.post("/api/v1/scans", json={"scans": [payload]}, headers=HEADERS).json()
    assert first["results"][0]["duplicate"] is False
    assert second["results"][0]["duplicate"] is True
    open_for_barcode = [
        e for e in client.get("/api/v1/exceptions", headers=HEADERS).json() if e["barcode"] == "036000291452"
    ]
    assert len(open_for_barcode) == 1


def test_mismatch_gets_rules_task_with_sop_deadline(client):
    client.post("/api/v1/scans", json={"scans": [scan("073410013533", 999)]}, headers=HEADERS)
    exceptions = client.get("/api/v1/exceptions", headers=HEADERS).json()
    target = next(e for e in exceptions if e["barcode"] == "073410013533")
    assert target["task_source"] == "rules"
    assert "within 1 hour" in target["task_text"]


def test_matching_rescan_auto_closes_open_exception(client):
    client.post("/api/v1/scans", json={"scans": [scan("016000275287", 499)]}, headers=HEADERS)
    client.post("/api/v1/scans", json={"scans": [scan("016000275287", 459)]}, headers=HEADERS)
    exceptions = client.get("/api/v1/exceptions", headers=HEADERS).json()
    assert all(e["barcode"] != "016000275287" for e in exceptions)


def test_ocr_misread_feeds_training_export(client):
    client.post("/api/v1/scans", json={"scans": [scan("041220576463", 219)]}, headers=HEADERS)
    target = next(
        e for e in client.get("/api/v1/exceptions", headers=HEADERS).json() if e["barcode"] == "041220576463"
    )
    resolved = client.post(
        f"/api/v1/exceptions/{target['id']}/resolve",
        json={"resolution": "OCR_MISREAD", "corrected_price_cents": 279},
        headers=HEADERS,
    )
    assert resolved.status_code == 204
    export = client.get("/api/v1/feedback/ocr-misreads.jsonl", headers=HEADERS).text
    assert '"label_price_cents": 279' in export
    assert client.get("/api/v1/metrics", headers=HEADERS).json()["ocr_misreads_flagged"] >= 1


def test_rejects_malformed_barcode(client):
    response = client.post("/api/v1/scans", json={"scans": [scan("ABC123", 100)]}, headers=HEADERS)
    assert response.status_code == 422
