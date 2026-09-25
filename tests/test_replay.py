"""Replaying the canned Notification sequence at a Receiver.

The replay is the demo's fallback when Grafana is uncooperative, and it is what
the end-to-end check posts. It drives a real Receiver over real HTTP here, the
same way it drives the container's one during a demo.
"""

from __future__ import annotations

import json
import time

import pytest

from grafana_jsm_sandbox.replay import SEQUENCE, replay
from tests.conftest import FIXTURES


@pytest.fixture
def canned_sequence() -> list[dict]:
    return [json.loads((FIXTURES / filename).read_text()) for filename in SEQUENCE]


def test_every_canned_notification_is_accepted(receiver):
    assert replay(receiver.url, pause=0) == [202, 202, 202]


def test_the_sequence_arrives_in_order_and_starts_one_run_each(receiver, spawner, canned_sequence):
    replay(receiver.url, pause=0)

    spawner.wait_for_spawns(3)
    assert [run.notification for run in spawner.spawned] == canned_sequence


def test_the_pause_falls_between_the_notifications_and_not_after_the_last(receiver, spawner):
    pause = 0.3
    started_at = time.monotonic()

    replay(receiver.url, pause=pause)

    elapsed = time.monotonic() - started_at
    assert 2 * pause <= elapsed < 3 * pause, "one pause between each pair, and none after the last"
    spawner.wait_for_spawns(3)


def test_a_receiver_that_is_not_there_says_so():
    with pytest.raises(OSError):
        replay("http://127.0.0.1:1", pause=0)
