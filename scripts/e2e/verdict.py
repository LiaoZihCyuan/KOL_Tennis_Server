"""Track whether the current uncommitted app changes were verified.

    python3 scripts/e2e/verdict.py state                 # fingerprint of current changes
    python3 scripts/e2e/verdict.py record PASS "notes"   # verifier agent only
    python3 scripts/e2e/verdict.py record FAIL "notes"
    python3 scripts/e2e/verdict.py check                 # exit 0 if current changes have a PASS

The fingerprint covers uncommitted changes to app files only; any further edit
after a PASS changes it, so a stale PASS never counts.
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / ".claude" / "verification" / "verdicts.jsonl"
IGNORED_PREFIXES = (".claude/", "e2e_artifacts/", "issues/", "document/", "scripts/", ".gitignore")


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def changed_app_files():
    files = set(_git("diff", "HEAD", "--name-only").split())
    files |= set(_git("ls-files", "--others", "--exclude-standard").split())
    return sorted(f for f in files if not f.startswith(IGNORED_PREFIXES) and not f.endswith(".md"))


def state():
    files = changed_app_files()
    if not files:
        return None
    h = hashlib.sha256()
    for f in files:
        p = ROOT / f
        h.update(f.encode() + b"\0" + (p.read_bytes() if p.is_file() else b"<deleted>") + b"\0")
    return h.hexdigest()[:16]


def latest_verdict(fingerprint):
    if not LOG.exists():
        return None
    verdict = None
    for line in LOG.read_text().splitlines():
        entry = json.loads(line)
        if entry["state"] == fingerprint:
            verdict = entry["verdict"]
    return verdict


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "state"
    fp = state()
    if cmd == "state":
        print(fp or "clean", *changed_app_files(), sep="\n")
    elif cmd == "record":
        verdict, notes = sys.argv[2].upper(), " ".join(sys.argv[3:])
        assert verdict in ("PASS", "FAIL"), "verdict must be PASS or FAIL"
        if fp is None:
            sys.exit("No uncommitted app changes to record a verdict for.")
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(json.dumps({"state": fp, "verdict": verdict, "notes": notes,
                                "at": datetime.now().isoformat(timespec="seconds")},
                               ensure_ascii=False) + "\n")
        print(f"recorded {verdict} for {fp}")
    elif cmd == "check":
        sys.exit(0 if fp is None or latest_verdict(fp) == "PASS" else 1)


if __name__ == "__main__":
    main()
