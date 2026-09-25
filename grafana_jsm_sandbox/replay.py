"""Replaying the canned Notification sequence at a Receiver.

The three committed fixtures are one Alert seen three times: a Firing, a repeat
Firing, and a Resolved. Posting them in order drives the whole Incident
lifecycle without Grafana being involved, which is the demo's fallback and what
the end-to-end check uses.

    python3 -m grafana_jsm_sandbox.replay --receiver http://localhost:8080 --pause 30

The Receiver runs Notifications one at a time in arrival order, so the pause is
about pacing what an audience sees, not about keeping the Runs apart.
"""

from __future__ import annotations

import argparse
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

SEQUENCE = (
    "notification-firing.json",
    "notification-firing-repeat.json",
    "notification-resolved.json",
)
"""The canned Notifications, in the order a demo replays them."""

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
"""Where the canned Notifications live in this repo."""

NOTIFICATION_PATH = "/notification"
"""The Receiver's endpoint, the one Grafana's contact point points at."""

DEFAULT_RECEIVER = "http://localhost:8080"
"""The demo on this laptop, or the container's published port."""

DEFAULT_PAUSE = 30.0
"""Seconds between Notifications: long enough to watch one Run finish before the next."""

POST_TIMEOUT = 10.0
"""Seconds to wait for the Receiver's acknowledgement, which it sends before the Run."""


def replay(receiver_url: str = DEFAULT_RECEIVER, pause: float = DEFAULT_PAUSE) -> list[int]:
    """Post the canned sequence in order and return what the Receiver answered each time."""
    url = receiver_url.rstrip("/") + NOTIFICATION_PATH
    statuses = []
    for index, filename in enumerate(SEQUENCE):
        if index:
            time.sleep(pause)
        status = post(url, (FIXTURES / filename).read_bytes())
        logger.info("posted %s, receiver said %s", filename, status)
        statuses.append(status)
    return statuses


def post(url: str, notification: bytes) -> int:
    """POST one Notification and return the status, whatever it was."""
    request = urllib.request.Request(
        url,
        data=notification,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=POST_TIMEOUT) as response:
            return response.status
    except urllib.error.HTTPError as refusal:
        refusal.read()
        return refusal.code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--receiver", default=DEFAULT_RECEIVER, help="the Receiver's base URL")
    parser.add_argument(
        "--pause", type=float, default=DEFAULT_PAUSE, help="seconds between Notifications"
    )
    arguments = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    statuses = replay(arguments.receiver, arguments.pause)
    return 0 if all(status == 202 for status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
