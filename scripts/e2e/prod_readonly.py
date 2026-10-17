"""READ-ONLY Playwright session against PRODUCTION, for post-deploy checks.

Approved by the user as a standing procedure (2026-10-17); see CLAUDE.md
「部署後的 production 唯讀驗證」. Runs on the local machine, installs nothing on EC2.

Safety:
  - Every browser request that is not GET/HEAD/OPTIONS is ABORTED, except the
    single login POST. Saving/deleting/adding in the UI therefore cannot reach
    the server. Blocked attempts are listed in s.blocked.
  - Every confirm()/alert() dialog is dismissed (Cancel).
  - Never use page.request / APIRequestContext for anything but GET: it bypasses
    the route guard.
  - Credentials come from ~/.kol_prod_verify and are never printed.

Usage:
    import sys; sys.path.insert(0, "scripts/e2e")
    from prod_readonly import prod_session
    with prod_session("name", mobile=False) as s:
        s.page.goto(s.url("/templates")); s.shot("templates")
"""
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://ec2-3-239-229-97.compute-1.amazonaws.com"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "e2e_artifacts"
MOBILE = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _creds():
    vals = {}
    for line in (Path.home() / ".kol_prod_verify").read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals["PROD_VERIFY_USER"], vals["PROD_VERIFY_PASS"]


class Session:
    def __init__(self, page, out_dir):
        self.page, self.out_dir = page, out_dir
        self.problems, self.blocked = [], []
        self.login_done = False

    def url(self, path):
        return BASE_URL + path

    def shot(self, name, full_page=True):
        path = self.out_dir / f"{name}.png"
        self.page.screenshot(path=str(path), full_page=full_page)
        print(f"screenshot: {path.relative_to(ROOT)}")
        return path


@contextmanager
def prod_session(name, mobile=False):
    run_dir = OUT / f"{datetime.now():%Y%m%d_%H%M%S}_prod_{re.sub(r'[^\w-]', '_', name)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    user, password = _creds()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(locale="zh-TW", timezone_id="Asia/Taipei", **(MOBILE if mobile else {}))
        page = context.new_page()
        s = Session(page, run_dir)

        def guard(route, request):
            is_login = request.method == "POST" and request.url.endswith("/api/auth/login") and not s.login_done
            if request.method in SAFE_METHODS or is_login:
                route.continue_()
            else:
                s.blocked.append(f"{request.method} {request.url}")
                route.abort()

        context.route("**/*", guard)
        page.on("dialog", lambda d: d.dismiss())
        page.on("console", lambda m: m.type == "error" and s.problems.append(f"console: {m.text}"))
        page.on("pageerror", lambda e: s.problems.append(f"pageerror: {e}"))
        page.on("response", lambda r: r.status >= 500 and s.problems.append(f"HTTP {r.status} {r.url}"))
        try:
            page.goto(s.url("/login"))
            page.fill("#identifier", user)
            page.fill("#password", password)
            page.click("#submitBtn")
            page.wait_for_url(re.compile(r".*/(calendar|student/portal)$"), timeout=15_000)
            s.login_done = True
            page.wait_for_load_state("networkidle")
            yield s
        finally:
            context.close()
            browser.close()
