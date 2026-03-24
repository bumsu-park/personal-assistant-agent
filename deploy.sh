#!/bin/bash
set -e  # Exit on error

echo "=== Building ARM64 image ==="
docker build -t bspark2318/task-agent:arm64 --platform linux/arm64 .

echo "=== Pushing to Docker Hub ==="
docker push bspark2318/task-agent:arm64

echo "=== Syncing config to Raspberry Pi ==="
scp docker-compose.yml pi@192.168.1.234:/home/pi/Deployment/personal-agent/

echo "=== Deploying to Raspberry Pi ==="
ssh pi@192.168.1.234 'cd /home/pi/Deployment/personal-agent && \
  grep -q "^ENVIRONMENT=prod$" .env.prod || echo "ENVIRONMENT=prod" >> .env.prod; \
  mkdir -p data/prod; \
  sudo chown -R 1000:1000 data; \
  sudo chmod -R u+rwX data; \
  docker stop task-agent-prod cloudflared-prod 2>/dev/null; \
  docker rm task-agent-prod cloudflared-prod 2>/dev/null; \
  docker pull bspark2318/task-agent:arm64 && \
  ENVIRONMENT=prod docker compose up -d --force-recreate && \
  docker image prune -f'
