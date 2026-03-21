#!/bin/bash
set -e  # Exit on error

echo "=== Building ARM64 image ==="
docker build -t bspark2318/task-agent:arm64 --platform linux/arm64 .

echo "=== Pushing to Docker Hub ==="
docker push bspark2318/task-agent:arm64

echo "=== Deploying to Raspberry Pi ==="
ssh pi@192.168.1.234 << 'EOF'
echo "Pulling new image..."
docker pull bspark2318/task-agent:arm64

echo "Stopping old container..."
docker stop task-agent || true
docker rm task-agent || true

echo "Starting new container..."
docker run -d \
  --name task-agent \
  --restart unless-stopped \
  --env-file /home/pi/Deployment/personal-agent/.env.prod \
  -v /home/pi/Deployment/personal-agent/gmail_credentials.json:/app/gmail_credentials.json:ro \
  bspark2318/task-agent:arm64

echo "Container started. Showing logs..."
docker logs --tail 50 task-agent
EOF
