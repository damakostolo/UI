from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .features import LAYOUTS


@dataclass(frozen=True)
class PolicyConfig:
    min_events: int = 5
    min_confidence: float = 0.55
    min_probability_gain: float = 0.15
    cooldown_hours: int = 24


def decide(probabilities: dict[str, float], current: str, event_count: int, *,
           enabled: bool = True, active_task: bool = False, last_change_at: datetime | None = None,
           model_available: bool = True, config: PolicyConfig = PolicyConfig()) -> dict:
    if current not in LAYOUTS:
        raise ValueError("Unknown layout")
    reasons = []
    if not enabled: reasons.append("user_disabled")
    if not model_available: reasons.append("model_unavailable")
    if event_count < config.min_events: reasons.append("cold_start")
    if active_task: reasons.append("active_task")
    if last_change_at and datetime.now(timezone.utc) - last_change_at < timedelta(hours=config.cooldown_hours):
        reasons.append("cooldown")
    candidate = max(LAYOUTS, key=lambda l: probabilities.get(l, 0))
    confidence = probabilities.get(candidate, 0)
    if candidate == current: reasons.append("same_layout")
    if confidence < config.min_confidence: reasons.append("low_confidence")
    if confidence - probabilities.get(current, 0) < config.min_probability_gain: reasons.append("low_gain")
    return {"proposed_layout": candidate if not reasons else current,
            "decision": "propose" if not reasons else "no_change",
            "reasons": reasons or ["suggestion_available"], "confidence": confidence,
            "requires_confirmation": True, "can_undo": True}


def rule_layout(row: dict) -> str:
    if float(row["quick_actions_7d"]) >= 8:
        return "compact"
    if float(row["opens_tasks_7d"]) >= 10:
        return "focus"
    return "standard"
