#!/bin/bash
set -e

PI_HOST="pi@192.168.1.234"
PI_DIR="/home/pi/Deployment/personal-agent"
CONTAINERS="task-agent-personal cloudflared-personal task-agent-business cloudflared-business"

echo "=== Building ARM64 image ==="
docker build -t bspark2318/task-agent:arm64 --platform linux/arm64 .

echo "=== Pushing to Docker Hub ==="
docker push bspark2318/task-agent:arm64

echo "=== Syncing config to Raspberry Pi ==="
scp docker-compose.yml "$PI_HOST:$PI_DIR/"

echo "=== Deploying to Raspberry Pi ==="
ssh "$PI_HOST" "cd $PI_DIR && \
  mkdir -p data/personal data/business; \
  sudo chown -R 1000:1000 data; \
  sudo chmod -R u+rwX data; \
  docker stop $CONTAINERS 2>/dev/null || true; \
  docker rm $CONTAINERS 2>/dev/null || true; \
  docker pull bspark2318/task-agent:arm64 && \
  docker compose up -d --force-recreate && \
  docker image prune -f"
