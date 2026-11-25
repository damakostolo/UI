#!/usr/bin/env python3
"""Recompute synthetic offline metrics in a temporary directory without touching results/."""
from __future__ import annotations

import csv
import json
import math
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.research import evaluate

SOURCE = ROOT / "data/sample_synthetic/feature_rows.csv"
EXISTING = ROOT / "results/synthetic/models_comparison.csv"


def rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {r["model"]: r for r in csv.DictReader(handle)}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ui_ml_repro_") as temporary:
        scratch = Path(temporary)
        output = scratch / "results/synthetic"
        evaluate(SOURCE, output, scratch, "synthetic")
        before, after = rows(EXISTING), rows(output / "models_comparison.csv")
        fields = ("status", "accuracy", "macro_precision", "macro_recall", "macro_f1", "logloss", "coverage", "selected_variant")
        mismatches = []
        for name in sorted(set(before) | set(after)):
            if name not in before or name not in after:
                mismatches.append(f"model set: {name}")
                continue
            for field in fields:
                a, b = before[name][field], after[name][field]
                if a == b:
                    continue
                if not (a and b and math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-10)):
                    mismatches.append(f"{name}.{field}: {a} != {b}")
        old_matrices = json.loads((ROOT / "results/synthetic/evaluation_report.json").read_text(encoding="utf-8"))["confusion_matrices"]
        new_matrices = json.loads((output / "evaluation_report.json").read_text(encoding="utf-8"))["confusion_matrices"]
        if old_matrices != new_matrices:
            mismatches.append("confusion matrices differ")
        old_split = json.loads((ROOT / "results/split_manifest.json").read_text(encoding="utf-8"))
        new_split = json.loads((scratch / "results/split_manifest.json").read_text(encoding="utf-8"))
        if old_split != new_split:
            mismatches.append("participant split differs")
    result = {"status": "PASS" if not mismatches else "FAIL", "source_kind": "synthetic",
              "models_checked": sorted(before), "fields_checked": list(fields),
              "latency_excluded_from_deterministic_comparison": True, "mismatches": mismatches}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
