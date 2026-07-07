#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch

import importlib.util


def _load_notify_module() -> Any:
    path = Path(__file__).with_name("pcraft_notify.py")
    spec = importlib.util.spec_from_file_location("pcraft_notify", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load pcraft_notify module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pcraft_notify = _load_notify_module()


class _PatchCaptureHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, Any]] = []

    def do_PATCH(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length) if length > 0 else b""
        self.__class__.requests.append(
            {
                "path": self.path,
                "body": payload.decode("utf-8"),
                "headers": dict(self.headers),
            }
        )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


class PcraftNotifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _PatchCaptureHandler)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=1)

    def setUp(self) -> None:
        _PatchCaptureHandler.requests = []

    def test_main_skips_without_required_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            rc = pcraft_notify.main([])
        self.assertEqual(rc, 0)
        self.assertEqual(_PatchCaptureHandler.requests, [])

    def test_main_patches_done_state(self) -> None:
        env = {"PCRAFT_TASK_ID": "task-123", "PCRAFT_API_URL": self.base_url}
        with patch.dict(os.environ, env, clear=True):
            rc = pcraft_notify.main([])
        self.assertEqual(rc, 0)
        self.assertEqual(len(_PatchCaptureHandler.requests), 1)
        req = _PatchCaptureHandler.requests[0]
        self.assertEqual(req["path"], "/api/v1/tasks/task-123")
        self.assertEqual(json.loads(req["body"]), {"state": "DONE"})

    def test_main_optional_gui_phase_patch(self) -> None:
        env = {"PCRAFT_TASK_ID": "task-456", "PCRAFT_API_URL": self.base_url}
        with patch.dict(os.environ, env, clear=True):
            rc = pcraft_notify.main(["--gui-phase", "gui-review", "--gui-phase-status", "done"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(_PatchCaptureHandler.requests), 1)
        req = _PatchCaptureHandler.requests[0]
        self.assertEqual(req["path"], "/api/v1/tasks/task-456/gui-phase")
        self.assertEqual(
            json.loads(req["body"]),
            {"phase": "gui-review", "status": "done"},
        )


if __name__ == "__main__":
    unittest.main()
