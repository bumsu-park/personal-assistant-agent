# CI/CD Automation Roadmap

## Step 1: CI Pipeline — Lint + Test on Push

Add a GitHub Actions workflow that runs `ruff check` and `pytest` on every push to `main` and `claude/**` branches. This is the foundation — nothing else matters if you can't gate on green CI.

```yaml
# .github/workflows/ci.yml
name: CI
on:
  push:
    branches: [main, "claude/**"]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: ruff check src/ tests/
      - run: pytest --tb=short -q
```

---

## Step 2: AI Code Review on PR Open ✅

Add CodeRabbit or the Claude Code GitHub Action to auto-review every PR. Posts inline comments on issues it finds.

**Option A — CodeRabbit** (zero config, free for OSS):
Install from GitHub Marketplace. It reviews PRs automatically on open.

**Option B — Claude Code Action** (more control):
```yaml
- name: Claude Code Review
  run: |
    claude -p "Review this PR diff for bugs, security issues, and style violations per CLAUDE.md. Output findings as JSON." \
      --output-format json \
      --allowedTools Read \
      --max-turns 5
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

---

## Step 3: Claude Code Headless — Auto-fix Failing CI

When CI fails, trigger Claude to attempt an auto-fix. It reads the failure, edits code, commits, and pushes.

```yaml
# .github/workflows/autofix.yml
on:
  workflow_run:
    workflows: [CI]
    types: [completed]

jobs:
  autofix:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Auto-fix
        run: |
          claude -p "The CI failed. Read the test output, fix the issue, and commit." \
            --allowedTools Read,Write,Shell \
            --max-turns 10
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

**Key flags:**
- `claude -p "prompt"` — one-shot headless mode, no human in the loop
- `--output-format json` — machine-readable output for piping into other steps
- `--allowedTools` — restrict capabilities (e.g. read-only for review, full for fixes)
- `--max-turns` — cap agentic loops to control cost and prevent runaway

---

## Step 4: Issue-to-PR Automation

Label a GitHub issue with `claude` and have it implemented automatically.

```yaml
# .github/workflows/implement-issue.yml
on:
  issues:
    types: [labeled]

jobs:
  implement:
    if: contains(github.event.label.name, 'claude')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Implement issue
        run: |
          claude -p "Read issue #${{ github.event.issue.number }}. \
            Create branch claude/issue-${{ github.event.issue.number }}, \
            implement the feature, write tests, commit, and open a PR." \
            --allowedTools Read,Write,Shell \
            --max-turns 20
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## Step 5: Guardrails + Cost Control

Before scaling any of the above:

- **Required human approval on merge** — never auto-merge to main for critical repos
- **Budget caps** — set `--max-turns` conservatively; monitor token usage per run
- **Scope tasks tightly** — "fix the flaky test in test_commands.py" >> "improve the codebase"
- **Restrict tools** — use `--allowedTools Read` for review-only steps
- **Audit trail** — Claude Code outputs are deterministic enough to `git log` but add `--output-format json` logging for post-hoc review

---

## Step 6: Cursor Background Agents (Alternative Path)

Cursor now offers background agents that run in the cloud. They can:
- Pick up GitHub issues
- Create branches, write code, run tests
- Open PRs autonomously

This is a managed alternative to self-hosting Claude Code in CI — less infra, but less control.

---

## Quick Reference: Claude Code CLI

| Flag | Purpose |
|------|---------|
| `-p "prompt"` | One-shot headless mode |
| `--output-format json` | Machine-readable output |
| `--allowedTools` | Restrict capabilities |
| `--max-turns N` | Cap agentic loop iterations |

Docs: https://docs.anthropic.com/en/docs/claude-code
