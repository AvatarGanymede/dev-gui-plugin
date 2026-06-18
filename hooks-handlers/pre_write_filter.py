#!/usr/bin/env python3
"""PreToolUse(Write|Edit) hook — anti-self-poisoning filter for gui-knowledge writes.

When a Write/Edit targets a path under EITHER knowledge base — the private one
(``${CLAUDE_PLUGIN_DATA}/gui-knowledge/``) or the project-public one
(``${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge/``) — screen the content with
capture_filter.py before it lands. If it trips a class (env failure / transient
error / negative-tool claim / single-instance narrative), DENY the write with a
reason telling the agent to store the fix / the class-level rule instead — so
operational noise never hardens into "knowledge" (plan §十.4).

Scope is deliberately narrow: writes that are NOT under a knowledge base are
always allowed (this hook only guards the knowledge bases, not normal code edits).

Fails OPEN: any parsing/import error → allow, never block on the filter's own
failure. Asymmetry holds — this mechanical screen may only REJECT a capture;
making an entry load-bearing still needs reviewer endorsement (gui_knowledge.py
promote).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# capture_filter lives in ../tools relative to this handler.
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT")
_tools = Path(_PLUGIN_ROOT) / "tools" if _PLUGIN_ROOT else Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(_tools))
try:
    from capture_filter import screen, reason_detail
except Exception:
    screen = None  # type: ignore
    reason_detail = None  # type: ignore


def _allow() -> int:
    sys.stdout.write("{}")
    return 0


def _is_knowledge_path(file_path: str) -> bool:
    if not file_path:
        return False
    norm = file_path.replace("\\", "/")
    if "gui-knowledge" not in norm:
        return False
    # Project-public KB: ${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge/
    if "/dev-gui-knowledge/" in norm or norm.endswith("/dev-gui-knowledge"):
        return True
    # Private KB: ${CLAUDE_PLUGIN_DATA}/gui-knowledge/
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if data:
        data_norm = data.replace("\\", "/").rstrip("/")
        return norm.startswith(data_norm) or "/gui-knowledge/" in norm
    # No data env: be conservative and still screen anything under a gui-knowledge dir.
    return "/gui-knowledge/" in norm or norm.endswith("/gui-knowledge")


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return _allow()

    if screen is None:
        return _allow()

    tool_input = event.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    if not _is_knowledge_path(file_path):
        return _allow()

    # Write → content; Edit → new_string (the text being introduced).
    content = tool_input.get("content") or tool_input.get("new_string") or ""
    try:
        reasons = screen(content)
    except Exception:
        return _allow()

    if not reasons:
        return _allow()

    detail = "; ".join(f"{r}: {reason_detail(r)}" for r in reasons) if reason_detail else ", ".join(reasons)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "gui-knowledge capture filter blocked this write (anti-self-poisoning, plan §十.4). "
                f"Flagged: {detail} "
                "改为存「怎么修 / 缺什么配置 / 它隐含的类级规则」，而非操作噪音或单次叙事。"
            ),
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
