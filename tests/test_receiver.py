"""The Receiver accepts Notifications and starts one Run for each."""

import logging
import re

import pytest

from grafana_jsm_sandbox.receiver import Receiver
from tests.conftest import (
    firing_notification,
    get_health,
    post_notification,
    wait_for_log,
)


def _firing_notification_but(change) -> dict:
    """The canned firing Notification with one thing broken by `change`."""
    notification = firing_notification()
    change(notification)
    return notification


def _firing_notification_with_fingerprint(fingerprint: str) -> dict:
    return _firing_notification_but(
        lambda notification: notification["alerts"][0].update(fingerprint=fingerprint)
    )


def test_health_reports_the_receiver_is_up(receiver):
    assert get_health(receiver).status == 200


def test_valid_notification_is_accepted_and_starts_one_run(receiver, spawner):
    notification = firing_notification()

    response = post_notification(receiver, notification)

    assert response.status == 202
    spawner.wait_for_spawns(1)
    assert len(spawner.spawned) == 1
    assert spawner.spawned[0].notification == notification


def test_notification_is_acknowledged_without_waiting_for_its_run(receiver, spawner):
    release = spawner.block_until_released()

    response = post_notification(receiver, firing_notification())

    assert response.status == 202
    spawner.wait_for_spawns(1)
    assert not release.is_set(), "the response arrived only after the Run had finished"
    release.set()


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"not json at all", id="not-json"),
        pytest.param(b"", id="empty-body"),
        pytest.param([1, 2, 3], id="json-but-not-an-object"),
        pytest.param(
            _firing_notification_but(lambda notification: notification.pop("alerts")),
            id="no-alerts-key",
        ),
        pytest.param(
            _firing_notification_but(
                lambda notification: notification.update(alerts={"status": "firing"})
            ),
            id="alerts-not-a-list",
        ),
        pytest.param(
            _firing_notification_but(
                lambda notification: notification["alerts"][0].pop("fingerprint")
            ),
            id="alert-without-fingerprint",
        ),
        pytest.param(
            _firing_notification_but(lambda notification: notification["alerts"][0].pop("status")),
            id="alert-without-status",
        ),
    ],
)
def test_body_that_is_not_a_notification_is_refused_and_starts_no_run(receiver, spawner, body):
    response = post_notification(receiver, body)

    assert response.status == 400
    assert spawner.spawned == []


def test_notification_the_receiver_cannot_record_gets_a_server_error(spawner, tmp_path):
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("the runs directory cannot be created underneath a file")
    receiver = Receiver(spawn_run=spawner, runs_directory=blocked / "runs")
    receiver.start()
    try:
        response = post_notification(receiver, firing_notification())
    finally:
        receiver.stop()

    assert response.status == 500
    assert spawner.spawned == []


def test_notifications_are_run_one_at_a_time_in_arrival_order(receiver, spawner):
    release_first = spawner.block_until_released()
    first = _firing_notification_with_fingerprint("1111111111111111")
    second = _firing_notification_with_fingerprint("2222222222222222")

    assert post_notification(receiver, first).status == 202
    spawner.wait_for_spawns(1)
    assert post_notification(receiver, second).status == 202

    assert len(spawner.spawned) == 1, "the second Run began before the first had finished"
    release_first.set()

    spawner.wait_for_spawns(2)
    assert [run.notification for run in spawner.spawned] == [first, second]


def test_receiver_logs_each_runs_start_end_exit_status_and_duration(receiver, spawner, caplog):
    caplog.set_level(logging.INFO)
    spawner.exit_status = 3

    post_notification(receiver, firing_notification())

    spawner.wait_for_spawns(1)
    run_id = spawner.spawned[0].run_id
    log = wait_for_log(caplog, f"run {run_id} finished")
    assert f"run {run_id} started" in log
    assert "exit status 3" in log
    assert re.search(rf"run {run_id} finished.*\b\d+\.\d+s", log)


def test_run_that_blows_up_is_logged_and_the_next_notification_still_runs(
    receiver, spawner, caplog
):
    caplog.set_level(logging.INFO)
    spawner.fail_next(RuntimeError("the spawner exploded"))

    post_notification(receiver, _firing_notification_with_fingerprint("1111111111111111"))
    spawner.wait_for_spawns(1)
    failed_run_id = spawner.spawned[0].run_id
    log = wait_for_log(caplog, f"run {failed_run_id} failed")
    assert "the spawner exploded" in log

    second = _firing_notification_with_fingerprint("2222222222222222")
    assert post_notification(receiver, second).status == 202
    spawner.wait_for_spawns(2)
    assert spawner.spawned[1].notification == second
