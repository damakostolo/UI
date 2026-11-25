#!/usr/bin/env python3
"""DEMO ONLY: synthetic feature rows and generated preferences, never real users."""
from __future__ import annotations
import argparse, csv, json, random
from pathlib import Path
from datetime import datetime, timezone, timedelta


def generate(n_participants=120, per_participant=3, seed=20261103, output=Path("data/sample_synthetic")):
    randomizer = random.Random(seed)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    counts = {"standard":0,"compact":0,"focus":0}
    for pi in range(n_participants):
        participant = f"syn_{pi:05d}"
        # Artificial latent preference is deliberately learned from simulated behavior.
        # THIS CAN NOT ESTABLISH UX GAINS OR PERFORMANCE ON REAL USERS.
        base = randomizer.choice(["standard","compact","focus"])
        for si in range(per_participant):
            ts = datetime(2026,10,1,tzinfo=timezone.utc) + timedelta(hours=pi*5+si)
            # Coherent but fabricated relationship for software smoke-testing.
            tasks = randomizer.randint(1,12) + (6 if base=="focus" else 0)
            reports = randomizer.randint(0,9) + (4 if base=="standard" else 0)
            quick = randomizer.randint(0,11) + (5 if base=="compact" else 0)
            label = base if randomizer.random()>0.12 else randomizer.choice(["standard","compact","focus"])
            counts[label] += 1
            rows.append({
                "participant_id":participant,"session_id":f"{participant}_{si}",
                "decision_at":ts.isoformat(),"observed_until":(ts-timedelta(seconds=1)).isoformat(),
                "opens_tasks_7d":tasks,"opens_reports_7d":reports,"quick_actions_7d":quick,
                "avg_actions_per_session_7d":round(randomizer.uniform(3,15),2),
                "active_sessions_7d":randomizer.randint(2,6),
                "last_device_category":randomizer.choice(["desktop","tablet","mobile"]),
                "last_viewport_category":randomizer.choice(["small","medium","large"]),
                "time_of_day_bin":randomizer.choice(["morning","day","evening"]),
                "prior_undo_rate":round(randomizer.uniform(0,0.25),3),
                "current_layout":"standard","preferred_layout":label,
                "label_source":"synthetic_generator","source":"synthetic", "is_synthetic":"true",
                "consent_version":"demo-synthetic"})
    with (output/"feature_rows.csv").open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    metadata={"source":"synthetic","is_synthetic":True,"n_participants":n_participants,
              "n_sessions":len(rows),"seed":seed,"class_counts":counts,
              "warning":"СИНТЕТИЧНІ ДАНІ. НЕ ДОКАЗ ЕФЕКТИВНОСТІ СЕРЕД РЕАЛЬНИХ КОРИСТУВАЧІВ."}
    (output/"dataset_manifest.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(metadata, ensure_ascii=False, indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--participants",type=int,default=120)
    p.add_argument("--sessions",type=int,default=3); p.add_argument("--seed",type=int,default=20261103)
    p.add_argument("--output",type=Path,default=Path("data/sample_synthetic"))
    a=p.parse_args(); generate(a.participants,a.sessions,a.seed,a.output)
