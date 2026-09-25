"""Receiver control client against real gated Forwarder sessions on socketpairs."""

import os
import queue
import socket
import threading

import pytest

import grafana_jsm_sandbox.forwarder_control as control_module
from grafana_jsm_sandbox.receiver_control_client import (
    ReceiverControlError,
    ReceiverControlSession,
)
from tests.test_forwarder_control_gate import (
    SECRET,
    TEST_TIMEOUT,
    new_gated_system,
    start_gated_control,
)
from tests.test_forwarder_routes import golden_manifest


def _session(client, boot='receiver-a'):
    return ReceiverControlSession(
        client, control_secret=SECRET, forwarder_uid=os.geteuid(),
        receiver_boot_id=boot, timeout=TEST_TIMEOUT,
    )


def test_heartbeat_and_unknown_closeout_are_observations_only():
    registry, _ledger, gate, _clock, _gate_clock = new_gated_system()
    client, _control, outcomes = start_gated_control(registry, gate)
    with _session(client) as session:
        beat = session.heartbeat()
        assert (beat.generation, beat.reason) == (registry.generation, 'ok')
        unknown = session.closeout('lease-does-not-exist')
        assert unknown.lease_state == unknown.closeout_state == 'unknown'
        assert unknown.lease_id == 'lease-does-not-exist'
        assert unknown.pending == unknown.in_flight == unknown.overdue == 0
        assert not hasattr(session, 'register')
        assert not hasattr(session, 'activate')
    assert outcomes.get(timeout=3).closeout == 'revoked'


def test_revocation_returns_distinct_receipt_and_closeout_without_secret():
    registry, _ledger, gate, _clock, _gate_clock = new_gated_system()
    client, _control, outcomes = start_gated_control(registry, gate)
    with _session(client) as session:
        manifest = golden_manifest()
        # Test-only setup of an installed lease. The Receiver client cannot
        # register or activate one, and this does not represent a Run permit.
        grant = registry.register(
            run_id=manifest.run_id, attempt_id=manifest.attempt_id,
            receiver_boot_id=session.receiver_boot_id, service='jira',
            scope_digest=manifest.digest, expires_at=1100.0,
            generation=session.generation,
        )
        gate.install_scope(grant=grant, manifest=manifest)
        revoked = session.revoke(grant.lease_id, reason='cancelled')
        assert revoked.generation == registry.generation
        assert revoked.lease_id == grant.lease_id
        assert revoked.reason == 'cancelled'
        assert revoked.closeout.lease_state == 'revoked'
        assert revoked.closeout.closeout_state == 'quiescent'
        assert revoked.closeout.pending == revoked.closeout.in_flight == 0
        assert grant.sentinel not in repr(revoked)
        assert SECRET.hex() not in repr(revoked)
        observed = session.closeout(grant.lease_id)
        assert observed.closeout_state == 'quiescent'
    assert outcomes.get(timeout=3).closeout == 'revoked'


def test_rejected_command_and_invalid_argument_fail_closed():
    registry, _ledger, gate, _clock, _gate_clock = new_gated_system()
    client, _control, outcomes = start_gated_control(registry, gate)
    with _session(client) as session:
        with pytest.raises(ReceiverControlError, match='control_argument_invalid'):
            session.revoke('bad id!', reason='cancelled')
        with pytest.raises(ReceiverControlError, match='control_rejected'):
            session.revoke('lease-does-not-exist', reason='cancelled')
        with pytest.raises(ReceiverControlError, match='control_session_closed'):
            session.heartbeat()
    assert outcomes.get(timeout=3).closeout == 'revoked'


def test_wrong_reply_sequence_closes_session(monkeypatch):
    registry, _ledger, gate, _clock, _gate_clock = new_gated_system()
    client, _control, outcomes = start_gated_control(registry, gate)
    with _session(client) as session:
        original = control_module.send_frame

        def wrong_sequence(sock, payload, *, timeout):
            if payload.get('op') == 'closeout' and payload.get('ok') is True:
                payload = {**payload, 'seq': payload['seq'] + 1}
            return original(sock, payload, timeout=timeout)

        monkeypatch.setattr(control_module, 'send_frame', wrong_sequence)
        with pytest.raises(ReceiverControlError, match='control_reply_invalid'):
            session.closeout('lease-does-not-exist')
        with pytest.raises(ReceiverControlError, match='control_session_closed'):
            session.heartbeat()
    assert outcomes.get(timeout=3).closeout == 'revoked'


@pytest.mark.parametrize('lease_state,closeout_state,overdue', [
    ('revoked', 'unknown', 0),
    ('active', 'open', 1),
])
def test_false_success_closeout_is_refused_and_closes_session(
    monkeypatch, lease_state, closeout_state, overdue,
):
    registry, _ledger, gate, _clock, _gate_clock = new_gated_system()
    client, _control, outcomes = start_gated_control(registry, gate)
    with _session(client) as session:
        original = control_module.send_frame

        def false_success(sock, payload, *, timeout):
            if payload.get('op') == 'closeout' and payload.get('ok') is True:
                payload = {**payload, 'result': {
                    **payload['result'], 'lease_state': lease_state,
                    'closeout_state': closeout_state, 'overdue': overdue,
                }}
            return original(sock, payload, timeout=timeout)

        monkeypatch.setattr(control_module, 'send_frame', false_success)
        with pytest.raises(ReceiverControlError, match='control_reply_invalid'):
            session.closeout('lease-does-not-exist')
        with pytest.raises(ReceiverControlError, match='control_session_closed'):
            session.heartbeat()
    assert outcomes.get(timeout=3).closeout == 'revoked'


