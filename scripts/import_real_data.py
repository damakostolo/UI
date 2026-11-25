#!/usr/bin/env python3
"""Validate a volunteer bundle before materializing predecision feature rows."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.features import build_feature_row, timestamp  # noqa: E402


def read_csv(path: Path, schema_name: str) -> list[dict]:
    schema = json.loads((ROOT / "contracts" / schema_name).read_text(encoding="utf-8"))
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)) or not set(reader.fieldnames) <= set(schema["properties"]):
            raise ValueError(f"Unknown or duplicate CSV column: {path}")
        rows = list(reader)
    for row in rows:
        for field, property_ in schema["properties"].items():
            if field in row and property_.get("type") == "boolean":
                if row[field].lower() not in {"true", "false"}: raise ValueError(f"Invalid boolean {field}")
                row[field] = row[field].lower() == "true"
            if field in row and property_.get("type") == "integer": row[field] = int(row[field])
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(row)
    return rows


def import_bundle(bundle: Path, output: Path) -> dict:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("source") != "volunteer" or manifest.get("is_synthetic") is not False:
        raise ValueError("Real provenance marker required")
    if not manifest.get("collection_procedure") or not manifest.get("consent_document_version") or not manifest.get("consent_approved_by"):
        raise ValueError("Collection procedure and approved consent metadata required")
    consents = manifest.get("consents")
    if not isinstance(consents, list) or not consents:
        raise ValueError("Participant-level opt-in records required")
    consent_map = {}
    for record in consents:
        if set(record) != {"participant_id", "consented_at", "consent_version", "scope"} or record["scope"] != "research" or record["participant_id"] in consent_map:
            raise ValueError("Invalid consent record")
        timestamp(record["consented_at"])
        consent_map[record["participant_id"]] = record
    labels = read_csv(bundle / "preference_labels.csv", "preference_labels.schema.json")
    trials = read_csv(bundle / "ux_trials.csv", "trials.schema.json") if (bundle / "ux_trials.csv").exists() else []
    event_schema = json.loads((ROOT / "contracts/events.schema.json").read_text(encoding="utf-8"))
    events = []
    with (bundle / "events.jsonl").open(encoding="utf-8") as file:
        for line in file:
            event = json.loads(line)
            Draft202012Validator(event_schema, format_checker=FormatChecker()).validate(event)
            events.append(event)
    all_rows = [*labels, *trials, *events]
    if not labels or not events or any(r["source"] != "volunteer" or r["is_synthetic"] is not False for r in all_rows):
        raise ValueError("Only nonempty, real volunteer data can be imported")
    for row in all_rows:
        consent = consent_map.get(row["participant_id"])
        if not consent or consent["consent_version"] != row["consent_version"]:
            raise ValueError("Missing matching participant consent")
        at = row.get("occurred_at") or row.get("decision_at")
        if at and timestamp(at) < timestamp(consent["consented_at"]):
            raise ValueError("Observation predates consent")
    features = [build_feature_row(label, events) for label in labels]
    output.mkdir(parents=True, exist_ok=True)
    with (output / "feature_rows.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(features[0])); writer.writeheader(); writer.writerows(features)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if trials:
        with (output / "ux_trials.csv").open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(trials[0])); writer.writeheader(); writer.writerows(trials)
    return {"participants": len(consent_map), "labels": len(labels), "events": len(events), "trials": len(trials)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("bundle", type=Path); parser.add_argument("--output", type=Path, default=ROOT / "data/real")
    args = parser.parse_args(); print(json.dumps(import_bundle(args.bundle, args.output)))
