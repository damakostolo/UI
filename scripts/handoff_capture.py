#!/usr/bin/env python3
"""Capture real browser screens from an isolated, disposable local test session."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "thesis_handoff/04_implementation/screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DB = ROOT / "tests/.handoff_capture.sqlite3"


def wait_url(url: str) -> None:
    for _ in range(100):
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(.2)
    raise RuntimeError(f"Server not ready: {url}")


def main() -> None:
    if not CHROME.exists():
        raise RuntimeError("SCREENSHOTS_NOT_CAPTURED: Chrome executable unavailable")
    DB.unlink(missing_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "18001", "--no-access-log"],
                               cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags,
                               env={**os.environ, "DATABASE_URL": "sqlite:///./tests/.handoff_capture.sqlite3"})
    frontend = subprocess.Popen(["npm", "run", "dev", "--", "--port", "15174", "--strictPort"], cwd=ROOT / "frontend",
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True, creationflags=flags,
                                env={**os.environ, "VITE_API_URL": "http://127.0.0.1:18001/api/v1"})
    try:
        wait_url("http://127.0.0.1:18001/api/v1/health")
        wait_url("http://127.0.0.1:15174")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=str(CHROME))
            page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            page.goto("http://127.0.0.1:15174", wait_until="networkidle")

            def shot(name: str) -> None:
                page.screenshot(path=str(SCREENSHOTS / f"{name}.png"), full_page=True)

            shot("01_static_standard")
            page.locator("#layout").select_option("compact")
            shot("02_static_compact")
            page.locator("#layout").select_option("focus")
            shot("03_static_focus")
            page.locator("#layout").select_option("standard")
            page.get_by_role("button", name="Надати згоду на події").click()
            page.get_by_role("button", name="Відкликати згоду").wait_for()
            shot("04_consent_enabled_test")
            page.locator("#mode").select_option("rule")
            shot("05_rule_mode_test")
            for _ in range(8):
                with page.expect_response(lambda response: response.url.endswith("/events") and response.request.method == "POST" and response.status == 200):
                    page.get_by_test_id("open-quick_actions").click()
            with page.expect_response(lambda response: response.url.endswith("/recommendations") and response.request.method == "POST") as recommendation:
                page.get_by_role("button", name="Отримати пропозицію").click()
            first = recommendation.value.json()
            page.get_by_role("button", name="Підтвердити зміну").wait_for()
            shot("06_rule_proposal_preview_test")
            page.get_by_role("button", name="Відхилити").click()
            page.get_by_role("button", name="Підтвердити зміну").wait_for(state="detached")
            shot("07_rejected_test")
            page.get_by_role("button", name="Отримати пропозицію").click()
            page.get_by_role("button", name="Підтвердити зміну").wait_for()
            page.get_by_role("button", name="Підтвердити зміну").click()
            page.locator(".app.layout-compact").wait_for()
            shot("08_accepted_compact_test")
            page.get_by_role("button", name="Скасувати зміну").click()
            page.locator(".app.layout-standard").wait_for()
            shot("09_undo_standard_test")
            page.get_by_role("button", name="Відкликати згоду").click()
            shot("10_consent_revoked_test")
            page.get_by_role("button", name="Видалити профіль").click()
            page.get_by_role("button", name="Надати згоду на події").wait_for()
            browser.close()
        trace = {"captured_utc": datetime.now(timezone.utc).isoformat(), "source_kind": "synthetic",
                 "scenario": "Automated local clicks in disposable database; no human participant or UX outcome",
                 "mode": "rule", "predecision_quick_action_events": 8,
                 "current_layout": first["current_layout"], "proposed_layout": first["proposed_layout"],
                 "probabilities": first["probabilities"], "decision": first["decision"], "reasons": first["reasons"],
                 "accepted_after_second_request": True, "undo_observed": True,
                 "request_id_omitted": True, "participant_id_omitted": True}
        (ROOT / "thesis_handoff/02_research/policy_trace_synthetic.json").parent.mkdir(parents=True, exist_ok=True)
        (ROOT / "thesis_handoff/02_research/policy_trace_synthetic.json").write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Captured {len(list(SCREENSHOTS.glob('*.png')))} browser screenshots; isolated database removed")
    finally:
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(frontend.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            frontend.terminate()
        backend.terminate()
        backend.wait(timeout=5)
        DB.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
