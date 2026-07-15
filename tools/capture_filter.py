#!/usr/bin/env python3
"""Anti-self-poisoning capture filter for gui-knowledge.

When the plugin captures durable knowledge (a bug/fix instance, a generalized
component/pattern/lesson), it must NOT store *operational noise* that hardens
into a self-cited falsehood. A self-improvement loop that records "the prefab MCP
is broken" or "this run failed" turns transient state into a permanent refusal
the agent later cites against itself, long after the real problem was fixed.

This is a CHEAP, DETERMINISTIC pre-filter for the (mostly) unambiguous classes.
It is called in two places:
  1. PreToolUse(Write) hook — when a Write targets a gui-knowledge path.
  2. gui-learn Phase 8, step 0 — before persisting any knowledge entry.

Four classes (plan §十.4):
  env_failure              missing binary / module / path / permission — store
                           the FIX or the missing config, never "X failed".
  transient_error          rate-limit / OOM / network / timeout that self-resolves.
  negative_tool_claim      "unity-prefab can't / the reviewer is broken" — these
                           harden into self-cited refusals. Store the workaround.
  single_instance_narrative  a one-off "this time / in XXPanel it ..." narrative
                           with no class-level rule extracted. Force the instance→
                           class generalization (plan §十.5) before storing.

Asymmetry (acceptance-gate.md): this filter may only REJECT (a mechanical safety
screen, low risk). Anything that PASSES and would become load-bearing (enter the
query_pack) still needs an independent reviewer to ACCEPT it. Same-model may
reject; accepting a class-level rule requires reviewer endorsement.

Deliberately conservative: a false reject just sends a real insight to manual
rewrite; a false negative is caught later by the reviewer. It is anchored so it
does NOT flag legitimate GUI findings ("StylesModule cannot animate", which is a
component limitation worth recording) — it targets THIS plugin's own tooling
being declared broken, raw error output, and un-generalized single-run prose.
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import List

# Raw error / environment-failure output — unambiguous transient state.
_ENV_FAILURE = [
    (re.compile(r"\bcommand not found\b", re.I), "env_failure"),
    (re.compile(r"\bNo such file or directory\b", re.I), "env_failure"),
    (re.compile(r"\bNo module named\b", re.I), "env_failure"),
    (re.compile(r"\bModuleNotFoundError\b"), "env_failure"),
    (re.compile(r"\bImportError\b"), "env_failure"),
    (re.compile(r"\bPermission denied\b", re.I), "env_failure"),
    (re.compile(r"\bconnection (refused|timed out|reset)\b", re.I), "transient_error"),
    (re.compile(r"\b(rate limit|429|quota exceeded|503|502|temporarily unavailable)\b", re.I), "transient_error"),
    (re.compile(r"\btimed out\b|\btimeout\b", re.I), "transient_error"),
]

# Negative capability claims about THIS plugin's own tooling. Anchored on
# qualified tool nouns ONLY — bare component/library names are NOT here, because
# "StylesModule cannot do X" is a legitimate component limitation worth recording.
# We require a tooling qualifier (mcp/cli/the reviewer/an explicit tool name).
_TOOL = (r"(?:"
         r"unity[ -](?:cli|mcp|prefab)|"
         r"unity-prefab|"
         r"excel[ -](?:config|mcp)|"
         r"excel-config|"
         r"the reviewer|reviewer subagent|"
         r"mcp server|the mcp|"
         r")")
_NEG_CLAIM = [
    (re.compile(_TOOL + r"\s+(?:can'?t|cannot|is unable to|does(?:n'?t| not))\s+", re.I), "negative_tool_claim"),
    (re.compile(_TOOL + r"\s+(?:is|are|was|were)\s+(?:broken|down|useless|unusable|buggy)\b", re.I), "negative_tool_claim"),
    (re.compile(_TOOL + r"\s+always\s+(?:fails|crashes|hangs|errors)\b", re.I), "negative_tool_claim"),
    (re.compile(r"\b(?:don'?t|do not|never)\s+use\s+(?:the\s+|a\s+)?" + _TOOL, re.I), "negative_tool_claim"),
]

# Single-instance narrative: temporal / this-run framing WITHOUT a class-level
# rule. Anchored on one-off markers ("this time", "this run", "当时", "这次",
# "刚才"). Conservative — only flags when such a marker is present; the
# instance→class generalization (plan §十.5) is otherwise prose guidance the
# reviewer enforces, not something a regex can fully judge.
_SINGLE_INSTANCE = [
    (re.compile(r"\bthis (?:time|run|once|particular run)\b", re.I), "single_instance_narrative"),
    (re.compile(r"\b(?:just|right) now\b", re.I), "single_instance_narrative"),
    (re.compile(r"当时|这次|刚才|这一次|本次运行时(?:碰|遇)到", re.I), "single_instance_narrative"),
]

_ALL = _ENV_FAILURE + _NEG_CLAIM + _SINGLE_INSTANCE


def screen(text: str) -> List[str]:
    """Return de-duplicated anti-pattern reason codes found in `text` (empty = clean).

    reason ∈ {env_failure, transient_error, negative_tool_claim,
              single_instance_narrative}.
    """
    if not text:
        return []
    found: List[str] = []
    for rx, reason in _ALL:
        if reason not in found and rx.search(text):
            found.append(reason)
    return found


def reason_detail(reason: str) -> str:
    return {
        "env_failure": "looks like an environment-specific failure (missing binary/module/path "
                       "/permission) — transient state, not durable knowledge. Store HOW TO FIX "
                       "or the missing config, never 'X failed'.",
        "transient_error": "looks like a transient error (rate limit / OOM / network / timeout) "
                           "that self-resolves — do not capture it as a durable rule.",
        "negative_tool_claim": "looks like a negative capability claim about this plugin's own "
                              "tooling ('X can't / is broken'). These harden into self-cited "
                              "refusals. Store the fix / the workaround, not 'X can't do Y'.",
        "single_instance_narrative": "looks like a one-off run narrative ('this time / in XXPanel "
                              "it ...') with no class-level rule. Extract the reusable rule first "
                              "(plan §十.5: instance→class) and store THAT, not the episode.",
    }.get(reason, reason)


__all__ = ["screen", "reason_detail"]


def main() -> int:
    ap = argparse.ArgumentParser(description="dev-gui-plugin anti-self-poisoning capture filter.")
    ap.add_argument("path", help="file to screen, or - for stdin")
    a = ap.parse_args()
    text = sys.stdin.read() if a.path == "-" else open(a.path, encoding="utf-8").read()
    reasons = screen(text)
    if reasons:
        print(f"DO-NOT-CAPTURE: {', '.join(reasons)}", file=sys.stderr)
        for r in reasons:
            print(f"  - {r}: {reason_detail(r)}", file=sys.stderr)
        return 1
    print("ok to capture (mechanical screen clean)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
