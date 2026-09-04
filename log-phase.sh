#!/usr/bin/env bash
# log-phase.sh — append a structured entry to PHASE_LOG.md
#
# Usage:
#   ./scripts/log-phase.sh <phase-id> <status> "<summary>" ["<still-mock-or-remaining>"]
#
# Example:
#   ./scripts/log-phase.sh R3 done "Real peel-chain, fan-out, mixer heuristics wired in; removed hash-based mock scoring" "mixer-address validation set still thin"
#
# status is free text but stick to: started | in-progress | blocked | done
# Run this at the start and end of each phase, and any time a blocker changes the plan —
# not on every commit. PHASE_LOG.md is append-only; never edit past entries, only add new ones.

set -euo pipefail

PHASE_ID="${1:?phase id required, e.g. R3}"
STATUS="${2:?status required: started|in-progress|blocked|done}"
SUMMARY="${3:?one-line summary required}"
REMAINING="${4:-none noted}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/../PHASE_LOG.md"
TIMESTAMP="$(date -u +"%Y-%m-%d %H:%M UTC")"

if [ ! -f "$LOG_FILE" ]; then
  {
    echo "# LEDGR Phase Log"
    echo ""
    echo "Append-only. Newest entries at the bottom. One entry per meaningful state change (phase start, phase done, blocker hit) — not every commit."
    echo "See \`PROJECT_MEMORY.md\` for the current overall project snapshot; this file is the detailed history behind it."
  } > "$LOG_FILE"
fi

{
  echo ""
  echo "## ${PHASE_ID} — ${STATUS} (${TIMESTAMP})"
  echo ""
  echo "- **Summary:** ${SUMMARY}"
  echo "- **Still mock / remaining:** ${REMAINING}"
} >> "$LOG_FILE"

echo "Logged to ${LOG_FILE}"
