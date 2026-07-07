#!/usr/bin/env python3
"""Resumable run-state for the dev-gui-plugin 7-phase pipeline.

A GUI pipeline run (plan → draft → prefab → config → review → improve → learn)
can fail mid-run; without a record of *which phase* finished, a resume restarts
from scratch. This helper models a run as an ordered list of phases with status,
so resume can pick up where it left off.

Note: gui-review is now the single verification phase — it runs the independent
Type-B reviewer subagent (Bias Guard) and the deterministic Type-A gates in
parallel and emits the 6-state GUI_VERDICT.json. The former standalone gui-verify
phase was merged into it.

The increment over a naive "resume = reopen" — the status enum SPLITS execution
from acceptance:

    done      the orchestrator (Claude) finished writing the artifact.
              EXECUTION-COMPLETENESS — a safe SAME-MODEL self-report.
    accepted  an INDEPENDENT reviewer subagent (Bias Guard, fresh context) OR a
              deterministic verifier returned a positive verdict, recorded with a
              verdict id + reviewer.
    skipped   the phase does not apply to this run (e.g. gui-config when there is
              no config change) — a deterministic decision, terminal.

Resume resolves FORWARD to the first phase that is NOT terminal ({accepted,
skipped}) — never the first non-`done`. So a phase the orchestrator self-
considered "done" but that crashed before its independent review is RE-VALIDATED
on resume, never silently skipped. Acceptance-gate rule made operational: a loop
can DRIVE resume, it cannot ACQUIT a phase past itself.

Structurally enforced: `set` may only write pending/running/done/failed/skipped;
only `accept` writes `accepted`, and it REQUIRES a verdict id + reviewer AND that
the phase already be `done` (use --force to override).

State at ``<root>/.claude/dev-gui-runs/<run_id>/run_state.json`` (run_id = panelId),
project-local and gitignored. Single-writer contract; a best-effort flock guards
against a concurrent resumer.

Migrated/adapted from ARIS `tools/run_state.py`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

try:
    import fcntl  # POSIX
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore

# The canonical 7 GUI pipeline phases (plan §三). gui-review is the single
# verification phase (parallel Type-A gates + Type-B reviewer subagent).
GUI_PHASES = [
    "gui-plan", "gui-draft", "gui-prefab", "gui-config",
    "gui-review", "gui-improve", "gui-learn",
]

EXECUTOR_STATUSES = {"pending", "running", "done", "failed", "skipped"}
TERMINAL_STATUSES = {"accepted", "skipped"}  # resume skips these
ALL_STATUSES = EXECUTOR_STATUSES | {"accepted"}

# Session scoping ------------------------------------------------------------
# A run is keyed by ``<panelId>__<sessionId>`` so concurrent/sequential sessions
# never share one panel's state file (panelId alone is NOT unique). All callers
# pass the bare panelId; the storage key is composed HERE (single source of
# truth), so the same panel under a different session resolves to a different
# directory. Cross-session resume is a deliberate NON-goal: a new session = a new
# id = a clean run.
SESSION_ENV = "CLAUDE_SESSION_ID"

_SESSION_HELP = (
    "CLAUDE_SESSION_ID is missing — dev-gui run state is session-scoped and cannot be "
    "created or located without it. Likely causes:\n"
    "  1) this Claude Code version does not provide CLAUDE_ENV_FILE, so the SessionStart "
    "hook could not bridge session_id into Bash;\n"
    "  2) the plugin was enabled mid-session (its SessionStart hook never ran for this "
    "session);\n"
    "  3) the SessionStart event carried no session_id, or on_session_start.py failed.\n"
    "Fix: start a NEW Claude Code session and retry; if it persists, update Claude Code or "
    "check the dev-gui-plugin SessionStart hook. (Override explicitly with --session-id <id>.)"
)


class SessionIdMissing(RuntimeError):
    """No session id available to scope the run. We refuse to fall back to a
    non-scoped key — that is exactly what would let two sessions collide on one
    panel's state."""


def _resolve_session_id(explicit: Optional[str] = None) -> str:
    sid = (explicit if explicit is not None else os.environ.get(SESSION_ENV, "")).strip()
    if not sid:
        raise SessionIdMissing(_SESSION_HELP)
    return sid


def _sanitize_component(s: str) -> str:
    """Reduce a key component to the run-id charset ([A-Za-z0-9-_.])."""
    return "".join(c if (c.isalnum() or c in "-_.") else "-" for c in s).strip("-")


def storage_key(panel_id: str, session_id: str) -> str:
    """Compose the session-scoped run id ``<panelId>__<sessionId>``.

    Idempotent: if ``panel_id`` already ends with the ``__<sessionId>`` suffix
    (a caller passed an already-composed key) it is returned unchanged rather
    than double-suffixed. Raises on an empty panel id / session id.
    """
    pid = _sanitize_component(panel_id.strip())
    sid = _sanitize_component(session_id.strip())
    if not pid:
        raise ValueError(f"empty/invalid panel id {panel_id!r}")
    if not sid:
        raise SessionIdMissing(_SESSION_HELP)
    suffix = f"__{sid}"
    return pid if pid.endswith(suffix) else f"{pid}{suffix}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_path(root: str, run_id: str) -> Path:
    safe = "".join(c for c in run_id if c.isalnum() or c in "-_.")
    if not safe or safe != run_id or run_id in (".", ".."):
        raise ValueError(f"invalid run_id {run_id!r} (use [A-Za-z0-9-_.])")
    return Path(root) / ".claude" / "dev-gui-runs" / run_id / "run_state.json"


