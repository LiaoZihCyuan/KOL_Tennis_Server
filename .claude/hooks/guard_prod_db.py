#!/usr/bin/env python3
"""PreToolUse hook: guard the production database on EC2.

Production holds live data entered by coaches and cannot be recreated, so:
  - catastrophic, data-destroying commands against prod are denied outright
    (the user can still run them by hand with `!` if truly needed);
  - anything that writes to prod (DB writes, migrations, deploys, restarts,
    file changes) requires the user's explicit confirmation, even though
    plain `ssh` to the host is on the allow list.
Commands that don't touch production pass through untouched.
"""
import json
import re
import sys

PROD_MARKERS = re.compile(
    r"ec2-3-239-229-97|postgres_prod|flask_api_prod|docker-compose\.prod|scripts/deploy\.sh",
    re.IGNORECASE,
)

DENY = [
    (r"docker\s+volume\s+(rm|prune)", "removes Docker volumes (pgdata holds the prod DB)"),
    (r"docker\s+system\s+prune", "prunes Docker data, may include the prod DB volume"),
    (r"\bdown\b[^;&|]*(\s-v\b|--volumes)", "`compose down -v` deletes the prod DB volume"),
    (r"\bdrop\s+(database|schema|table)\b", "drops prod database objects"),
    (r"\bdropdb\b", "drops the prod database"),
    (r"\btruncate\b", "truncates prod tables"),
    (r"\brm\b[^;&|]*(backups|pgdata|/var/lib/docker)", "deletes prod backups or DB files"),
    (r"e2e", "runs E2E test tooling (creates test accounts) against prod"),
]

ASK = [
    (r"scripts/deploy\.sh", "deploy (rebuilds containers and runs migrations)"),
    (r"flask\s+db\s+(upgrade|downgrade|stamp|migrate)", "changes the prod DB schema"),
    (r"\b(insert|update|delete|alter|create|grant|revoke)\b", "SQL that writes to prod"),
    (r"\bpg_restore\b|psql[^;&|]*(\s-f\s|<)", "loads SQL into the prod DB"),
    (r"docker\s+(compose\s+)?[^;&|]*\b(restart|stop|kill|rm|down|up)\b", "restarts/stops prod containers"),
    (r"\bgit\s+(pull|reset|checkout|clean)\b", "changes prod code"),
    (r"\bcrontab\b", "changes the prod cron (backups)"),
    (r"\brm\s", "deletes files on prod"),
    (r"\b(yum|dnf)\b", "changes system packages on prod"),
]

REMINDER = (
    "Production DB holds live coach data that cannot be recreated. "
    "Before any write: confirm a fresh backup exists "
    "(ssh ... '~/backup_db.sh && ls -lh ~/backups | tail -3'), "
    "and explain to the user exactly what will change."
)


def decide(command: str):
    if not PROD_MARKERS.search(command):
        return None
    for pattern, why in DENY:
        if re.search(pattern, command, re.IGNORECASE):
            return "deny", (
                f"Blocked: this {why}. This is never done by Claude; "
                "if truly required, the user must run it themselves with `!`."
            )
    for pattern, why in ASK:
        if re.search(pattern, command, re.IGNORECASE):
            return "ask", f"Production write: {why}. {REMINDER}"
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    command = (data.get("tool_input") or {}).get("command") or ""
    result = decide(command)
    if result is None:
        return
    decision, reason = result
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
