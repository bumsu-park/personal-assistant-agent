# Claude Code — Project Instructions

## Workflow: Every Task Must Follow This Pipeline

### 1. PLAN (before writing any code)
- Create or update a plan file at `.claude/plans/<branch-name>.md`
- Plan must include: goal, affected files, approach, risks
- For small fixes, a 2-3 line summary is fine; for features, be thorough
- Reference existing code patterns — check `src/core/` for conventions

### 2. CODE (implement on a feature branch)
- Always work on a branch: `claude/<descriptive-slug>`
- Follow existing patterns: plugin architecture in `src/plugins/`, core in `src/core/`
- Write or update tests in `tests/` for any logic changes
- Keep commits atomic — one logical change per commit

### 3. REVIEW (before submitting)
- Run `ruff check src/ tests/` and fix all lint errors
- Run `pytest --tb=short -q` and ensure all tests pass
- Self-review: re-read the diff (`git diff main...HEAD`) and check for:
  - Unused imports or dead code
  - Missing error handling
  - Hardcoded secrets or config
  - Breaking changes to existing APIs

### 4. SUBMIT (create PR)
- Push branch and create PR with the plan as the PR body
- PR title format: `<type>: <short description>` (feat, fix, refactor, docs, test, chore)
- Ensure CI passes before requesting review

---

## Code Conventions

- **Python 3.11**, type hints everywhere
- **Async-first**: use `async def` for I/O-bound functions
- **Config**: environment variables via `src/core/config.py`, never hardcode
- **Plugins**: extend `BasePlugin` in `src/core/plugin.py`
- **Tests**: pytest + pytest-asyncio, mock external services
- **Linting**: ruff (see `ruff.toml`)
- **Imports**: stdlib → third-party → local, separated by blank lines

## Project Structure

```
src/
  core/       # Config, LLM, graph, API, state, memory, plugin base
  agents/     # Agent definitions (e.g. personal/)
  plugins/    # Plugin implementations (gmail/, calendar/)
tests/        # Mirrors src/ structure
```

## Deployment

- Docker → Raspberry Pi via `deploy.sh`
- CI runs on push to `main` and `claude/**` branches
- PRs to `main` trigger full pipeline (lint + test + review)
