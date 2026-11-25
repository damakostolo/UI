from __future__ import annotations

import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from ml.features import LAYOUTS
from ml.policy import decide, rule_layout

ROOT = Path(__file__).resolve().parents[1]
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./dashboard.sqlite3")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(engine)


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


class Base(DeclarativeBase): pass


class AnonymousParticipant(Base):
    __tablename__ = "participants"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    consent: Mapped["ConsentRecord | None"] = relationship(back_populates="participant", cascade="all,delete-orphan", uselist=False)
    events: Mapped[list["InteractionEvent"]] = relationship(cascade="all,delete-orphan")
    recommendations: Mapped[list["Recommendation"]] = relationship(cascade="all,delete-orphan")
    trials: Mapped[list["StudyTrial"]] = relationship(cascade="all,delete-orphan")
    layout: Mapped["LayoutState | None"] = relationship(cascade="all,delete-orphan", uselist=False)


class ConsentRecord(Base):
    __tablename__ = "consents"
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), primary_key=True)
    version: Mapped[str] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    participant: Mapped[AnonymousParticipant] = relationship(back_populates="consent")


class InteractionEvent(Base):
    __tablename__ = "events"
    event_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(80))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    widget_id: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    consent_version: Mapped[str] = mapped_column(String(50))
    device_category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    viewport_category: Mapped[str | None] = mapped_column(String(16), nullable=True)


class LayoutState(Base):
    __tablename__ = "layout_states"
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), primary_key=True)
    current_layout: Mapped[str] = mapped_column(String(16), default="standard")
    previous_layout: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    current_layout: Mapped[str] = mapped_column(String(16))
    proposed_layout: Mapped[str] = mapped_column(String(16))
    decision: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class StudyTrial(Base):
    __tablename__ = "study_trials"
    trial_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(80))
    task_id: Mapped[str] = mapped_column(String(32))
    condition: Mapped[str] = mapped_column(String(16))
    layout_variant: Mapped[str] = mapped_column(String(16))
    sequence_index: Mapped[int] = mapped_column(Integer)
    elapsed_ms: Mapped[int] = mapped_column(Integer)
    click_count: Mapped[int] = mapped_column(Integer)
    completed: Mapped[bool] = mapped_column(Boolean)
    error_count: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(16))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    consent_version: Mapped[str] = mapped_column(String(50))


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ModelArtifact(Base):
    __tablename__ = "model_artifacts"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("model_runs.id"))
    path: Mapped[str] = mapped_column(String(200))


Base.metadata.create_all(engine)

class Strict(BaseModel): model_config = ConfigDict(extra="forbid")

class ConsentIn(Strict): version: str = Field(min_length=1, max_length=50)
class EventIn(Strict):
    event_id: str = Field(pattern=r"^[A-Za-z0-9_-]{6,80}$")
    participant_id: str = Field(pattern=r"^[A-Za-z0-9_-]{6,80}$")
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{6,80}$")
    occurred_at: datetime
    event_type: Literal["widget_open", "task_start", "task_complete", "quick_action", "layout_preview", "layout_accept", "layout_reject", "layout_undo"]
    widget_id: Literal["tasks", "calendar", "activity", "quick_actions", "reports", "notifications", "none"]
    source: Literal["volunteer", "synthetic"]
    is_synthetic: bool
    consent_version: str = Field(max_length=50)
    device_category: Literal["desktop", "tablet", "mobile", "unknown"] | None = None
    viewport_category: Literal["small", "medium", "large", "unknown"] | None = None

class RecommendIn(Strict):
    mode: Literal["static", "rule", "hybrid"]
    current_layout: Literal["standard", "compact", "focus"] | None = None
    active_task: bool = False
    enabled: bool = True
    synthetic_mode: bool = False

class TrialIn(Strict):
    trial_id: str = Field(pattern=r"^[A-Za-z0-9_-]{6,80}$")
    participant_id: str
    session_id: str
    task_id: Literal["find_task", "open_report", "use_quick_action"]
    condition: Literal["static", "rule", "hybrid"]
    layout_variant: Literal["standard", "compact", "focus"]
    sequence_index: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
    click_count: int = Field(ge=0)
    completed: bool
    error_count: int = Field(ge=0)
    source: Literal["volunteer", "synthetic"]
    is_synthetic: bool
    consent_version: str

app = FastAPI(title="UI ML Research API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:15173", "http://127.0.0.1:15174"], allow_methods=["GET", "POST", "DELETE"], allow_headers=["Authorization", "Content-Type"])


def db_session():
    with SessionLocal() as db: yield db


def participant(authorization: str | None = Header(default=None), db: Session = Depends(db_session)) -> AnonymousParticipant:
    token = authorization.removeprefix("Bearer ") if authorization and authorization.startswith("Bearer ") else ""
    p = db.scalar(select(AnonymousParticipant).where(AnonymousParticipant.token == token)) if token else None
    if not p: raise HTTPException(401, "Invalid participant token")
    return p


