#!/usr/bin/env python3
"""Checks contract for Codex-generated results. Never fabricates missing files.

Usage: python scripts/check_deliverables.py [--root .] [--strict]
Default reports pending files; --strict fails if any mandatory output is missing.
"""
from __future__ import annotations
import argparse
import csv
import json
import hashlib
from pathlib import Path

REQUIRED_FILES = [
    'results/STATUS.md',
    'results/ARTIFACT_MANIFEST.json',
    'results/THESIS_TABLES_UA.md',
    'results/THESIS_FIGURES_UA.md',
    'results/EXPERIMENT_METHODS_UA.md',
    'results/LIMITATIONS_UA.md',
    'results/feature_dictionary.csv',
    'results/split_manifest.json',
    'results/config_snapshot.json',
    'results/test_results.json',
    'results/synthetic/dataset_card.md',
    'results/synthetic/dataset_summary.json',
    'results/synthetic/class_distribution.png',
    'results/synthetic/models_comparison.csv',
    'results/synthetic/models_comparison.png',
    'results/synthetic/evaluation_report.json',
    'results/synthetic/confusion_matrix.png',
    'results/synthetic/policy_metrics.csv',
    'results/synthetic/ablation.csv',
    'results/synthetic/ablation.png',
    'results/synthetic/system_benchmark.json',
    'docs/API.md',
    'docs/diagrams/activity_hybrid_policy.mmd',
    'docs/diagrams/component.mmd',
    'docs/diagrams/erd.mmd',
    'docs/diagrams/sequence_recommendation.mmd',
    'docs/diagrams/use_cases.mmd',
    'docs/DECISIONS.md',
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    missing = [p for p in REQUIRED_FILES if not (root/p).exists() or (root/p).stat().st_size == 0]
    print(f'Required evidence files: {len(REQUIRED_FILES)}; present: {len(REQUIRED_FILES)-len(missing)}')
    for p in missing:
        print(f'PENDING: {p}')
    issues = []
    manifest_path = root/'results/ARTIFACT_MANIFEST.json'
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf8'))
            if not isinstance(manifest, list) or not manifest:
                issues.append('ARTIFACT_MANIFEST.json must be a nonempty JSON list')
            else:
                for entry in manifest:
                    if not isinstance(entry, dict) or not {'path','source','is_synthetic','sha256'} <= set(entry):
                        issues.append(f'incomplete entry: {entry!r}'); continue
                    filepath = root/entry['path']
                    if not filepath.is_file():
                        issues.append(f'manifest path not found: {entry["path"]}'); continue
                    digest=hashlib.sha256(filepath.read_bytes()).hexdigest()
                    if entry['sha256'] != digest:
                        issues.append(f'bad SHA256: {entry["path"]}')
                    if 'results/synthetic/' in entry['path'] and not entry['is_synthetic']:
                        issues.append(f'synthetic incorrectly marked real: {entry["path"]}')
        except (ValueError, OSError) as e:
            issues.append(f'invalid manifest: {e}')
    feature_csv = root/'results/feature_dictionary.csv'
    if feature_csv.exists():
        with feature_csv.open(encoding='utf8',newline='') as f:
            r = csv.DictReader(f)
            if not {'feature','definition','available_at','missing_policy'} <= set(r.fieldnames or []):
                issues.append('feature_dictionary.csv required columns missing')
    split_path = root/'results/split_manifest.json'
    if split_path.exists():
        try:
            split=json.loads(split_path.read_text(encoding='utf8'))
            groups=[set(split[x]) for x in ('train_ids','validation_ids','test_ids')]
            if any(a & b for i,a in enumerate(groups) for b in groups[i+1:]):
                issues.append('participant leakage across splits')
            if not all(groups):
                issues.append('empty participant split')
        except (ValueError, KeyError, TypeError) as e:
            issues.append(f'invalid split manifest: {e}')
    comp = root/'results/synthetic/models_comparison.csv'
    if comp.exists():
        with comp.open(encoding='utf8',newline='') as f:
            r=csv.DictReader(f)
            fields=set(r.fieldnames or [])
            if not {'model','accuracy','macro_f1','source','is_synthetic'} <= fields:
                issues.append('models_comparison.csv missing required columns')
            else:
                for row in r:
                    if row['is_synthetic'].lower() not in ('true','1'):
                        issues.append('synthetic model comparison contains non-synthetic row')
    print('Contract issues: ' + (str(len(issues)) if issues else 'none identified'))
    for item in issues: print('ISSUE:',item)
    if issues or (missing and args.strict): return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
