#!/bin/bash
# הועתק מ-sessions-archive/toolkit/process/hooks/session-start.sh@9801386
# SessionStart hook — canonical process-toolkit version.
# 1. Displays open requirements from PROCESS.md (if present).
# 2. Warns if the local clone lags behind origin (never auto-resets).
# Copy into a project's .claude/hooks/ and reference from .claude/settings.json.
# Provenance: copied from sessions-archive/toolkit/process/hooks/session-start.sh@<commit>.

set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}"

# Open requirements (works local and remote)
if [ -f "PROCESS.md" ]; then
  echo "📋 PROCESS.md — דרישות פתוחות:"
  awk '/^## דרישות פתוחות/,/^## דרישות סגורות/' PROCESS.md | head -30
  echo ""
fi

# Drift check against origin — report only, never reset
DEFAULT_BRANCH="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@' || echo main)"
if git rev-parse --git-dir >/dev/null 2>&1; then
  git fetch origin "$DEFAULT_BRANCH" --quiet 2>/dev/null || true
  behind="$(git rev-list --count "HEAD..origin/${DEFAULT_BRANCH}" 2>/dev/null || echo 0)"
  if [ "$behind" -gt 0 ]; then
    echo "⚠️  הקלונה המקומית מפגרת ב-${behind} commits אחרי origin/${DEFAULT_BRANCH} — שקול git pull לפני עבודה."
    echo ""
  fi
fi

# --- Per-project extensions below this line (e.g. dependency install for tests) ---
