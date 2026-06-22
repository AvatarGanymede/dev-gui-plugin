#!/usr/bin/env python3
"""Stop hook — autorun driver that keeps the 8-phase pipeline chained.

The pipeline's phase-to-phase chaining is otherwise "soft": each SKILL.md ends
with a natural-language "→ next phase" hint and relies on the agent to follow it.
This hook turns that into an enforceable loop **only when the user opted in via
``/dev-gui-plugin:run``** (which drops an ``.autorun.json`` sentinel in the run
dir). On every agent stop:

  1. Find runs under ``${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/*`` that carry a
     ``.autorun.json`` sentinel (i.e. an active autorun).
  2. For the most-recently-updated such run, compute the FORWARD driver target:
     the first phase whose status is NOT in {done, accepted, skipped}.
       - NOTE: this is deliberately different from gui_run_state.resume_point,
         which returns the first NON-{accepted,skipped} phase (so it re-validates
         `done`-but-unaccepted phases on crash-resume). For *forward driving* a
         `done` phase counts as progressed, so we also treat `done` as advanced.
  3. If a target remains → emit ``{"decision":"block","reason":...}`` so the agent
     is forced to continue with that phase instead of stopping.
  4. If no target remains (all done/accepted/skipped) → remove the sentinel and
     allow the stop.

Safety:
  - Gated by the sentinel: sessions WITHOUT an active autorun are never affected,
    so single-phase manual use (e.g. just /dev-gui-plugin:gui-review) is untouched.
  - Session-scoped: a sentinel records the ``session_id`` of the session that
    started the autorun (stamped by the ``/dev-gui-plugin:run`` command). The Stop
    hook only drives a sentinel whose ``session_id`` matches the CURRENT stopping
    session, so an unrelated session that happens to stop in the same project is
    never hijacked into the pipeline. (Legacy/unscoped sentinels with no
    ``session_id`` — or events that carry no ``session_id`` — fall back to the old
    project-global behavior so in-flight runs are not abandoned.)
  - A per-run nudge counter (``max_nudges``, default 30) caps runaway loops; once
    exceeded the sentinel is cleared, an alert is logged, and the stop is allowed.
  - Fails OPEN: any error → allow the stop, never wedge the session.

This is a *driver*, not a *health monitor* — for cross-run "is anything wedged?"
polling, use tools/watchdog.py.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# A phase is "advanced" for forward-driving once its execution finished (done) or
# it was independently accepted / deemed not applicable (skipped). The driver
# targets the first phase NOT yet advanced.
_ADVANCED = {"done", "accepted", "skipped"}
_DEFAULT_MAX_NUDGES = 30


def _allow() -> int:
    sys.stdout.write("{}")
    return 0


def _project_root(event: dict) -> Path | None:
    root = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd")
    if not root:
        return None
    p = Path(root)
    return p if p.exists() else None


def _owned_by(sentinel: dict, current_sid: str | None) -> bool:
    """Whether this autorun sentinel belongs to the current stopping session.

    Core of the cross-session fix. A sentinel that records a ``session_id`` is
    only driven for that exact session. Missing data on EITHER side (an unscoped
    legacy sentinel, or a Stop event without a session_id) degrades to the old
    project-global behavior so we never strand an in-flight run.
    """
    owner = sentinel.get("session_id")
    if not owner or not current_sid:
        return True
    return owner == current_sid


def _next_phase(state: dict) -> str | None:
    """First phase whose status is not in _ADVANCED, or None if the run is done."""
    for ph in state.get("phases", []):
        if ph.get("status") not in _ADVANCED:
            return ph.get("phase")
    return None


def _candidates(runs_dir: Path) -> list[tuple[float, Path, dict, dict]]:
    """(updated_ts, run_dir, run_state, sentinel) for runs with an autorun sentinel."""
    out: list[tuple[float, Path, dict, dict]] = []
    for state_path in runs_dir.glob("*/run_state.json"):
        run_dir = state_path.parent
        sentinel_path = run_dir / ".autorun.json"
        if not sentinel_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        try:
            sentinel = json.loads(sentinel_path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError):
            sentinel = {}
        ts = state_path.stat().st_mtime
        out.append((ts, run_dir, state, sentinel))
    out.sort(key=lambda t: t[0], reverse=True)
    return out


def _clear_sentinel(run_dir: Path) -> None:
    try:
        (run_dir / ".autorun.json").unlink()
    except OSError:
        pass


def _log_alert(run_dir: Path, msg: str) -> None:
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(run_dir / ".autorun.log", "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except OSError:
        pass


def main() -> int:
    # The event payload is optional — we prefer CLAUDE_PROJECT_DIR. Parse best-effort
    # (tolerate a BOM / stray whitespace); fall back to an empty event, don't bail.
    try:
        raw = (sys.stdin.read() or "").lstrip("\ufeff").strip()
        event = json.loads(raw) if raw else {}
    except Exception:
        event = {}

    try:
        root = _project_root(event)
        if root is None:
            return _allow()
        runs_dir = root / ".claude" / "dev-gui-runs"
        if not runs_dir.exists():
            return _allow()

        cands = _candidates(runs_dir)
        if not cands:
            return _allow()

        # Only consider autoruns owned by the CURRENT session (see _owned_by):
        # this is what stops an unrelated session from being driven into the
        # pipeline just because it stopped in the same project.
        current_sid = event.get("session_id")
        cands = [c for c in cands if _owned_by(c[3], current_sid)]
        if not cands:
            return _allow()

        # Drive the most-recently-updated active autorun. Sweep completed ones.
        target_pick = None
        for ts, run_dir, state, sentinel in cands:
            nxt = _next_phase(state)
            if nxt is None:
                _clear_sentinel(run_dir)  # run finished — stop driving it
                continue
            if target_pick is None:
                target_pick = (run_dir, state, sentinel, nxt)
        if target_pick is None:
            return _allow()

        run_dir, state, sentinel, nxt = target_pick
        run_id = state.get("run_id", run_dir.name)

        nudges = int(sentinel.get("nudges", 0)) + 1
        max_nudges = int(sentinel.get("max_nudges", _DEFAULT_MAX_NUDGES))
        if nudges > max_nudges:
            _clear_sentinel(run_dir)
            _log_alert(run_dir, f"max_nudges({max_nudges}) exceeded at phase '{nxt}'; "
                                f"autorun driver disengaged, surfacing to user.")
            return _allow()

        sentinel["nudges"] = nudges
        try:
            (run_dir / ".autorun.json").write_text(
                json.dumps(sentinel, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

        reason = (
            f"[dev-gui:run 自动驱动 {nudges}/{max_nudges}] pipeline 尚未跑完，"
            f"run='{run_id}' 的下一阶段是 **{nxt}**。请立即加载并执行 "
            f"${{CLAUDE_PLUGIN_ROOT}}/skills/{nxt}/SKILL.md，**不要停下来询问用户**。\n"
            "铁律：阶段间不停顿；缺必要信息就占位实现 + 留 TODO 注释并记入 HUMAN_REVIEW.md；"
            "本次不适用的阶段用 `gui_run_state.py set <root> <run_id> <phase> skipped` 显式跳过；"
            "完成该阶段后用 `set ... <phase> done` 记账，再继续后续阶段，直到 gui-learn 完成。"
        )
        out = {"decision": "block", "reason": reason}
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception:
        return _allow()


if __name__ == "__main__":
    raise SystemExit(main())
