Goal: Rename FastAPI auth env var from `API_KEY` to `FASTAPI_KEY` for clarity.

Affected files: `src/core/config.py`, `main.py`, `env.example`.

Approach: Replace config field/env lookup to `FASTAPI_KEY` and pass through to API app creation; update env template key name to match runtime.

Risks: Existing deployments using `API_KEY` will need env update (breaking rename if old key is left unchanged).
