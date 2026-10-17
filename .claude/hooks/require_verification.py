#!/usr/bin/env python3
"""Stop hook: don't hand work back while app changes are unverified.

If there are uncommitted app changes whose fingerprint has no PASS from the
verifier agent, block the stop once and tell Claude to run verification.
Blocks only once per stop (stop_hook_active), so Claude can still stop to ask
the user a question mid-task — but must then say verification is pending.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "e2e"))
import verdict  # noqa: E402


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        data = {}
    if data.get("stop_hook_active"):
        return
    fp = verdict.state()
    if fp is None or verdict.latest_verdict(fp) == "PASS":
        return
    files = ", ".join(verdict.changed_app_files()[:8])
    json.dump({
        "decision": "block",
        "reason": (
            f"Unverified app changes ({files}). Before handing work to the user: run the "
            "functional checks, then spawn the `verifier` agent (Playwright on the local site) "
            "and wait for its PASS. If you are only pausing to ask the user something, say "
            "explicitly that verification has not run yet."
        ),
    }, sys.stdout)


if __name__ == "__main__":
    main()
