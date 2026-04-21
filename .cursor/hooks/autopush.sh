#!/usr/bin/env bash
set -euo pipefail

# Cursor hook: afterFileEdit
# Goal: auto-commit + push on edits (debounced + filtered).
#
# Safety:
# - skips if no git remote
# - skips on re-entry (debounce)
# - skips known secret/binary/generated paths

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if ! command -v git >/dev/null 2>&1; then
  exit 0
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

# Debounce: at most one auto-commit per 20 seconds.
LOCK_FILE="$(git rev-parse --git-dir)/.cursor_autopush_lock"
NOW="$(date +%s)"
LAST="0"
if [[ -f "$LOCK_FILE" ]]; then
  LAST="$(cat "$LOCK_FILE" 2>/dev/null || echo 0)"
fi
if [[ "$NOW" =~ ^[0-9]+$ ]] && [[ "$LAST" =~ ^[0-9]+$ ]]; then
  if (( NOW - LAST < 20 )); then
    exit 0
  fi
fi
echo "$NOW" >"$LOCK_FILE" 2>/dev/null || true

# Must have a push remote.
if ! git remote get-url origin >/dev/null 2>&1; then
  exit 0
fi

# Stage changes but exclude risky / noisy paths.
CHANGED="$(git status --porcelain)"
if [[ -z "$CHANGED" ]]; then
  exit 0
fi

should_skip_path() {
  local p="$1"
  case "$p" in
    *.env|*/.env|*/.env.*) return 0 ;;
    backend/data/*|backend/data/**) return 0 ;;
    backend/data/generated_media/*|backend/data/generated_media/**) return 0 ;;
    backend/data/reel_runs/*|backend/data/reel_runs/**) return 0 ;;
    Images/*|Images/**) return 0 ;;
    *.mp4|*.mov|*.m4a|*.mp3|*.wav|*.aiff|*.png|*.jpg|*.jpeg|*.webp) return 0 ;;
  esac
  return 1
}

# Add only safe, text-like files.
while IFS= read -r line; do
  # porcelain format: XY <path>
  p="${line:3}"
  # handle renames: "old -> new"
  if [[ "$p" == *" -> "* ]]; then
    p="${p##* -> }"
  fi
  if should_skip_path "$p"; then
    continue
  fi
  git add -- "$p" >/dev/null 2>&1 || true
done <<<"$CHANGED"

# If nothing got staged, stop.
if git diff --cached --quiet >/dev/null 2>&1; then
  exit 0
fi

msg="chore: auto-save $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
git commit -m "$msg" >/dev/null 2>&1 || exit 0

# Push current branch.
git push -u origin HEAD >/dev/null 2>&1 || true

exit 0

