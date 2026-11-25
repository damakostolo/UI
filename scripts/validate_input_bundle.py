#!/usr/bin/env python3
"""Verify this starter's inputs only; does not imply the application was built."""
import csv, json, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
required = [
    'README.md', 'AGENTS.md', 'START_HERE_CODEX.md',
    'context/Plan_magisterska_UI_ML.docx',
    'context/Magisterska_UI_ML_Referat_Vstup_Rozdil1.docx',
    'docs/SPECIFICATION.md', 'docs/EXPERIMENT_PROTOCOL.md',
    'docs/DATA_AND_CONSENT.md', 'docs/OUTPUTS_FOR_THESIS.md',
    'docs/ARCHITECTURE_AND_API.md', 'docs/ACCEPTANCE_TESTS.md',
    'docs/BIBLIOGRAPHY_HANDOFF.md', 'docs/MATH_MODEL.md',
    'contracts/events.schema.json', 'contracts/trials.schema.json',
    'contracts/preference_labels.schema.json', 'contracts/prediction.schema.json',
    'data/sample_synthetic/feature_rows.csv','data/sample_synthetic/dataset_manifest.json'
]
for file in required:
    path = ROOT/file
    assert path.exists() and path.stat().st_size, f'Missing or empty: {file}'
    if file.endswith('.docx'):
        assert zipfile.is_zipfile(path), f'Invalid DOCX: {file}'
for f in (ROOT/'contracts').glob('*.json'):
    schema=json.loads(f.read_text(encoding='utf8'))
    assert schema['type']=='object' and 'properties' in schema, f'Bad schema: {f}'
with (ROOT/'data/sample_synthetic/feature_rows.csv').open(encoding='utf8', newline='') as f:
    rows=list(csv.DictReader(f))
assert len(rows)>=100
assert all(r['source']=='synthetic' and r['is_synthetic']=='true' for r in rows)
assert len(set(r['participant_id'] for r in rows))>=50
manifest=json.loads((ROOT/'data/sample_synthetic/dataset_manifest.json').read_text(encoding='utf8'))
assert manifest['source']=='synthetic' and manifest['is_synthetic']
assert manifest['n_sessions']==len(rows)
print(f'STARTER INPUTS PASS: {len(required)} required inputs; {len(rows)} clearly synthetic sample records; no real UX dataset.')
