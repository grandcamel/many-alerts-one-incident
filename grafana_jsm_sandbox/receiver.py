"""The Receiver: the HTTP endpoint that accepts Notifications and starts Runs."""

from __future__ import annotations

import logging
import queue
import secrets
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from grafana_jsm_sandbox.notification import (
    NOTIFICATION_FILENAME,
    InvalidNotification,
    validate_notification,
)

logger = logging.getLogger(__name__)

SHUTDOWN_POLL_INTERVAL = 0.05
"""How long `stop` may wait for the serving loop to notice it. The module's own default
of half a second is time a container spends on the way down, and time a test suite pays
for every server it starts."""


@dataclass(frozen=True)
class Run:
    """One headless Claude invocation, started for exactly one Notification."""

    run_id: str
    working_directory: Path

    @property
    def notification_path(self) -> Path:
        return self.working_directory / NOTIFICATION_FILENAME


class Receiver:
    """Accepts Grafana Notifications over HTTP and starts one Run for each.

    Runs are executed one at a time in arrival order by a single worker, so two
    Firings of the same Alert can never race. `spawn_run` is injected so that
    tests can substitute a fake: it is called with a Run and returns the Run's
    exit status.
    """

    def __init__(self, spawn_run, runs_directory: Path, host: str = "127.0.0.1", port: int = 0):
        self._spawn_run = spawn_run
        self._runs_directory = Path(runs_directory)
        self._host = host
        self._queue: queue.Queue = queue.Queue()
        self._server = ThreadingHTTPServer((host, port), _build_handler(self))
        self._http_thread: threading.Thread | None = None
        self._worker_thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        """Where the Receiver is actually listening, once an ephemeral port is bound."""
        port = self._server.server_address[1]
        return f"http://{self._host}:{port}"

    def start(self) -> None:
        self._worker_thread = threading.Thread(target=self._work, name="receiver-runs", daemon=True)
        self._worker_thread.start()
        self._http_thread = threading.Thread(
            target=self._server.serve_forever,
            args=(SHUTDOWN_POLL_INTERVAL,),
            name="receiver-http",
            daemon=True,
        )
        self._http_thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._http_thread is not None:
            self._http_thread.join(timeout=5)
        self._queue.put(None)
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=5)

    def accept(self, body: bytes) -> Run:
        """Record a Notification as a new Run and queue it. Returns before it starts.

        Raises InvalidNotification if the body is not a Grafana Notification.
        """
        validate_notification(body)
        run = self._prepare_run(body)
        self._queue.put(run)
        return run

    def _prepare_run(self, body: bytes) -> Run:
        run_id = f"{time.strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(3)}"
        working_directory = self._runs_directory / run_id
        working_directory.mkdir(parents=True)
        run = Run(run_id, working_directory)
        run.notification_path.write_bytes(body)
        return run

    def _work(self) -> None:
        while True:
            run = self._queue.get()
            if run is None:
                return
            self._execute(run)

    def _execute(self, run: Run) -> None:
        """Run one Run to completion. A Run that blows up must not stall the queue."""
        logger.info("run %s started in %s", run.run_id, run.working_directory)
        started_at = time.monotonic()
        try:
            exit_status = self._spawn_run(run)
        except Exception:
            duration = time.monotonic() - started_at
            logger.exception("run %s failed after %.2fs", run.run_id, duration)
        else:
            duration = time.monotonic() - started_at
            logger.info(
                "run %s finished with exit status %s in %.2fs", run.run_id, exit_status, duration
            )


def _build_handler(receiver: Receiver):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            if self.path == "/health":
                self._respond(200, b"ok")
            else:
                self._respond(404, b"not found")

        def do_POST(self):
            if self.path != "/notification":
                self._respond(404, b"not found")
                return
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                receiver.accept(body)
            except InvalidNotification as error:
                self._respond(400, str(error).encode())
                return
            except Exception:
                logger.exception("could not record a Notification as a Run")
                self._respond(500, b"could not record the notification")
                return
            self._respond(202, b"accepted")

        def _respond(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            """Silence BaseHTTPRequestHandler's stderr access log; the Receiver logs Runs."""

    return Handler
