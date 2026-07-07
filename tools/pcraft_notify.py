#!/usr/bin/env python3
"""Fail-open notifier for pcraft task state/phase updates.

Usage examples:
  python3 tools/pcraft_notify.py self-check
  python3 tools/pcraft_notify.py
  python3 tools/pcraft_notify.py --task-id 123 --api-url http://127.0.0.1:7777
  python3 tools/pcraft_notify.py --gui-phase gui-review --gui-phase-status done
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _env_or_arg(value: str | None, env_key: str) -> str:
    if value:
        return value
    return os.environ.get(env_key, "").strip()


def _task_url(api_url: str, task_id: str) -> str:
    base = api_url.rstrip("/")
    quoted = urllib.parse.quote(task_id, safe="")
    return f"{base}/api/v1/tasks/{quoted}"


def _phase_url(api_url: str, task_id: str) -> str:
    return f"{_task_url(api_url, task_id)}/gui-phase"


def _patch_json(url: str, payload: dict[str, Any], timeout_s: float = 3.0) -> tuple[bool, str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="PATCH",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            code = getattr(resp, "status", 200)
            if 200 <= code < 300:
                return True, f"{code}"
            return False, f"unexpected status {code}"
    except urllib.error.HTTPError as e:
        return False, f"http {e.code}"
    except Exception as e:  # pragma: no cover - depends on network/runtime
        return False, str(e)


def notify_done(
    api_url: str,
    task_id: str,
    state: str = "DONE",
    gui_phase: str | None = None,
    gui_phase_status: str | None = None,
    *,
    patch_state: bool = True,
) -> int:
    task_endpoint = _task_url(api_url, task_id)
    if patch_state:
        ok, reason = _patch_json(task_endpoint, {"state": state})
        if not ok:
            print(f"[pcraft_notify] warn: task state notify failed ({reason})", file=sys.stderr)
        else:
            print(f"[pcraft_notify] ok: state={state} -> {task_endpoint}")

    if gui_phase:
        phase_endpoint = _phase_url(api_url, task_id)
        phase_payload: dict[str, Any] = {"phase": gui_phase}
        if gui_phase_status:
            phase_payload["status"] = gui_phase_status
        ok_phase, reason_phase = _patch_json(phase_endpoint, phase_payload)
        if not ok_phase:
            print(
                f"[pcraft_notify] warn: gui phase notify failed ({reason_phase})",
                file=sys.stderr,
            )
        else:
            print(f"[pcraft_notify] ok: gui phase -> {phase_endpoint}")

    # fail-open: never block pipeline completion.
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Notify pcraft task completion (fail-open).")
    parser.add_argument("--task-id", help="pcraft task id (default: PCRAFT_TASK_ID env)")
    parser.add_argument("--api-url", help="pcraft API base URL (default: PCRAFT_API_URL env)")
    parser.add_argument(
        "--state",
        default=None,
        help="task state to PATCH (default: DONE when no --gui-phase; omitted for phase-only updates)",
    )
    parser.add_argument("--gui-phase", help="optional gui phase, e.g. gui-review")
    parser.add_argument("--gui-phase-status", help="optional gui phase status, e.g. done")
    return parser


def self_check() -> int:
    url = _task_url("http://127.0.0.1:9999/", "task/中文")
    expected = "http://127.0.0.1:9999/api/v1/tasks/task%2F%E4%B8%AD%E6%96%87"
    if url != expected:
        print(f"self-check failed: unexpected url={url}", file=sys.stderr)
        return 1
    phase_url = _phase_url("http://127.0.0.1:9999/", "task-1")
    if phase_url != "http://127.0.0.1:9999/api/v1/tasks/task-1/gui-phase":
        print(f"self-check failed: unexpected phase url={phase_url}", file=sys.stderr)
        return 1
    print("self-check ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] == "self-check":
        return self_check()

    args = build_parser().parse_args(args_list)
    task_id = _env_or_arg(args.task_id, "PCRAFT_TASK_ID")
    api_url = _env_or_arg(args.api_url, "PCRAFT_API_URL")

    if not task_id or not api_url:
        print(
            "[pcraft_notify] skip: PCRAFT_TASK_ID/PCRAFT_API_URL missing, nothing to notify",
            file=sys.stderr,
        )
        return 0

    patch_state = args.state is not None or args.gui_phase is None
    return notify_done(
        api_url=api_url,
        task_id=task_id,
        state=args.state or "DONE",
        gui_phase=args.gui_phase,
        gui_phase_status=args.gui_phase_status,
        patch_state=patch_state,
    )


if __name__ == "__main__":
    raise SystemExit(main())
