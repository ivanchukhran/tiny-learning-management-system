#!/usr/bin/env bash
# PostToolUse hook: run `ruff format` on a Python file Claude Code just edited.
# Receives the tool-call payload as JSON on stdin.
set -euo pipefail

file_path="$(jq -r '.tool_input.file_path // empty')"

# Only format real Python files that still exist on disk.
case "$file_path" in
  *.py) ;;
  *) exit 0 ;;
esac
[ -f "$file_path" ] || exit 0

uv run --no-sync ruff format "$file_path"