@contextmanager
def _lock(root: str, run_id: str) -> Iterator[None]:
    """Best-effort advisory lock for the load-modify-save of one run. No-op where
    fcntl is unavailable (Windows)."""
    p = _run_path(root, run_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fcntl is None:
        yield
        return
    lock_path = p.with_suffix(".lock")
    fh = open(lock_path, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()


def _load(root: str, run_id: str) -> dict:
    p = _run_path(root, run_id)
    if not p.exists():
        raise FileNotFoundError(f"no run state at {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _save(root: str, run_id: str, state: dict) -> None:
    p = _run_path(root, run_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    state["updated"] = _now()
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{run_id}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        finally:
            raise


def _build_metadata(pcraft_task_id: Optional[str], p4_changelist: Optional[str]) -> dict:
    return {
        "pcraft_task_id": pcraft_task_id or None,
        "p4_changelist": p4_changelist or None,
    }


def _apply_metadata(state: dict, pcraft_task_id: Optional[str], p4_changelist: Optional[str]) -> bool:
    metadata = state.setdefault("metadata", {})
    changed = False
    if pcraft_task_id:
        if metadata.get("pcraft_task_id") != pcraft_task_id:
            metadata["pcraft_task_id"] = pcraft_task_id
            changed = True
    if p4_changelist:
        if metadata.get("p4_changelist") != p4_changelist:
            metadata["p4_changelist"] = p4_changelist
            changed = True
    return changed


def start_run(
    root: str,
    run_id: str,
    phases: list[str],
    pcraft_task_id: Optional[str] = None,
    p4_changelist: Optional[str] = None,
) -> dict:
    """Create a run with ordered phases, all `pending` (idempotent: won't clobber)."""
    with _lock(root, run_id):
        if _run_path(root, run_id).exists():
            state = _load(root, run_id)
            if _apply_metadata(state, pcraft_task_id, p4_changelist):
                _save(root, run_id, state)
            return state
        state = {
            "run_id": run_id,
            "created": _now(),
            "updated": _now(),
            "metadata": _build_metadata(pcraft_task_id, p4_changelist),
            "phases": [{"phase": ph, "status": "pending", "artifact": None,
                        "verdict_id": None, "reviewer": None, "updated": _now()} for ph in phases],
        }
        _save(root, run_id, state)
        return state


def _find_phase(state: dict, phase: str) -> dict:
    for ph in state["phases"]:
        if ph["phase"] == phase:
            return ph
    raise KeyError(f"phase {phase!r} not in run (have: {[p['phase'] for p in state['phases']]})")


def set_status(root: str, run_id: str, phase: str, status: str, artifact: Optional[str] = None) -> dict:
    """Executor-side status. running/done/failed/skipped — NOT accepted (use accept())."""
    if status not in EXECUTOR_STATUSES:
        raise ValueError(
            f"set_status may only write {sorted(EXECUTOR_STATUSES)}; "
            f"'accepted' is reserved for accept() (needs an independent reviewer verdict).")
    with _lock(root, run_id):
        state = _load(root, run_id)
        ph = _find_phase(state, phase)
        ph["status"] = status
        if artifact is not None:
            ph["artifact"] = artifact
        ph["updated"] = _now()
        _save(root, run_id, state)
        return state


def accept(root: str, run_id: str, phase: str, verdict_id: str, reviewer: str, force: bool = False) -> dict:
    """Mark a phase `accepted` — REQUIRES a recorded verdict id + reviewer, and
    (unless force) that the phase already be `done`.

    Call ONLY from an independent reviewer subagent verdict (Bias Guard, fresh
    context) or a deterministic verifier (a passing gate, exit 0). The
    orchestrator must never call this on its own self-report.

    `verdict_id` should be a durable handle: the reviewer subagent's GUI_REVIEW.md
    path / GUI_VERDICT.json path, not just a label.
    """
    if not verdict_id or not reviewer:
        raise ValueError("accept requires a non-empty verdict_id AND reviewer — "
                         "a phase cannot be accepted without recording who acquitted it.")
    with _lock(root, run_id):
        state = _load(root, run_id)
        ph = _find_phase(state, phase)
        if not force and ph["status"] not in ("done", "accepted"):
            raise ValueError(
                f"phase {phase!r} is {ph['status']!r}, not 'done' — cannot accept a phase that "
                f"has not completed execution. Set it 'done' first, or pass force=True.")
        # Self-acquittal tripwire: the reviewer must be an INDEPENDENT subagent or
        # a deterministic verifier, never the orchestrator acquitting itself.
        low = reviewer.strip().lower()
        if low in ("", "self", "orchestrator", "executor", "me"):
            print(f"⚠️  accept: reviewer={reviewer!r} looks like the orchestrator itself. "
                  f"Acceptance must come from an independent reviewer subagent (Bias Guard) or "
                  f"a deterministic verifier. Recording anyway, but this is likely self-acquittal.",
                  file=sys.stderr)
        ph["status"] = "accepted"
        ph["verdict_id"] = verdict_id
        ph["reviewer"] = reviewer
        ph["updated"] = _now()
        _save(root, run_id, state)
        return state


def resume_point(root: str, run_id: str) -> Optional[dict]:
    """First phase whose status is NOT terminal ({accepted, skipped}) — the resume
    target — or None if the run is complete.

    A `done`-but-not-`accepted` phase IS a resume target: its independent review is
    still owed and must run before the next phase proceeds.
    """
    state = _load(root, run_id)
    for ph in state["phases"]:
        if ph["status"] not in TERMINAL_STATUSES:
            return ph
    return None


def _print_status(state: dict) -> None:
    print(f"run {state['run_id']}  (updated {state.get('updated', '?')})")
    glyph = {"pending": "·", "running": "▶", "done": "✓(unaccepted)",
             "failed": "✗", "accepted": "✅", "skipped": "⊘(skipped)"}
    for ph in state["phases"]:
        line = f"  {glyph.get(ph['status'], '?'):>14}  {ph['phase']}  [{ph['status']}]"
        if ph["status"] == "accepted":
            line += f"  ← {ph['reviewer']} / {ph['verdict_id']}"
        elif ph["artifact"]:
            line += f"  → {ph['artifact']}"
        print(line)
    rp = next((p for p in state["phases"] if p["status"] not in TERMINAL_STATUSES), None)
    print(f"  resume → {rp['phase'] if rp else 'COMPLETE (all phases accepted/skipped)'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="dev-gui-plugin resumable run-state (done vs accepted).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    # --session-id overrides CLAUDE_SESSION_ID for the run-id-bearing subcommands;
    # run_id is the bare panelId, composed to <panelId>__<sessionId> internally.
    s = sub.add_parser("start"); s.add_argument("root"); s.add_argument("run_id"); s.add_argument("--phases", default=",".join(GUI_PHASES), help="comma-separated phase names (default: the 7 GUI phases)"); s.add_argument("--pcraft-task-id"); s.add_argument("--p4-changelist"); s.add_argument("--session-id")
    s = sub.add_parser("set"); s.add_argument("root"); s.add_argument("run_id"); s.add_argument("phase"); s.add_argument("status", choices=sorted(EXECUTOR_STATUSES)); s.add_argument("--artifact"); s.add_argument("--session-id")
    s = sub.add_parser("accept"); s.add_argument("root"); s.add_argument("run_id"); s.add_argument("phase"); s.add_argument("--verdict-id", required=True); s.add_argument("--reviewer", required=True); s.add_argument("--force", action="store_true"); s.add_argument("--session-id")
    s = sub.add_parser("resume"); s.add_argument("root"); s.add_argument("run_id"); s.add_argument("--session-id")
    s = sub.add_parser("status"); s.add_argument("root"); s.add_argument("run_id"); s.add_argument("--session-id")
    s = sub.add_parser("list"); s.add_argument("root")
    # runid: print the composed <panelId>__<sessionId> key (asserts session id).
    # Used by /run for its own filesystem ops (run dir / sentinel / run_meta).
    s = sub.add_parser("runid"); s.add_argument("run_id"); s.add_argument("--session-id")
    a = ap.parse_args()

    try:
        if a.cmd == "runid":
            print(storage_key(a.run_id, _resolve_session_id(a.session_id)))
            return 0

        # All run-id-bearing subcommands are session-scoped: resolve the bare
        # panelId to <panelId>__<sessionId> here (single source of truth). This
        # also asserts a session id is available, failing closed if not.
        if a.cmd in ("start", "set", "accept", "resume", "status"):
            key = storage_key(a.run_id, _resolve_session_id(a.session_id))

        if a.cmd == "start":
            _print_status(start_run(
                a.root,
                key,
                [p.strip() for p in a.phases.split(",") if p.strip()],
                pcraft_task_id=a.pcraft_task_id,
                p4_changelist=a.p4_changelist,
            ))
        elif a.cmd == "set":
            _print_status(set_status(a.root, key, a.phase, a.status, a.artifact))
        elif a.cmd == "accept":
            _print_status(accept(a.root, key, a.phase, a.verdict_id, a.reviewer, force=a.force))
        elif a.cmd == "resume":
            rp = resume_point(a.root, key)
            if rp is None:
                print("COMPLETE"); return 0
            print(rp["phase"])  # machine-readable: the resume target phase name
            print(json.dumps(rp), file=sys.stderr)
        elif a.cmd == "status":
            _print_status(_load(a.root, key))
        elif a.cmd == "list":
            d = Path(a.root) / ".claude" / "dev-gui-runs"
            for f in sorted(d.glob("*/run_state.json")) if d.exists() else []:
                print(f.parent.name)
    except SessionIdMissing as e:
        print(f"error: {e}", file=sys.stderr); return 1
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
