# CD Auto-Deploy Pipeline

## Goal
Enable remote deployment without SSH access to the Pi. Push to `main` → CI builds ARM64 image → pushes to Docker Hub → Watchtower on Pi auto-pulls and restarts containers.

## Affected Files
- `.github/workflows/ci.yml` — add `build-and-push` job after tests pass on `main`
- `docker-compose.yml` — add Watchtower service

## Approach
1. **GitHub Actions CD job**: builds ARM64 Docker image via QEMU + buildx, pushes to Docker Hub. Only runs on push to `main` (not PRs or `claude/**`).
2. **Watchtower**: runs on the Pi, polls Docker Hub every 5 minutes, auto-pulls new images and recreates containers.

## Risks
- Docker Hub credentials must be stored as GitHub Secrets (`DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`).
- Watchtower can't sync `docker-compose.yml` changes — those still require manual `deploy.sh`. This is acceptable since compose changes are rare.
- QEMU cross-compilation is slower than native ARM builds (~5-10 min).
