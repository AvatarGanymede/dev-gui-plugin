#!/usr/bin/env python3
"""Deterministic prompt-injection / exfiltration scanner for dev-gui-plugin.

The plugin injects model- and tool-authored content back into agent context:
the gui-knowledge query_pack (auto-injected by the SessionStart hook), knowledge
nodes/edges, and fetched Prefab / Excel data. None of that is trustworthy by
default. This module is the cheap, deterministic layer that runs over the
query_pack AFTER it is assembled — a poisoned knowledge node cannot talk its way
past a regex.

A clean scan is NOT a safety acquittal — only the absence of known-bad strings.
"Drive, not acquit": this scanner may GATE / banner an inject; correctness of the
content still belongs to the independent reviewer (see shared-references/
acceptance-gate.md).

Migrated from ARIS `tools/threat_scan.py` (which adapted NousResearch/hermes-agent
`tools/threat_patterns.py`, MIT). Trimmed to the injection-scan surface this
plugin needs: `scan_for_threats`, `quarantine`, `first_threat_message`.

Scope (nested: all ⊂ context ⊂ strict):
  all      — classic injection + exfil; minimal false positives, any text.
  context  — + promptware / C2 / role-hijack; web/tool content, warn-by-default.
  strict   — + persistence / ssh-backdoor / exfil-URL / config-mod / secrets;
             user-mediated writes (knowledge, query_pack) — scan here.
"""

from __future__ import annotations

import re
import sys
from typing import List, Optional, Tuple

