#!/usr/bin/env bash
# Pull production data DOWN into your local dev database, for testing against
# real data. This OVERWRITES your local database — never run this the other
# way around (local -> prod), since prod now holds live data entered by coaches.
set -euo pipefail

EC2_HOST="ec2-user@ec2-3-239-229-97.compute-1.amazonaws.com"
EC2_KEY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/koltennis_key.pem"
DUMP_FILE="/tmp/prod_data_$(date +%Y%m%d_%H%M%S).sql"

read -p "This will OVERWRITE your local database with production data. Continue? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Aborted."
  exit 1
fi

echo "==> Dumping data from production..."
ssh -i "$EC2_KEY" "$EC2_HOST" "sudo docker exec postgres_prod pg_dump -U appuser -d appdb --data-only --disable-triggers --no-owner" > "$DUMP_FILE"

echo "==> Clearing local tables..."
docker exec postgres_dev psql -U appuser -d appdb -c "
TRUNCATE TABLE bookings, credit_transactions, notifications, renewal_requests, courses, course_templates, users RESTART IDENTITY CASCADE;
"

echo "==> Loading production data into local database..."
docker exec -i postgres_dev psql -U appuser -d appdb < "$DUMP_FILE"

rm -f "$DUMP_FILE"
echo "==> Done. Local database now mirrors production."