def consent_required(p: AnonymousParticipant) -> ConsentRecord:
    if not p.consent or not p.consent.enabled: raise HTTPException(403, "Consent required")
    return p.consent


@app.get("/api/v1/health")
def health(): return {"status": "ok", "version": app.version}


@app.get("/api/v1/layouts")
def layouts(): return {"layouts": [{"id": l, "widgets": ["tasks", "calendar", "activity", "quick_actions", "reports", "notifications"]} for l in LAYOUTS]}


@app.post("/api/v1/profiles")
def create_profile(db: Session = Depends(db_session)):
    p = AnonymousParticipant(id="usr_" + uuid.uuid4().hex, token=secrets.token_urlsafe(32))
    p.layout = LayoutState(current_layout="standard")
    db.add(p); db.commit()
    return {"participant_id": p.id, "token": p.token, "current_layout": "standard"}


@app.get("/api/v1/consent")
def get_consent(p: AnonymousParticipant = Depends(participant)):
    return {"enabled": bool(p.consent and p.consent.enabled), "version": p.consent.version if p.consent else None}


@app.post("/api/v1/consent")
def grant_consent(body: ConsentIn, p: AnonymousParticipant = Depends(participant), db: Session = Depends(db_session)):
    if not p.consent: p.consent = ConsentRecord(version=body.version, enabled=True, consented_at=now())
    else: p.consent.version = body.version; p.consent.enabled = True; p.consent.consented_at = now()
    db.commit(); return {"enabled": True, "version": body.version}


@app.delete("/api/v1/consent")
def revoke_consent(p: AnonymousParticipant = Depends(participant), db: Session = Depends(db_session)):
    if p.consent: p.consent.enabled = False
    db.commit(); return {"enabled": False}


@app.post("/api/v1/events")
def add_event(body: EventIn, p: AnonymousParticipant = Depends(participant), db: Session = Depends(db_session)):
    consent = consent_required(p)
    if body.participant_id != p.id or body.consent_version != consent.version or body.source != "volunteer" or body.is_synthetic:
        raise HTTPException(403, "Invalid event provenance")
    if body.occurred_at < aware(consent.consented_at) or body.occurred_at > now() + timedelta(minutes=5):
        raise HTTPException(422, "Invalid event time")
    if db.get(InteractionEvent, body.event_id): return {"stored": True, "event_id": body.event_id}
    ttl_days = max(1, int(os.getenv("EVENT_TTL_DAYS", "30")))
    db.execute(delete(InteractionEvent).where(InteractionEvent.occurred_at < now() - timedelta(days=ttl_days)))
    db.add(InteractionEvent(**body.model_dump())); db.commit()
    return {"stored": True, "event_id": body.event_id}


def recent_events(db: Session, p: AnonymousParticipant):
    cutoff = now() - timedelta(days=7)
    return list(db.scalars(select(InteractionEvent).where(InteractionEvent.participant_id == p.id, InteractionEvent.occurred_at >= cutoff, InteractionEvent.occurred_at < now())))


@app.post("/api/v1/recommendations")
def recommend(body: RecommendIn, p: AnonymousParticipant = Depends(participant), db: Session = Depends(db_session)):
    if body.current_layout and body.current_layout != p.layout.current_layout:
        # Explicit manual layout selection is local-first; synchronize that
        # user-controlled state before calculating a new proposal.
        p.layout.current_layout = body.current_layout
        p.layout.previous_layout = None
        db.commit()
    current = p.layout.current_layout
    events = recent_events(db, p) if p.consent and p.consent.enabled else []
    count = len(events)
    row = {"quick_actions_7d": sum(e.event_type == "quick_action" for e in events),
           "opens_tasks_7d": sum(e.event_type == "widget_open" and e.widget_id == "tasks" for e in events)}
    probabilities = {l: 0.0 for l in LAYOUTS}
    model_name = body.mode
    available = True
    if body.mode == "static": probabilities["standard"] = 1.0
    elif body.mode == "rule": probabilities[rule_layout(row)] = 1.0
    else:
        # A synthetic model is only available in an explicitly marked demo request.
        model_path = ROOT / "results/synthetic/demo_model.joblib"
        available = bool(body.synthetic_mode and model_path.exists())
        if available:
            import joblib
            from ml.features import MODEL_FEATURES
            artifact = joblib.load(model_path)
            model = artifact["pipeline"]
            feature = {"opens_tasks_7d": row["opens_tasks_7d"], "opens_reports_7d": sum(e.event_type == "widget_open" and e.widget_id == "reports" for e in events),
                       "quick_actions_7d": row["quick_actions_7d"], "avg_actions_per_session_7d": count / max(len({e.session_id for e in events}), 1),
                       "active_sessions_7d": len({e.session_id for e in events}), "prior_undo_rate": 0.0,
                       "last_device_category": events[-1].device_category or "unknown" if events else "unknown",
                       "last_viewport_category": events[-1].viewport_category or "unknown" if events else "unknown",
                       "time_of_day_bin": "day", "current_layout": current}
            import pandas as pd
            raw = model.predict_proba(pd.DataFrame([feature])[list(MODEL_FEATURES)])[0]
            probabilities = dict(zip(model.named_steps["model"].classes_, map(float, raw)))
            model_name = "logistic_regression_synthetic_demo"
        else:
            probabilities[current] = 1.0
            model_name = "unavailable"
    decision = decide(probabilities, current, count, enabled=body.enabled and body.mode != "static" and bool(p.consent and p.consent.enabled),
                      active_task=body.active_task, last_change_at=aware(p.layout.last_change_at), model_available=available)
    rec = Recommendation(id="rec_" + uuid.uuid4().hex, participant_id=p.id, current_layout=current,
                         proposed_layout=decision["proposed_layout"], decision=decision["decision"])
    db.add(rec); db.commit()
    return {"request_id": rec.id, "model_name": model_name, "current_layout": current, "proposed_layout": decision["proposed_layout"],
            "probabilities": probabilities, "confidence": decision["confidence"], "decision": decision["decision"],
            "reasons": decision["reasons"], "requires_confirmation": True, "can_undo": True, "synthetic_mode": body.synthetic_mode}


