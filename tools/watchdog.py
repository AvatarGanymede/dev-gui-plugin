#!/usr/bin/env python3
"""
watchdog.py — pipeline health monitor for dev-gui-plugin.

Adapted from ARIS `tools/watchdog.py`. The GPU / training / download checks are
removed; instead it scans the project's run-state files
(``<root>/.claude/dev-gui-runs/<panelId>/run_state.json``, written by
gui_run_state.py) and reports the health of each GUI pipeline run — flagging
phases that are STALLED (stuck `running` past a staleness threshold) or FAILED,
and aggregating a one-line-per-run summary for low-frequency polling.

Optional component: the pipeline runs fine without it. Use it when driving many
GUI runs and you want a cheap "is anything wedged?" signal.

Usage:
    # one-shot scan + print summary
    python3 watchdog.py --root <project_dir> --status

    # daemon: re-scan every <interval>s, write status/ + summary.txt
    python3 watchdog.py --root <project_dir> [--interval 60] [--stale-mins 30]
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_INTERVAL = 60
DEFAULT_STALE_MINS = 30


def _runs_dir(root: str) -> Path:
    return Path(root) / ".claude" / "dev-gui-runs"


def _watchdog_dir(root: str) -> Path:
    return _runs_dir(root) / ".watchdog"


def _parse_ts(ts: str) -> float:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, TypeError):
        return 0.0


def check_run(state_path: Path, stale_secs: int) -> dict:
    """Classify one run: DEAD/STALLED/FAILED/RUNNING/COMPLETE/OK."""
    now_ts = datetime.now(timezone.utc).timestamp()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"status": "ERROR", "run": state_path.parent.name, "msg": str(e), "ts": now}

    run_id = state.get("run_id", state_path.parent.name)
    phases = state.get("phases", [])
    failed = [p["phase"] for p in phases if p.get("status") == "failed"]
    running = [p for p in phases if p.get("status") == "running"]
    terminal = {"accepted", "skipped"}
    pending = [p for p in phases if p.get("status") not in terminal]

    if failed:
        return {"status": "FAILED", "run": run_id, "msg": f"failed phases: {', '.join(failed)}", "ts": now}
    if not pending:
        return {"status": "COMPLETE", "run": run_id, "msg": "all phases accepted/skipped", "ts": now}
    # Staleness: a phase `running` (or the whole run idle) past the threshold.
    last = max((_parse_ts(p.get("updated", "")) for p in phases), default=0.0)
    if last and (now_ts - last) > stale_secs:
        mins = int((now_ts - last) / 60)
        cur = running[0]["phase"] if running else pending[0]["phase"]
        return {"status": "STALLED", "run": run_id,
                "msg": f"no progress for {mins}min (current: {cur})", "ts": now}
    if running:
        return {"status": "RUNNING", "run": run_id, "msg": f"in {running[0]['phase']}", "ts": now}
    return {"status": "OK", "run": run_id,
            "msg": f"next: {pending[0]['phase']}" if pending else "idle", "ts": now}


def write_status(wd: Path, data: dict) -> dict:
    wd.mkdir(parents=True, exist_ok=True)
    (wd / f"{data['run']}.json").write_text(json.dumps(data), encoding="utf-8")
    if data.get("status") in ("DEAD", "STALLED", "FAILED", "ERROR"):
        with open(wd / "alerts.log", "a", encoding="utf-8") as f:
            f.write(f"[{data['ts']}] {data['run']}: {data['status']} — {data.get('msg','')}\n")
    return data


def scan_once(root: str, stale_secs: int) -> str:
    runs = _runs_dir(root)
    wd = _watchdog_dir(root)
    lines = []
    if runs.exists():
        for state_path in sorted(runs.glob("*/run_state.json")):
            data = check_run(state_path, stale_secs)
            write_status(wd, data)
            lines.append(f"{data['run']}: {data['status']} — {data.get('msg','')}")
    summary = "\n".join(lines) if lines else "no runs"
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "summary.txt").write_text(summary, encoding="utf-8")
    return summary


def run_daemon(root: str, interval: int, stale_secs: int) -> None:
    wd = _watchdog_dir(root)
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "watchdog.pid").write_text(str(os.getpid()), encoding="utf-8")

    def handle(sig, frame):
        try:
            (wd / "watchdog.pid").unlink(missing_ok=True)
        finally:
            sys.exit(0)

    signal.signal(signal.SIGTERM, handle)
    signal.signal(signal.SIGINT, handle)
    print(f"watchdog started (pid={os.getpid()}, root={root}, interval={interval}s, stale={stale_secs//60}min)")
    while True:
        scan_once(root, stale_secs)
        time.sleep(interval)


def main() -> int:
    ap = argparse.ArgumentParser(description="dev-gui-plugin pipeline health watchdog")
    ap.add_argument("--root", default=os.environ.get("CLAUDE_PROJECT_DIR", "."),
                    help="project dir holding .claude/dev-gui-runs/ (default: $CLAUDE_PROJECT_DIR or .)")
    ap.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    ap.add_argument("--stale-mins", type=int, default=DEFAULT_STALE_MINS)
    ap.add_argument("--status", action="store_true", help="one-shot scan + print summary, then exit")
    a = ap.parse_args()
    stale_secs = a.stale_mins * 60
    if a.status:
        print(scan_once(a.root, stale_secs))
        return 0
    run_daemon(a.root, a.interval, stale_secs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
