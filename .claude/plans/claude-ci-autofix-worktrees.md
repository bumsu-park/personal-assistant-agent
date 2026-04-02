# CI Auto-fix with Git Worktrees

## Goal
Implement Step 3 of the CI automation roadmap: auto-fix failing CI using Claude Code headless mode. Use git worktrees for branch isolation, both in CI and locally for multi-agent workflows.

## Affected files
- `.github/workflows/autofix.yml` — new workflow triggered on CI failure
- `scripts/worktree-agent.sh` — local multi-agent worktree manager

## Approach
- **CI**: `workflow_run` trigger fires when "CI Pipeline" fails on a `claude/**` branch (never main). Creates a worktree on a fix branch, runs Claude headless with the failure log, pushes + opens PR back into the failing branch.
- **Local**: Shell script wraps `git worktree` commands for quick create/list/rm/run. The `run` subcommand creates a worktree and runs `claude -p` inside it — enabling parallel agent work without branch conflicts.

## Risks
- Claude may not fix the issue — workflow exits cleanly if no commits made
- Cost: capped at `--max-turns 15` (~$2-5 per run)
- Never auto-fixes main (guarded by branch filter)
- Requires `ANTHROPIC_API_KEY` secret in repo settings