def transition(rec_id: str, action: str, p: AnonymousParticipant, db: Session):
    rec = db.get(Recommendation, rec_id)
    if not rec or rec.participant_id != p.id: raise HTTPException(404, "Recommendation not found")
    if action == "accept":
        if rec.status == "accepted": return {"status": rec.status, "current_layout": p.layout.current_layout}
        if rec.status != "pending" or rec.decision != "propose" or p.layout.current_layout != rec.current_layout:
            raise HTTPException(409, "Recommendation cannot be accepted")
        p.layout.previous_layout = p.layout.current_layout
        p.layout.current_layout = rec.proposed_layout
        p.layout.last_change_at = now(); rec.status = "accepted"
    elif action == "reject":
        if rec.status == "pending": rec.status = "rejected"
    elif action == "undo":
        if rec.status == "undone": return {"status": rec.status, "current_layout": p.layout.current_layout}
        if rec.status != "accepted" or p.layout.current_layout != rec.proposed_layout:
            raise HTTPException(409, "Cannot undo")
        p.layout.current_layout = rec.current_layout; p.layout.previous_layout = None; p.layout.last_change_at = None; rec.status = "undone"
    db.commit(); return {"status": rec.status, "current_layout": p.layout.current_layout}


@app.post("/api/v1/recommendations/{rec_id}/accept")
def accept(rec_id: str, p: AnonymousParticipant = Depends(participant), db: Session = Depends(db_session)): return transition(rec_id, "accept", p, db)
@app.post("/api/v1/recommendations/{rec_id}/reject")
def reject(rec_id: str, p: AnonymousParticipant = Depends(participant), db: Session = Depends(db_session)): return transition(rec_id, "reject", p, db)
@app.post("/api/v1/recommendations/{rec_id}/undo")
def undo(rec_id: str, p: AnonymousParticipant = Depends(participant), db: Session = Depends(db_session)): return transition(rec_id, "undo", p, db)


@app.post("/api/v1/study/trials")
def add_trial(body: TrialIn, p: AnonymousParticipant = Depends(participant), db: Session = Depends(db_session)):
    consent = consent_required(p)
    if body.participant_id != p.id or body.consent_version != consent.version or body.source != "volunteer" or body.is_synthetic:
        raise HTTPException(403, "Invalid trial provenance")
    if db.get(StudyTrial, body.trial_id): return {"stored": True}
    db.add(StudyTrial(**body.model_dump())); db.commit(); return {"stored": True}


@app.get("/api/v1/export/me")
def export_me(p: AnonymousParticipant = Depends(participant), db: Session = Depends(db_session)):
    events = db.scalars(select(InteractionEvent).where(InteractionEvent.participant_id == p.id)).all()
    trials = db.scalars(select(StudyTrial).where(StudyTrial.participant_id == p.id)).all()
    return {"participant_id": p.id, "consent": get_consent(p), "current_layout": p.layout.current_layout,
            "events": [{k: getattr(e, k) for k in ("event_id", "session_id", "occurred_at", "event_type", "widget_id")} for e in events],
            "trials": [{k: getattr(t, k) for k in ("trial_id", "task_id", "condition", "layout_variant", "sequence_index", "elapsed_ms", "click_count", "completed", "error_count")} for t in trials]}


@app.delete("/api/v1/profile/me")
def delete_profile(p: AnonymousParticipant = Depends(participant), db: Session = Depends(db_session)):
    db.delete(p); db.commit(); return {"deleted": True}
