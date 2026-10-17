"""Baseline smoke test: every page loads for each role, desktop and mobile,
with no console errors, page errors, or 5xx responses.

    python3 scripts/e2e/smoke.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import ensure_users, session  # noqa: E402

PAGES = {
    "admin": ["/calendar", "/users", "/add_user", "/coaches/stats", "/students/stats",
              "/templates", "/renewals/manage"],
    "coach": ["/calendar"],
    "student": ["/student/portal"],
}


def main():
    ensure_users()
    failures = []
    for mobile in (False, True):
        for role, paths in PAGES.items():
            label = f"smoke_{role}_{'mobile' if mobile else 'desktop'}"
            try:
                with session(role, label, mobile=mobile) as s:
                    for path in paths:
                        s.page.goto(s.url(path))
                        s.page.wait_for_load_state("networkidle")
                        s.shot(path.strip("/").replace("/", "_") or "root")
                print(f"PASS {label}")
            except Exception as e:  # keep going so one run reports everything
                failures.append(f"{label}: {e}")
                print(f"FAIL {label}: {e}")
    if failures:
        sys.exit("\nSMOKE FAILED:\n" + "\n".join(failures))
    print("\nSMOKE PASSED")


if __name__ == "__main__":
    main()
