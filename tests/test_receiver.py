"""The Receiver accepts Notifications and starts one Run for each."""

import logging
import re
import socket
from urllib.parse import urlsplit

import pytest

from grafana_jsm_sandbox.receiver import Receiver, RunOutcome
from tests.conftest import (
    firing_notification,
    get_health,
    http_request,
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
    log = wait_for_log(caplog, f"run {failed_run_id} FAILED")
    assert "the spawner exploded" in log

    second = _firing_notification_with_fingerprint("2222222222222222")
    assert post_notification(receiver, second).status == 202
    spawner.wait_for_spawns(2)
    assert spawner.spawned[1].notification == second


# --- Failures read as failures (step 05 of demo-onboarding) ---


def records(caplog, substring: str) -> list[logging.LogRecord]:
    return [record for record in caplog.records if substring in record.getMessage()]


def test_a_run_whose_transcript_says_it_failed_is_logged_failed_though_it_exited_0(
    receiver, spawner, caplog
):
    """A refused Run exits 0; the spawner read its result and says why it failed."""
    caplog.set_level(logging.INFO)
    spawner.outcome = RunOutcome(0, "api_error: You're out of usage credits")

    post_notification(receiver, firing_notification())

    spawner.wait_for_spawns(1)
    run_id = spawner.spawned[0].run_id
    wait_for_log(caplog, f"run {run_id} FAILED")
    [failed] = records(caplog, f"run {run_id} FAILED")
    assert failed.getMessage() == f"run {run_id} FAILED: api_error: You're out of usage credits"
    assert failed.levelno == logging.ERROR


def test_a_run_with_a_nonzero_exit_status_is_logged_failed(receiver, spawner, caplog):
    caplog.set_level(logging.INFO)
    spawner.exit_status = 3

    post_notification(receiver, firing_notification())

    spawner.wait_for_spawns(1)
    run_id = spawner.spawned[0].run_id
    log = wait_for_log(caplog, f"run {run_id} FAILED")
    assert f"run {run_id} FAILED: exit status 3" in log


def test_a_run_that_did_its_job_is_never_logged_failed(receiver, spawner, caplog):
    caplog.set_level(logging.INFO)
    spawner.outcome = RunOutcome(0)

    post_notification(receiver, firing_notification())

    spawner.wait_for_spawns(1)
    log = wait_for_log(caplog, f"run {spawner.spawned[0].run_id} finished")
    assert "FAILED" not in log


def test_an_accepted_notification_is_logged_with_its_alerts_run_and_place_in_the_queue(
    receiver, spawner, caplog
):
    caplog.set_level(logging.INFO)
    release_first = spawner.block_until_released()
    two_alerts = firing_notification()
    two_alerts["alerts"].append(dict(two_alerts["alerts"][0], fingerprint="2222222222222222"))

    post_notification(receiver, firing_notification())
    spawner.wait_for_spawns(1)
    post_notification(receiver, two_alerts)
    first = spawner.spawned[0].run_id
    log = wait_for_log(caplog, "notification accepted", count=2)
    release_first.set()
    spawner.wait_for_spawns(2)

    accepted = [r.getMessage() for r in records(caplog, "notification accepted")]
    assert accepted[0] == f"notification accepted: 1 alert, run {first} queued, 0 ahead"
    assert re.fullmatch(r"notification accepted: 2 alerts, run \S+ queued, 1 ahead", accepted[1])
    assert log.index("notification accepted") < log.index(f"run {first} started")


def test_the_queue_depth_counts_down_as_runs_finish(receiver, spawner, caplog):
    caplog.set_level(logging.INFO)

    post_notification(receiver, firing_notification())
    spawner.wait_for_spawns(1)
    wait_for_log(caplog, f"run {spawner.spawned[0].run_id} finished")
    post_notification(receiver, firing_notification())
    spawner.wait_for_spawns(2)

    accepted = [r.getMessage() for r in records(caplog, "notification accepted")]
    assert [message.endswith(", 0 ahead") for message in accepted] == [True, True]


def test_a_rejected_notification_is_logged_with_its_reason(receiver, spawner, caplog):
    caplog.set_level(logging.INFO)

    response = post_notification(receiver, b"not json at all")

    assert response.status == 400
    [rejected] = records(caplog, "rejected a Notification")
    assert rejected.levelno == logging.WARNING
    assert "body is not JSON" in rejected.getMessage()
    assert "127.0.0.1" in rejected.getMessage()


def test_a_post_anywhere_else_is_logged_as_rejected(receiver, caplog):
    caplog.set_level(logging.INFO)

    response = http_request(receiver.url + "/elsewhere", method="POST", data=b"{}")

    assert response.status == 404
    [rejected] = records(caplog, "rejected a POST")
    assert rejected.levelno == logging.WARNING
    assert rejected.getMessage() == "rejected a POST to '/elsewhere' from 127.0.0.1: not found"


def test_a_rejected_path_reaches_the_log_escaped(receiver, caplog):
    """Anyone who can reach the port chooses the path, and the log may be on a projected
    terminal, so a control character in it is shown, not obeyed."""
    caplog.set_level(logging.INFO)
    site = urlsplit(receiver.url)

    with socket.create_connection((site.hostname, site.port), timeout=5) as connection:
        connection.sendall(
            b"POST /x\x1b[2J HTTP/1.1\r\nHost: x\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        )
        answer = b""
        while chunk := connection.recv(4096):
            answer += chunk
    assert answer.split(b"\r\n", 1)[0].endswith(b" 404 Not Found")

    [rejected] = records(caplog, "rejected a POST")
    assert "\x1b" not in rejected.getMessage()
    assert "'/x\\x1b[2J'" in rejected.getMessage()
