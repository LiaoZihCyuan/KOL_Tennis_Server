#!/usr/bin/env bash
# Deploy the latest pushed code (origin/main) to the AWS EC2 production host.
# Run this from your local machine after `git push`.
set -euo pipefail

EC2_HOST="ec2-user@ec2-3-239-229-97.compute-1.amazonaws.com"
EC2_KEY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/koltennis_key.pem"
REMOTE_DIR="~/app"
COMPOSE_FILE="docker-compose.prod.yml"

echo "==> Pulling latest code on EC2..."
ssh -i "$EC2_KEY" "$EC2_HOST" "cd $REMOTE_DIR && git pull origin main"

echo "==> Rebuilding and restarting containers..."
ssh -i "$EC2_KEY" "$EC2_HOST" "cd $REMOTE_DIR && sudo docker compose -f $COMPOSE_FILE up -d --build"

echo "==> Running database migrations..."
ssh -i "$EC2_KEY" "$EC2_HOST" "cd $REMOTE_DIR && sudo docker compose -f $COMPOSE_FILE exec -T api flask db upgrade"

echo "==> Health check..."
ssh -i "$EC2_KEY" "$EC2_HOST" "curl -sS -o /dev/null -w 'HTTP %{http_code}\n' http://localhost/"

echo "==> Deploy complete."
