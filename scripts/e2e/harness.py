"""Playwright harness for verifying the LOCAL dev site (http://localhost:5000).

Used by the verifier agent. Task-specific checks go in e2e_artifacts/ (gitignored):

    import sys; sys.path.insert(0, "scripts/e2e")
    from harness import session, ensure_users

    ensure_users()
    with session("admin", "my-check") as s:          # logs in through the real form
        s.page.goto(s.url("/calendar"))
        s.shot("calendar")                            # -> e2e_artifacts/<run>/calendar.png
        assert s.page.get_by_text("...").is_visible()
    # leaving the block raises if the page logged console errors or got 5xx responses

Never point this at production: BASE_URL is pinned to localhost.
"""
import os
import re
import subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5000"
ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "e2e_artifacts"
PASSWORD = "e2e-pass-123"
ROLES = {"admin": "e2e_admin", "coach": "e2e_coach", "student": "e2e_student"}
LANDING = {"admin": "/calendar", "coach": "/calendar", "student": "/student/portal"}
MOBILE = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}


def ensure_users():
    """Create/reset the e2e_* accounts in the local dev DB."""
    subprocess.run(
        ["docker", "exec", "-e", "E2E_DEV_ONLY=1", "flask_api_dev",
         "python3", "scripts/e2e/ensure_e2e_users.py"],
        check=True,
    )


class Session:
    def __init__(self, page, out_dir):
        self.page = page
        self.out_dir = out_dir
        self.problems = []

    def url(self, path):
        return BASE_URL + path

    def shot(self, name, full_page=True):
        path = self.out_dir / f"{name}.png"
        self.page.screenshot(path=str(path), full_page=full_page)
        print(f"screenshot: {path.relative_to(ROOT)}")
        return path


@contextmanager
def session(role, name, mobile=False, login=True, headless=True):
    """Open a browser logged in as an e2e user; fail on console errors / 5xx / page errors."""
    run_dir = ARTIFACTS / f"{datetime.now():%Y%m%d_%H%M%S}_{re.sub(r'[^\w-]', '_', name)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="zh-TW", timezone_id="Asia/Taipei", **(MOBILE if mobile else {})
        )
        page = context.new_page()
        s = Session(page, run_dir)
        page.on("console", lambda m: m.type == "error" and s.problems.append(f"console: {m.text}"))
        page.on("pageerror", lambda e: s.problems.append(f"pageerror: {e}"))
        page.on("response", lambda r: r.status >= 500 and s.problems.append(f"HTTP {r.status} {r.url}"))
        try:
            if login:
                page.goto(s.url("/login"))
                page.fill("#identifier", ROLES[role])
                page.fill("#password", PASSWORD)
                page.click("#submitBtn")
                page.wait_for_url(f"**{LANDING[role]}", timeout=10_000)
                page.wait_for_load_state("networkidle")
            yield s
        except Exception:
            s.shot("FAILURE")
            raise
        finally:
            context.close()
            browser.close()
        if s.problems:
            raise AssertionError("Page problems:\n  " + "\n  ".join(s.problems))
