from datetime import datetime, timezone

import pandas as pd
import pytest
import json
from pathlib import Path

from ml.features import MODEL_FEATURES, build_feature_row, validate_predecision
from ml.policy import decide
from ml.research import split_participants
from scripts.generate_synthetic_data import generate
from scripts.import_real_data import import_bundle


def test_participant_split_is_disjoint():
    frame = pd.DataFrame([{"participant_id": f"syn_{i:05d}", "preferred_layout": ("standard", "compact", "focus")[i % 3]} for i in range(120)])
    result = split_participants(frame)
    groups = [set(result[k]) for k in ("train_ids", "validation_ids", "test_ids")]
    assert all(a.isdisjoint(b) for i, a in enumerate(groups) for b in groups[i + 1:])


def test_no_future_event_enters_feature_row():
    label = {"participant_id":"usr_123456", "session_id":"ses_123456", "decision_at":"2026-10-02T12:00:00Z", "observed_until":"2026-10-02T11:59:59Z",
             "preferred_layout":"focus", "label_source":"explicit_preference", "source":"volunteer", "is_synthetic":False, "consent_version":"v1"}
    before = {"participant_id":"usr_123456", "session_id":"ses_123456", "occurred_at":"2026-10-02T11:00:00Z", "event_type":"widget_open", "widget_id":"tasks"}
    after = {**before, "occurred_at":"2026-10-02T12:00:01Z"}
    row = build_feature_row(label, [before, after])
    assert row["opens_tasks_7d"] == 1
    assert "preferred_layout" not in MODEL_FEATURES
    with pytest.raises(ValueError): validate_predecision({**label, "observed_until": label["decision_at"]})


def test_policy_cold_start_and_active_task():
    p = {"standard":.1,"compact":.8,"focus":.1}
    assert decide(p,"standard",0)["decision"] == "no_change"
    assert decide(p,"standard",8,active_task=True)["reasons"] == ["active_task"]
    assert decide(p,"standard",8)["decision"] == "propose"


def test_policy_cooldown():
    p = {"standard":.1,"compact":.8,"focus":.1}
    assert "cooldown" in decide(p,"standard",8,last_change_at=datetime.now(timezone.utc))["reasons"]


def test_synthetic_generator_repeats_byte_for_byte(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    generate(30, 2, 31, first); generate(30, 2, 31, second)
    assert (first / "feature_rows.csv").read_bytes() == (second / "feature_rows.csv").read_bytes()
    assert (first / "dataset_manifest.json").read_bytes() == (second / "dataset_manifest.json").read_bytes()


def test_real_import_rejects_missing_consent(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"source":"volunteer","is_synthetic":False,"collection_procedure":"pilot",
        "consent_document_version":"v1","consent_approved_by":"committee","consents":[]}),encoding="utf-8")
    with pytest.raises(ValueError, match="opt-in"):
        import_bundle(tmp_path, tmp_path / "output")
