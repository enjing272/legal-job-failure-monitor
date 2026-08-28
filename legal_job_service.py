"""Minimal HTTP entry point accepting scheduled legal job reports."""

from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from legal_job_monitor import InfraiClient, InfraiError, ScheduledJobReport, observe_scheduled_job


class LegalJobHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/scheduled-jobs/report":
            self._send(404, {"error": "route not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            report = ScheduledJobReport.from_dict(body)
            decision = observe_scheduled_job(report, InfraiClient())
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
            return
        except InfraiError as exc:
            status = exc.status_code if 400 <= exc.status_code < 500 else 502
            self._send(status, {"error": exc.detail})
            return

        self._send(200, asdict(decision))

    def _send(self, status: int, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), LegalJobHandler)
    print("Listening on http://127.0.0.1:8000")
    server.serve_forever()