# Each entry: (regex, pattern_id, scope), scope ∈ {"all", "context", "strict"}
_PATTERNS: List[Tuple[str, str, str]] = [
    # ── Classic prompt injection (everywhere) ────────────────────────
    (r'ignore\s+(?:\w+\s+)*(previous|all|above|prior)\s+(?:\w+\s+)*instructions', "prompt_injection", "all"),
    (r'system\s+prompt\s+override', "sys_prompt_override", "all"),
    (r'disregard\s+(?:\w+\s+)*(your|all|any)\s+(?:\w+\s+)*(instructions|rules|guidelines)', "disregard_rules", "all"),
    (r'act\s+as\s+(if|though)\s+(?:\w+\s+)*you\s+(?:\w+\s+)*(have\s+no|don\'t\s+have)\s+(?:\w+\s+)*(restrictions|limits|rules)', "bypass_restrictions", "all"),
    (r'<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->', "html_comment_injection", "all"),
    (r'do\s+not\s+(?:\w+\s+)*tell\s+(?:\w+\s+)*the\s+user', "deception_hide", "all"),

    # ── Role-play / identity hijack (context) ────────────────────────
    (r'you\s+are\s+(?:\w+\s+)*now\s+(?:a|an|the)\s+', "role_hijack", "context"),
    (r'pretend\s+(?:\w+\s+)*(you\s+are|to\s+be)\s+', "role_pretend", "context"),
    (r'output\s+(?:\w+\s+)*(system|initial)\s+prompt', "leak_system_prompt", "context"),
    (r'(respond|answer|reply)\s+without\s+(?:\w+\s+)*(restrictions|limitations|filters|safety)', "remove_filters", "context"),
    (r'you\s+have\s+been\s+(?:\w+\s+)*(updated|upgraded|patched)\s+to', "fake_update", "context"),

    # ── C2 / promptware (context; warn-by-default) ───────────────────
    (r'(heartbeat|beacon|check[\s\-]?in)\s+(to|with)\s+', "c2_heartbeat", "context"),
    (r'you\s+must\s+(?:\w+\s+){0,3}(beacon|exfiltrate|phone\s+home)\b', "forced_action", "context"),
    (r'unset\s+\w*(?:CLAUDE|CODEX|GEMINI|AGENT|OPENAI|ANTHROPIC)\w*', "env_var_unset_agent", "context"),
    (r'\b(?:cobalt\s*strike|sliver|havoc|mythic|metasploit)\b', "known_c2_framework", "context"),
    (r'\bcommand\s+and\s+control\b', "c2_explicit_long", "context"),

    # ── Exfiltration (everywhere / strict) ───────────────────────────
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_curl", "all"),
    (r'wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_wget", "all"),
    (r'cat\s+[^\n>]*(\.env|credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)', "read_secrets", "all"),
    (r'(?:exfiltrate|smuggle|leak)\s+[^\n]{0,60}\s+(?:to|at)\s+https?://', "exfil_to_url", "strict"),
    (r'(include|output|print|share)\s+(?:\w+\s+)*(conversation|chat\s+history|previous\s+messages|full\s+context|entire\s+context)', "context_exfil", "strict"),

    # ── Persistence / backdoor / config-mod (strict) ─────────────────
    (r'authorized_keys', "ssh_backdoor", "strict"),
    (r'\$HOME/\.ssh|\~/\.ssh', "ssh_access", "strict"),
    (r'(?:update|modify|edit|append\s+to|overwrite)\s+[^\n]{0,40}(?:AGENTS\.md|CLAUDE\.md|(?<![A-Za-z_])MEMORY\.md|\.cursorrules|\.clinerules)', "agent_config_mod", "strict"),

    # ── Hardcoded secrets (strict) ───────────────────────────────────
    (r'(?:api[_-]?key|token|secret|password)\s*[=:]\s*["\'][A-Za-z0-9+/=_-]{20,}', "hardcoded_secret", "strict"),
]

# Invisible / bidirectional unicode used in injection attacks.
INVISIBLE_CHARS = frozenset({
    '​', '‌', '‍', '⁠', '⁢', '⁣', '⁤',
    '﻿', '‪', '‫', '‬', '‭', '‮',
    '⁦', '⁧', '⁨', '⁩',
})

_COMPILED: dict[str, List[Tuple[re.Pattern, str]]] = {}


def _compile() -> None:
    global _COMPILED
    if _COMPILED:
        return
    all_p: List[Tuple[re.Pattern, str]] = []
    context_p: List[Tuple[re.Pattern, str]] = []
    strict_p: List[Tuple[re.Pattern, str]] = []
    for pattern, pid, scope in _PATTERNS:
        entry = (re.compile(pattern, re.IGNORECASE), pid)
        if scope == "all":
            all_p.append(entry); context_p.append(entry); strict_p.append(entry)
        elif scope == "context":
            context_p.append(entry); strict_p.append(entry)
        elif scope == "strict":
            strict_p.append(entry)
        else:
            raise ValueError(f"threat_scan: unknown scope {scope!r} for {pid!r}")
    _COMPILED = {"all": all_p, "context": context_p, "strict": strict_p}


_compile()


def scan_for_threats(content: str, scope: str = "context") -> List[str]:
    """Return matched pattern IDs in ``content`` at ``scope`` (empty = clean).

    Invisible-unicode hits are returned as ``invisible_unicode_U+XXXX``.
    """
    if not content:
        return []
    findings: List[str] = []
    for ch in (set(content) & INVISIBLE_CHARS):
        findings.append(f"invisible_unicode_U+{ord(ch):04X}")
    patterns = _COMPILED.get(scope)
    if patterns is None:
        raise ValueError(f"scan_for_threats: unknown scope {scope!r}")
    for compiled, pid in patterns:
        if compiled.search(content):
            findings.append(pid)
    return findings


def first_threat_message(content: str, scope: str = "strict") -> Optional[str]:
    """Human-readable error for the first threat found at ``scope``, else None."""
    findings = scan_for_threats(content, scope=scope)
    if not findings:
        return None
    pid = findings[0]
    if pid.startswith("invisible_unicode_"):
        return f"Blocked: invisible unicode character {pid.replace('invisible_unicode_', '')} (possible injection)."
    return (
        f"Blocked: content matches threat pattern '{pid}'. This content is "
        f"re-injected into agent context and must not carry an injection or "
        f"exfiltration payload."
    )


def quarantine(content: str, scope: str = "strict", label: str = "entry") -> Tuple[str, List[str]]:
    """Inject-time quarantine (fail-closed-with-visibility).

    If ``content`` trips a pattern, return a visible ``[BLOCKED: ...]`` placeholder
    plus the findings; the caller keeps the RAW text on disk so a human can review
    it. If clean, returns ``(content, [])``.
    """
    findings = scan_for_threats(content, scope=scope)
    if not findings:
        return content, []
    placeholder = (
        f"[BLOCKED: {label} matched threat pattern(s): {', '.join(findings)} "
        f"— raw text preserved on disk; review and remove. Not injected into context.]"
    )
    return placeholder, findings


__all__ = ["INVISIBLE_CHARS", "scan_for_threats", "first_threat_message", "quarantine"]


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="dev-gui-plugin injection / exfiltration scanner.")
    ap.add_argument("path", help="file to scan, or - for stdin")
    ap.add_argument("--scope", choices=["all", "context", "strict"], default="strict")
    ap.add_argument("--quarantine", action="store_true",
                    help="print the quarantined text instead of the findings")
    args = ap.parse_args()
    text = sys.stdin.read() if args.path == "-" else open(args.path, encoding="utf-8").read()
    if args.quarantine:
        out, findings = quarantine(text, scope=args.scope, label=args.path)
        sys.stdout.write(out if out.endswith("\n") else out + "\n")
        return 1 if findings else 0
    findings = scan_for_threats(text, scope=args.scope)
    if findings:
        print(f"THREAT ({args.scope}): {', '.join(findings)}", file=sys.stderr)
        return 1
    print(f"clean ({args.scope})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
