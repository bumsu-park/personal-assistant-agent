#!/bin/bash
set -e  # Exit on error

echo "=== Building ARM64 image ==="
docker build -t bspark2318/task-agent:arm64 --platform linux/arm64 .

echo "=== Pushing to Docker Hub ==="
docker push bspark2318/task-agent:arm64

echo "=== Deploying to Raspberry Pi ==="
ssh pi@192.168.1.234 << 'EOF'
cd /home/pi/Deployment/personal-agent

echo "Pulling new image..."
docker pull bspark2318/task-agent:arm64

echo "Restarting services..."
ENVIRONMENT=prod docker compose up -d --force-recreate

echo "Services started. Showing logs..."
docker compose logs --tail 50
EOF