def test_false_success_nested_revoke_closeout_is_refused(monkeypatch):
    registry, _ledger, gate, _clock, _gate_clock = new_gated_system()
    client, _control, outcomes = start_gated_control(registry, gate)
    with _session(client) as session:
        manifest = golden_manifest()
        grant = registry.register(
            run_id=manifest.run_id, attempt_id=manifest.attempt_id,
            receiver_boot_id=session.receiver_boot_id, service='jira',
            scope_digest=manifest.digest, expires_at=1100.0,
            generation=session.generation,
        )
        gate.install_scope(grant=grant, manifest=manifest)
        original = control_module.send_frame

        def false_success(sock, payload, *, timeout):
            if payload.get('op') == 'revoke' and payload.get('ok') is True:
                closeout = {**payload['result']['closeout'], 'closeout_state': 'unknown'}
                payload = {**payload, 'result': {
                    **payload['result'], 'closeout_state': 'unknown',
                    'closeout': closeout,
                }}
            return original(sock, payload, timeout=timeout)

        monkeypatch.setattr(control_module, 'send_frame', false_success)
        with pytest.raises(ReceiverControlError, match='control_reply_invalid'):
            session.revoke(grant.lease_id, reason='cancelled')
        with pytest.raises(ReceiverControlError, match='control_session_closed'):
            session.heartbeat()
    assert outcomes.get(timeout=3).closeout == 'revoked'


def test_boolean_revoked_at_cannot_equal_numeric_zero(monkeypatch):
    registry, _ledger, gate, _clock, _gate_clock = new_gated_system()
    client, _control, outcomes = start_gated_control(registry, gate)
    with _session(client) as session:
        manifest = golden_manifest()
        grant = registry.register(
            run_id=manifest.run_id, attempt_id=manifest.attempt_id,
            receiver_boot_id=session.receiver_boot_id, service='jira',
            scope_digest=manifest.digest, expires_at=1100.0,
            generation=session.generation,
        )
        gate.install_scope(grant=grant, manifest=manifest)
        original = control_module.send_frame

        def false_time(sock, payload, *, timeout):
            if payload.get('op') == 'revoke' and payload.get('ok') is True:
                payload = {**payload, 'result': {
                    **payload['result'], 'observed_at': 0.0, 'revoked_at': False,
                }}
            return original(sock, payload, timeout=timeout)

        monkeypatch.setattr(control_module, 'send_frame', false_time)
        with pytest.raises(ReceiverControlError, match='control_reply_invalid'):
            session.revoke(grant.lease_id, reason='cancelled')
        with pytest.raises(ReceiverControlError, match='control_session_closed'):
            session.heartbeat()
    assert outcomes.get(timeout=3).closeout == 'revoked'


def test_replaced_owner_leaves_previous_session_outcome_unknown():
    registry, _ledger, gate, _clock, _gate_clock = new_gated_system()
    client_a, control, outcomes_a = start_gated_control(registry, gate)
    session_a = _session(client_a)
    client_b, server_b = socket.socketpair()
    outcomes_b = queue.Queue()
    worker = threading.Thread(target=lambda: outcomes_b.put(control.serve_connection(server_b)))
    worker.start()
    with _session(client_b, boot='receiver-b') as session_b:
        with pytest.raises(ReceiverControlError, match='control_outcome_unknown'):
            session_a.heartbeat()
        assert session_b.closeout('lease-does-not-exist').closeout_state == 'unknown'
    session_a.close()
    assert outcomes_b.get(timeout=3).closeout == 'revoked'
    assert outcomes_a.get(timeout=5).closeout == 'not_owner'
    worker.join(timeout=3)


def test_lost_reply_leaves_session_terminal_and_outcome_unknown(monkeypatch):
    registry, _ledger, gate, _clock, _gate_clock = new_gated_system()
    client, _control, outcomes = start_gated_control(registry, gate)
    with _session(client) as session:
        original = control_module.send_frame

        def lose_closeout(sock, payload, *, timeout):
            if payload.get('op') == 'closeout' and payload.get('ok') is True:
                sock.close()
                return None
            return original(sock, payload, timeout=timeout)

        monkeypatch.setattr(control_module, 'send_frame', lose_closeout)
        with pytest.raises(ReceiverControlError, match='control_outcome_unknown'):
            session.closeout('lease-does-not-exist')
        with pytest.raises(ReceiverControlError, match='control_session_closed'):
            session.heartbeat()
    assert outcomes.get(timeout=3).closeout == 'revoked'


def test_bad_secret_does_not_create_session():
    registry, _ledger, gate, _clock, _gate_clock = new_gated_system()
    client, _control, outcomes = start_gated_control(registry, gate)
    with pytest.raises(ReceiverControlError, match='control_authentication_failed'):
        ReceiverControlSession(client, control_secret=b'x' * 32,
                               forwarder_uid=os.geteuid(),
                               receiver_boot_id='receiver-a', timeout=TEST_TIMEOUT)
    assert outcomes.get(timeout=3).authenticated is False
