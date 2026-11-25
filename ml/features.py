from __future__ import annotations

from datetime import datetime, timedelta

LAYOUTS = ("standard", "compact", "focus")
FEATURES_NUM = ("opens_tasks_7d", "opens_reports_7d", "quick_actions_7d", "avg_actions_per_session_7d", "active_sessions_7d", "prior_undo_rate")
FEATURES_CAT = ("last_device_category", "last_viewport_category", "time_of_day_bin", "current_layout")
MODEL_FEATURES = FEATURES_NUM + FEATURES_CAT
FORBIDDEN = {"participant_id", "session_id", "decision_at", "observed_until", "preferred_layout", "elapsed_ms", "completed", "trial_completed", "future_score", "active_task"}
assert not (set(MODEL_FEATURES) & FORBIDDEN)


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_predecision(row: dict) -> None:
    if timestamp(row["observed_until"]) >= timestamp(row["decision_at"]):
        raise ValueError("Feature observation must precede decision")


def build_feature_row(label: dict, events: list[dict], current_layout: str = "standard") -> dict:
    """Use only consented events strictly before the preference decision."""
    decision = timestamp(label["decision_at"])
    cutoff = timestamp(label["observed_until"])
    if cutoff >= decision:
        raise ValueError("Invalid observation cutoff")
    prior = [e for e in events if e["participant_id"] == label["participant_id"] and
             cutoff - timedelta(days=7) <= timestamp(e["occurred_at"]) <= cutoff and
             timestamp(e["occurred_at"]) < decision]
    prior.sort(key=lambda e: e["occurred_at"])
    sessions = {e["session_id"] for e in prior}
    undo_count = sum(e["event_type"] == "layout_undo" for e in prior)
    layout_actions = sum(e["event_type"] in {"layout_accept", "layout_undo"} for e in prior)
    row = {k: label[k] for k in ("participant_id", "session_id", "decision_at", "observed_until", "preferred_layout", "label_source", "source", "is_synthetic", "consent_version")}
    row.update({
        "opens_tasks_7d": sum(e["event_type"] == "widget_open" and e["widget_id"] == "tasks" for e in prior),
        "opens_reports_7d": sum(e["event_type"] == "widget_open" and e["widget_id"] == "reports" for e in prior),
        "quick_actions_7d": sum(e["event_type"] == "quick_action" for e in prior),
        "avg_actions_per_session_7d": len(prior) / max(len(sessions), 1),
        "active_sessions_7d": len(sessions),
        "prior_undo_rate": undo_count / max(layout_actions, 1),
        "last_device_category": prior[-1].get("device_category", "unknown") if prior else "unknown",
        "last_viewport_category": prior[-1].get("viewport_category", "unknown") if prior else "unknown",
        "time_of_day_bin": "morning" if decision.hour < 12 else "day" if decision.hour < 18 else "evening",
        "current_layout": current_layout,
    })
    return row
