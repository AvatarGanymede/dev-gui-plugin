#!/usr/bin/env bash
# lint_skills_helpers.sh — Advisory lint for hardcoded tool-path references.
#
# SKILL.md / agents files in this plugin must invoke the bundled Python tools via
# the canonical plugin-root chain:
#     python3 "${CLAUDE_PLUGIN_ROOT}/tools/<helper>.py" ...
# NOT a bare relative path like `python3 tools/foo.py`, which breaks once the
# plugin is installed from a marketplace (the cwd is the user's project, not the
# plugin root).
#
# This script is ADVISORY: it always exits 0 and only prints findings.
#
# Run from the plugin root:
#     bash tools/lint_skills_helpers.sh

set -u

HELPERS='gui_knowledge|gui_run_state|capture_filter|threat_scan|watchdog'
# A bare invocation with no ${CLAUDE_PLUGIN_ROOT} (or $CLAUDE_PLUGIN_ROOT) prefix.
INVOCATION_PY="python3 (\\./)?tools/($HELPERS)\\.py"

violation_count=0
violation_report=""

while IFS= read -r f; do
  hits=$(grep -nE "$INVOCATION_PY" "$f" 2>/dev/null | grep -v 'CLAUDE_PLUGIN_ROOT' || true)
  if [ -n "$hits" ]; then
    violation_count=$((violation_count + 1))
    violation_report="${violation_report}
=== $f ===
${hits}"
  fi
done < <(find skills agents -name '*.md' -type f 2>/dev/null)

echo "dev-gui-plugin helper-resolution lint (advisory)"
echo "================================================"
echo "Files with hardcoded \`tools/<helper>\` references (no \${CLAUDE_PLUGIN_ROOT}): $violation_count"

if [ "$violation_count" -gt 0 ]; then
  printf '%s\n\n' "$violation_report"
  echo "Resolution:"
  echo "  Invoke bundled tools as:"
  echo "    python3 \"\${CLAUDE_PLUGIN_ROOT}/tools/<helper>.py\" ..."
fi

echo ""
echo "Status: advisory (this script never fails CI; warnings only)."
exit 0
