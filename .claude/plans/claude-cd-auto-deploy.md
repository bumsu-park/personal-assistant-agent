# Move Gmail OAuth client JSON under `credentials/`

**Goal:** Keep `gmail_credentials.json` out of repo root; mount `/app/credentials/...` in Docker.

**Files:** `docker-compose.yml`, `.gitignore`, `.dockerignore`, `credentials/.gitkeep`. `env.example` already documents `credentials/gmail_credentials.json`.

**Risk:** Local `.env.*` must use `GMAIL_CREDENTIALS_PATH=credentials/gmail_credentials.json` and the file must live at `credentials/gmail_credentials.json` on disk.
