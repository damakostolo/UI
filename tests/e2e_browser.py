"""Real headless Chrome smoke test and screenshots of the running UI."""
from __future__ import annotations

import subprocess
import os
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def wait_url(url: str):
    for _ in range(100):
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200: return
        except Exception: time.sleep(.2)
    raise RuntimeError(f"Server not ready: {url}")


def main():
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    db_path = ROOT / "tests/.e2e.sqlite3"
    db_path.unlink(missing_ok=True)
    backend = subprocess.Popen(["python", "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "18001", "--no-access-log"], cwd=ROOT,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags,
                               env={**os.environ, "DATABASE_URL":"sqlite:///./tests/.e2e.sqlite3"})
    frontend = subprocess.Popen(["npm", "run", "dev", "--", "--port", "15174", "--strictPort"], cwd=ROOT / "frontend", stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, shell=True, creationflags=flags,
                                env={**os.environ, "VITE_API_URL":"http://127.0.0.1:18001/api/v1"})
    try:
        wait_url("http://127.0.0.1:18001/api/v1/health"); wait_url("http://127.0.0.1:15174")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(CHROME))
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            event_posts = []
            page.on("request", lambda r: event_posts.append(r) if r.method == "POST" and "/events" in r.url else None)
            page.goto("http://127.0.0.1:15174", wait_until="networkidle")
            assert page.get_by_role("heading", name="Робоча панель").is_visible()
            assert page.locator(".card").count() == 6
            page.keyboard.press("Tab")
            assert page.locator(":focus").get_attribute("class") == "skip"
            page.keyboard.press("Enter")
            assert page.evaluate("location.hash") == "#main"
            page.get_by_test_id("open-tasks").click()
            assert not event_posts, "Consent-off click sent an event"
            screenshots = ROOT / "results/screenshots"; screenshots.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshots / "dashboard_standard.png"), full_page=True)
            page.locator("#layout").select_option("focus")
            assert page.locator(".card").count() == 6
            page.screenshot(path=str(screenshots / "dashboard_focus.png"), full_page=True)
            page.locator("#layout").select_option("standard")
            page.get_by_role("button", name="Надати згоду на події").click()
            page.get_by_role("button", name="Відкликати згоду").wait_for()
            page.locator("#mode").select_option("rule")
            for _ in range(8):
                with page.expect_response(lambda r: r.url.endswith("/events") and r.request.method == "POST"):
                    page.get_by_test_id("open-quick_actions").click()
            page.get_by_role("button", name="Отримати пропозицію").click()
            page.get_by_role("button", name="Підтвердити зміну").wait_for()
            assert page.locator(".preview li").count() == 6
            page.keyboard.press("Escape")
            page.get_by_role("button", name="Підтвердити зміну").wait_for(state="detached")
            page.get_by_role("button", name="Отримати пропозицію").click()
            page.get_by_role("button", name="Підтвердити зміну").wait_for()
            assert page.locator(".app").get_attribute("class").find("layout-standard") >= 0
            page.get_by_role("button", name="Підтвердити зміну").click()
            page.locator(".app.layout-compact").wait_for()
            page.get_by_role("button", name="Скасувати зміну").click()
            page.locator(".app.layout-standard").wait_for()
            page.get_by_role("button", name="Відкликати згоду").click()
            n = len(event_posts)
            page.get_by_test_id("open-tasks").click()
            assert len(event_posts) == n, "Post-revocation click sent an event"
            page.get_by_role("button", name="Видалити профіль").click()
            page.get_by_role("button", name="Надати згоду на події").wait_for()
            browser.close()
        print("E2E PASS: keyboard Tab/Enter/Escape, consent-off, six widgets, focus, preview, rule proposal, accept, undo, revoke, delete")
    finally:
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(frontend.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            frontend.terminate()
        backend.terminate()
        backend.wait(timeout=5)
        db_path.unlink(missing_ok=True)


if __name__ == "__main__": main()
