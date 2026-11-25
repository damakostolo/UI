import os
import tempfile
from pathlib import Path
import uuid
from datetime import datetime, timezone

_test_db = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
_test_db.close()
os.environ["DATABASE_URL"] = "sqlite:///" + _test_db.name.replace("\\", "/")

from fastapi.testclient import TestClient  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import func, select  # noqa: E402
from backend.app import app, engine, SessionLocal, InteractionEvent  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_database():
    yield
    client.close()
    engine.dispose()
    Path(_test_db.name).unlink(missing_ok=True)


def profile():
    p = client.post("/api/v1/profiles").json()
    return p, {"Authorization": "Bearer " + p["token"]}


def event(p, index=0, kind="quick_action"):
    return {"event_id":"evt_"+uuid.uuid4().hex, "participant_id":p["participant_id"], "session_id":"ses_123456",
            "occurred_at":datetime.now(timezone.utc).isoformat(), "event_type":kind, "widget_id":"quick_actions", "source":"volunteer", "is_synthetic":False,
            "consent_version":"v1"}


def test_consent_off_rejects_events_and_extra_fields():
    p,h=profile()
    assert client.post("/api/v1/events",headers=h,json=event(p)).status_code == 403
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(InteractionEvent).where(InteractionEvent.participant_id==p["participant_id"])) == 0
    assert client.post("/api/v1/consent",headers=h,json={"version":"v1"}).status_code == 200
    assert client.post("/api/v1/events",headers=h,json={**event(p),"email":"person@example.com"}).status_code == 422
    assert client.post("/api/v1/events",headers=h,json=event(p)).status_code == 200
    assert client.delete("/api/v1/consent",headers=h).status_code == 200
    assert client.post("/api/v1/events",headers=h,json=event(p)).status_code == 403
    assert client.delete("/api/v1/profile/me",headers=h).status_code == 200
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(InteractionEvent).where(InteractionEvent.participant_id==p["participant_id"])) == 0


def test_recommendation_requires_accept_and_can_undo():
    p,h=profile()
    client.post("/api/v1/consent",headers=h,json={"version":"v1"})
    for i in range(8): assert client.post("/api/v1/events",headers=h,json=event(p,i)).status_code == 200
    rec=client.post("/api/v1/recommendations",headers=h,json={"mode":"rule"}).json()
    assert rec["decision"] == "propose" and rec["proposed_layout"] == "compact"
    assert client.get("/api/v1/export/me",headers=h).json()["current_layout"] == "standard"
    assert client.post(f"/api/v1/recommendations/{rec['request_id']}/accept",headers=h).json()["current_layout"] == "compact"
    assert client.post(f"/api/v1/recommendations/{rec['request_id']}/undo",headers=h).json()["current_layout"] == "standard"


def test_active_task_blocks_change_and_reject_is_idempotent():
    p,h=profile(); client.post("/api/v1/consent",headers=h,json={"version":"v1"})
    for i in range(8): client.post("/api/v1/events",headers=h,json=event(p,i))
    blocked=client.post("/api/v1/recommendations",headers=h,json={"mode":"rule","active_task":True}).json()
    assert blocked["decision"] == "no_change" and "active_task" in blocked["reasons"]
    assert client.post(f"/api/v1/recommendations/{blocked['request_id']}/accept",headers=h).status_code == 409
    rec=client.post("/api/v1/recommendations",headers=h,json={"mode":"rule"}).json()
    assert client.post(f"/api/v1/recommendations/{rec['request_id']}/reject",headers=h).json()["status"] == "rejected"
    assert client.post(f"/api/v1/recommendations/{rec['request_id']}/reject",headers=h).json()["status"] == "rejected"


def test_health_and_layout_contract():
    assert client.get("/api/v1/health").json()["status"] == "ok"
    rows=client.get("/api/v1/layouts").json()["layouts"]
    assert len(rows)==3 and all(len(r["widgets"])==6 for r in rows)


def test_manual_layout_is_recommendation_baseline():
    p,h=profile()
    response=client.post("/api/v1/recommendations",headers=h,json={"mode":"static","current_layout":"focus"}).json()
    assert response["current_layout"] == "focus"
    assert client.get("/api/v1/export/me",headers=h).json()["current_layout"] == "focus"
