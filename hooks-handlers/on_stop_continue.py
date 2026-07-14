#!/usr/bin/env python3
"""Stop hook — autorun driver that keeps the 7-phase pipeline chained.

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
  - Session-scoped (STRICT): a sentinel records the ``session_id`` of the session
    that started the autorun (stamped by the ``/dev-gui-plugin:run`` command). The
    Stop hook drives a sentinel ONLY when its ``session_id`` equals the CURRENT
    stopping session's, so an unrelated session that happens to stop in the same
    project is never hijacked into the pipeline. There is no project-global
    fallback: an unscoped sentinel (no ``session_id`` — a pre-upgrade residual or a
    session_id-capture failure) is never driven and is retired on sight; a sentinel
    owned by a different live session is left for that session to drive.
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

    Core of the cross-session fix, STRICT: drive only when the sentinel records a
    ``session_id`` AND it equals the current Stop event's ``session_id``.

    There is deliberately NO project-global fallback. An earlier version drove
    sentinels that lacked a ``session_id`` "globally" so as not to strand in-flight
    runs — but that re-opened the exact bug: a pre-upgrade (unscoped) sentinel kept
    hijacking unrelated sessions that merely stopped in the same project. So an
    unscoped sentinel (or a Stop event with no session_id) now means "not ours" and
    is never driven (unscoped residuals are retired separately, see main()).
    """
    owner = sentinel.get("session_id")
    return bool(owner) and bool(current_sid) and owner == current_sid


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


def _reason_for(nxt: str, run_id: str, nudges: int, max_nudges: int) -> str:
    """Driver nudge text for the target phase.

    Most phases share one generic nudge. `gui-prefab` is special: it is the head of
    the `gui-prefab ∥ gui-config` PARALLEL group — reaching it means the orchestrator
    should drive BOTH in one turn (prefab on the main agent, config in a background
    subagent when the requirement touches config), settling both states before it
    yields. `gui-config` alone is only reached on a resume boundary (prefab already
    done, config still pending) — there we just drive config normally.
    """
    head = (
        f"[dev-gui:run 自动驱动 {nudges}/{max_nudges}] pipeline 尚未跑完，"
        f"run='{run_id}' 的下一阶段是 **{nxt}**。"
    )
    tail = (
        "\n铁律：阶段间不停顿；缺必要信息就占位实现 + 留 TODO 注释并记入 HUMAN_REVIEW.md；"
        "本次不适用的阶段用 `gui_run_state.py set <root> <run_id> <phase> skipped` 显式跳过；"
        "完成该阶段后用 `set ... <phase> done` 记账，再继续后续阶段，直到 gui-learn 完成。"
    )
    if nxt == "gui-prefab":
        return (
            head
            + "这是 **gui-prefab ∥ gui-config 并行组**，请在**同一回合内**同时驱动两阶段并把两者状态都落定：\n"
            "① **主 agent 跑 gui-prefab**（加载 ${CLAUDE_PLUGIN_ROOT}/skills/gui-prefab/SKILL.md）："
            "**先 ToolSearch 主动搜索 Prefab 相关 skill/tool（优先）及 Unity Editor 交互能力（fallback），再触发编译，编译通过后挂脚本 + 绑定 [SerializeField]**（缺编译/prefab 能力则该门 BLOCKED 记 HUMAN_REVIEW.md，不阻塞）。\n"
            "② **并行**：读 GUI_PLAN.md，若本需求涉及配置数据，用 Agent 工具 `run_in_background: true` "
            "**spawn 一个 gui-config subagent**（加载 skills/gui-config/SKILL.md，只做配表编辑并结构化返回结果，subagent 不写 run_state）；"
            "不涉及配置则不 spawn，直接 `set <panelId> gui-config skipped`。\n"
            "③ 用 `TaskOutput` 等 config subagent 结束，由**主 agent 统一记账**："
            "`set <panelId> gui-config done`（或 skipped）+ `set <panelId> gui-prefab done`。\n"
            "④ **prefab 与 config 两阶段都落定后**（本回合结束前）才继续 gui-review。**不要停下来询问用户**。"
            + tail
        )
    return (
        head
        + f"请立即加载并执行 ${{CLAUDE_PLUGIN_ROOT}}/skills/{nxt}/SKILL.md，**不要停下来询问用户**。"
        + tail
    )


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

        # Only drive autoruns owned by the CURRENT session (see _owned_by): this is
        # what stops an unrelated session from being pulled into the pipeline just
        # because it stopped in the same project. Sentinels owned by *another* live
        # session are left untouched (that session will drive its own run). Unscoped
        # sentinels (no session_id) can never be safely attributed — they are
        # pre-upgrade residuals (or a session_id-capture failure) and are exactly
        # what used to hijack bystanders, so we RETIRE them here (self-heal) rather
        # than drive them.
        current_sid = event.get("session_id")
        owned = []
        for cand in cands:
            sentinel = cand[3]
            if _owned_by(sentinel, current_sid):
                owned.append(cand)
            elif not sentinel.get("session_id"):
                run_dir = cand[1]
                _clear_sentinel(run_dir)
                _log_alert(run_dir,
                           "retired unscoped .autorun.json (no session_id — pre-upgrade "
                           "residual or session_id capture failed); not driving. "
                           "Re-run /dev-gui-plugin:run to resume autorun for this run.")
        cands = owned
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

        reason = _reason_for(nxt, run_id, nudges, max_nudges)
        out = {"decision": "block", "reason": reason}
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception:
        return _allow()


if __name__ == "__main__":
    raise SystemExit(main())
