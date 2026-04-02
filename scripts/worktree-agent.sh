#!/usr/bin/env bash
set -euo pipefail

# Multi-agent worktree manager
# Creates isolated git worktrees so multiple agents (Claude, Cursor, etc.)
# can work on separate branches simultaneously without conflicts.
#
# Usage:
#   ./scripts/worktree-agent.sh create <task-slug>   # spin up a worktree
#   ./scripts/worktree-agent.sh list                  # show active worktrees
#   ./scripts/worktree-agent.sh rm <task-slug>        # tear down a worktree
#   ./scripts/worktree-agent.sh run <task-slug> "prompt"  # create + run claude headless

REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_BASE="${REPO_ROOT}/../task_agent-worktrees"

_branch_name() {
    echo "claude/$1"
}

_worktree_dir() {
    echo "${WORKTREE_BASE}/$1"
}

cmd_create() {
    local slug="${1:?Usage: $0 create <task-slug> [base-branch]}"
    local base="${2:-main}"
    local branch
    branch="$(_branch_name "$slug")"
    local dir
    dir="$(_worktree_dir "$slug")"

    if [ -d "$dir" ]; then
        echo "Worktree already exists: $dir"
        echo "Use: cd $dir"
        return 0
    fi

    git fetch origin "$base" 2>/dev/null || true
    git worktree add "$dir" -b "$branch" "origin/$base"

    echo "Worktree created:"
    echo "  dir:    $dir"
    echo "  branch: $branch"
    echo "  base:   $base"
    echo ""
    echo "Next steps:"
    echo "  cd $dir"
    echo "  # open in editor, run claude, etc."
}

cmd_list() {
    echo "Active worktrees:"
    echo ""
    git worktree list
    echo ""

    if [ -d "$WORKTREE_BASE" ]; then
        echo "Agent worktrees in $WORKTREE_BASE:"
        ls -1 "$WORKTREE_BASE" 2>/dev/null || echo "  (none)"
    fi
}

cmd_rm() {
    local slug="${1:?Usage: $0 rm <task-slug>}"
    local dir
    dir="$(_worktree_dir "$slug")"
    local branch
    branch="$(_branch_name "$slug")"

    if [ ! -d "$dir" ]; then
        echo "No worktree at $dir"
        return 1
    fi

    git worktree remove "$dir" --force
    echo "Removed worktree: $dir"

    read -rp "Also delete branch '$branch'? [y/N] " yn
    if [[ "$yn" =~ ^[Yy]$ ]]; then
        git branch -D "$branch" 2>/dev/null || true
        echo "Deleted branch: $branch"
    fi
}

cmd_run() {
    local slug="${1:?Usage: $0 run <task-slug> \"prompt\" [base-branch]}"
    local prompt="${2:?Usage: $0 run <task-slug> \"prompt\" [base-branch]}"
    local base="${3:-main}"
    local dir
    dir="$(_worktree_dir "$slug")"

    if [ ! -d "$dir" ]; then
        cmd_create "$slug" "$base"
    fi

    echo "Running Claude Code headless in: $dir"
    echo "Prompt: $prompt"
    echo "---"

    (cd "$dir" && claude -p "$prompt" \
        --allowedTools Read,Write,Shell \
        --max-turns 15)

    echo "---"
    echo "Done. Review changes:"
    echo "  cd $dir && git diff"
}

cmd_prune() {
    git worktree prune -v
    echo "Pruned stale worktree references."
}

case "${1:-help}" in
    create) shift; cmd_create "$@" ;;
    list)   cmd_list ;;
    rm)     shift; cmd_rm "$@" ;;
    run)    shift; cmd_run "$@" ;;
    prune)  cmd_prune ;;
    *)
        echo "Usage: $0 {create|list|rm|run|prune}"
        echo ""
        echo "Commands:"
        echo "  create <slug> [base]    Create worktree + branch"
        echo "  list                    Show all worktrees"
        echo "  rm <slug>               Remove worktree (optionally delete branch)"
        echo "  run <slug> \"prompt\"     Create worktree + run claude headless in it"
        echo "  prune                   Clean up stale worktree refs"
        echo ""
        echo "Examples:"
        echo "  $0 create fix-auth           # worktree at ../task_agent-worktrees/fix-auth"
        echo "  $0 run fix-tests \"Fix the failing test in test_commands.py\""
        echo "  $0 rm fix-auth               # cleanup"
        ;;
esac
