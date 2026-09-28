#!/usr/bin/env bash
# Daily Postgres backup, run ON THE EC2 HOST ITSELF via cron (not locally).
# Deployed to ~/backup_db.sh on EC2 and scheduled with:
#   crontab: 0 20 * * * /home/ec2-user/backup_db.sh >> /home/ec2-user/backup.log 2>&1
#   (20:00 UTC = 04:00 Asia/Taipei; server clock is UTC)
# Keeps the last 14 days of dumps under ~/backups.
set -euo pipefail

BACKUP_DIR="$HOME/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILE="$BACKUP_DIR/appdb_$TIMESTAMP.sql.gz"

sudo docker exec postgres_prod pg_dump -U appuser -d appdb --no-owner | gzip > "$FILE"

# Keep only the last 14 backups
ls -1t "$BACKUP_DIR"/appdb_*.sql.gz | tail -n +15 | xargs -r rm -f

echo "Backup written to $FILE"
