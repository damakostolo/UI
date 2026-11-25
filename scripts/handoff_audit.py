#!/usr/bin/env python3
"""Capture actual command outcomes in thesis_handoff without modifying application logic."""
from __future__ import annotations

import csv
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "thesis_handoff"
TESTS = HANDOFF / "05_tests"
LOGS = TESTS / "raw_logs"
LOGS.mkdir(parents=True, exist_ok=True)
(HANDOFF / "01_project").mkdir(parents=True, exist_ok=True)


def redact(value: str) -> str:
    return value.replace(str(Path.home()), "<USER_HOME>").replace(str(Path.home()).replace("\\", "/"), "<USER_HOME>")


def stamp():
    moment = datetime.now(timezone.utc)
    return moment.isoformat(), moment.astimezone().isoformat()


def run(name: str, argv: list[str], cwd: Path = ROOT, timeout: int = 300) -> dict:
    started_utc, started_local = stamp()
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        code, out, err = result.returncode, result.stdout, result.stderr
        status = "PASS" if code == 0 else "FAIL"
    except FileNotFoundError as exc:
        code, out, err, status = "", "", str(exc), "BLOCKED"
    except subprocess.TimeoutExpired as exc:
        code, out, err, status = "", (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""), str(exc), "FAIL"
    ended_utc, ended_local = stamp()
    stdout = LOGS / f"{name}.stdout.txt"
    stderr = LOGS / f"{name}.stderr.txt"
    stdout.write_text(redact(out), encoding="utf-8")
    stderr.write_text(redact(err), encoding="utf-8")
    print(f"{name}: {status} ({code})")
    return {"name": name, "command": redact(" ".join(argv)), "status": status, "exit_code": code,
            "started_utc": started_utc, "ended_utc": ended_utc,
            "started_local": started_local, "ended_local": ended_local,
            "os": platform.platform(), "stdout_log": stdout.relative_to(HANDOFF).as_posix(),
            "stderr_log": stderr.relative_to(HANDOFF).as_posix()}


def main():
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    commands = [
        ("pytest", [sys.executable, "-m", "pytest", "-q"], ROOT, 180),
        ("input_bundle", [sys.executable, "scripts/validate_input_bundle.py"], ROOT, 60),
        ("deliverables_report", [sys.executable, "scripts/check_deliverables.py"], ROOT, 60),
        ("deliverables_strict", [sys.executable, "scripts/check_deliverables.py", "--strict"], ROOT, 60),
        ("frontend_typecheck", [npm, "run", "typecheck"], ROOT / "frontend", 120),
        ("frontend_unit", [npm, "test"], ROOT / "frontend", 120),
        ("frontend_build", [npm, "run", "build"], ROOT / "frontend", 180),
        ("browser_e2e", [sys.executable, "tests/e2e_browser.py"], ROOT, 180),
        ("synthetic_repro", [sys.executable, "scripts/handoff_reproducibility.py"], ROOT, 240),
        ("docker_config", ["docker", "compose", "config", "--quiet"], ROOT, 60),
    ]
    rows = [run(*item) for item in commands]
    with (TESTS / "commands_and_status.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    packages = ("fastapi", "pydantic", "SQLAlchemy", "pandas", "numpy", "scikit-learn", "matplotlib", "xgboost", "pytest", "playwright", "jsonschema")
    versions = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "NOT_AVAILABLE"
    runtime = {"captured_utc": stamp()[0], "os": platform.platform(), "python": sys.version.split()[0],
               "cpu": platform.processor(), "logical_cpus": os.cpu_count(), "packages": versions,
               "node": subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip(),
               "npm": subprocess.run([npm, "--version"], capture_output=True, text=True).stdout.strip(),
               "commands": len(rows)}
    (HANDOFF / "01_project/run_environment.json").write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"PASS": sum(r["status"] == "PASS" for r in rows), "FAIL": sum(r["status"] == "FAIL" for r in rows),
                      "BLOCKED": sum(r["status"] == "BLOCKED" for r in rows)}))


if __name__ == "__main__":
    main()
