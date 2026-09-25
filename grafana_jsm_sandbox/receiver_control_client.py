"""Receiver-side revocation and closeout over authenticated Forwarder control.

The caller supplies an already connected private Unix stream socket. This
session cannot register or activate a lease, and none of its observations
authorize a Run, effect, budget transition or release of a durable hold.
"""

from __future__ import annotations

import math
import socket
import threading
from dataclasses import dataclass
from functools import wraps
from typing import Self

from .forwarder_control import MAX_SEQUENCE, authenticate_receiver
from .forwarder_control_protocol import ControlProtocolError, recv_frame, send_frame
from .forwarder_control_scope import CLOSEOUT_FIELDS, MAX_CLOSEOUT_COUNT, MAX_TIME_INT
from .forwarder_dispatch import CLOSEOUT_STATES, LEASE_STATES
from .forwarder_leases import REVOCATION_REASONS

_ID_CHARS = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.')
_RECEIPT_FIELDS = frozenset({
    'operation', 'generation', 'lease_id', 'service', 'state', 'reason',
    'authorized', 'observed_at',
})


class ReceiverControlError(ValueError):
    """Fixed uncertainty code; never carries a reply, secret or sentinel."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class HeartbeatObservation:
    generation: str
    reason: str
    observed_at: float


@dataclass(frozen=True, slots=True)
class CloseoutObservation:
    generation: str
    lease_id: str
    lease_state: str
    closeout_state: str
    pending: int
    in_flight: int
    overdue: int
    uncertain: int
    drain_deadline: float | None
    observed_at: float


@dataclass(frozen=True, slots=True)
class RevocationObservation:
    generation: str
    lease_id: str
    reason: str
    revoked_at: float
    closeout: CloseoutObservation


def _check(condition: bool, code: str = 'control_reply_invalid') -> None:
    if not condition:
        raise ReceiverControlError(code)


def _id(value: object) -> bool:
    return type(value) is str and 1 <= len(value) <= 128 and all(
        character in _ID_CHARS for character in value)


def _time(value: object) -> bool:
    if type(value) is int:
        return 0 <= value <= MAX_TIME_INT
    return type(value) is float and math.isfinite(value) and value >= 0


def _close(sock: socket.socket) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


def _serialized(method):
    @wraps(method)
    def invoke(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return invoke


def _closeout(value: object, *, generation: str, lease_id: str) -> CloseoutObservation:
    _check(type(value) is dict and value.keys() == set(CLOSEOUT_FIELDS))
    _check(value['generation'] == generation and value['lease_id'] == lease_id)
    lease_state, state = value['lease_state'], value['closeout_state']
    _check(type(lease_state) is str and lease_state in LEASE_STATES and
           type(state) is str and state in CLOSEOUT_STATES)
    counts = tuple(value[key] for key in ('pending', 'in_flight', 'overdue', 'uncertain'))
    _check(all(type(number) is int and 0 <= number <= MAX_CLOSEOUT_COUNT
               for number in counts))
    pending, in_flight, overdue, uncertain = counts
    observed_at, deadline = value['observed_at'], value['drain_deadline']
    _check(_time(observed_at) and (deadline is None or _time(deadline)))
    _check((deadline is None) == (in_flight == 0))
    _check((state != 'open' or lease_state in ('registered', 'active')) and
           (lease_state not in ('registered', 'active') or state in ('open', 'unknown')) and
           (lease_state != 'unknown' or state == 'unknown') and
           (state != 'overdue' or overdue >= 1) and
           (state != 'draining' or (in_flight >= 1 and overdue == 0)) and
           (state != 'quiescent' or (in_flight == 0 and overdue == 0)))
    # These are success-only properties of the Forwarder adapter. A known
    # lease with unknown closeout, or any overdue flight, is a refusal there.
    _check(overdue == 0 and (state != 'unknown' or lease_state == 'unknown'))
    return CloseoutObservation(generation, lease_id, lease_state, state,
                               pending, in_flight, overdue, uncertain,
                               deadline, observed_at)


class ReceiverControlSession:
    """One sequential authenticated session; any ambiguity closes it."""

    def __init__(self, sock: socket.socket, *, control_secret: bytes,
                 forwarder_uid: int, receiver_boot_id: str, timeout: float = 10.0):
        _check(type(sock) is socket.socket, 'control_socket_invalid')
        self._sock = sock
        self._lock = threading.RLock()
        self._closed = False
        self._sequence = 1
        self._timeout = timeout
        failed = False
        try:
            authenticated = authenticate_receiver(
                sock, control_secret=control_secret, forwarder_uid=forwarder_uid,
                receiver_boot_id=receiver_boot_id, timeout=timeout,
            )
        except (ControlProtocolError, OSError):
            failed = True
        if failed:
            self._closed = True
            _close(sock)
            raise ReceiverControlError('control_authentication_failed') from None
        self.generation = authenticated.generation
        self.receiver_boot_id = authenticated.receiver_boot_id

    def close(self) -> None:
        with self._lock:
            self._closed = True
            _close(self._sock)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_unused: object) -> None:
        self.close()

    def _request(self, op: str, params: dict) -> dict:
        with self._lock:
            _check(not self._closed, 'control_session_closed')
            if self._sequence > MAX_SEQUENCE:
                self._closed = True
                _close(self._sock)
                raise ReceiverControlError('control_sequence_exhausted')
            sequence = self._sequence
            transport_failed = False
            try:
                send_frame(self._sock, {'op': op, 'seq': sequence, 'params': params},
                           timeout=self._timeout)
                reply = recv_frame(self._sock, timeout=self._timeout)
            except (ControlProtocolError, OSError):
                transport_failed = True
            if transport_failed:
                self._closed = True
                _close(self._sock)
                raise ReceiverControlError('control_outcome_unknown') from None
            self._sequence += 1
            if (type(reply) is dict and reply.keys() == {'op', 'seq', 'ok', 'error'} and
                    reply.get('op') == op and type(reply.get('seq')) is int and
                    reply['seq'] == sequence and reply.get('ok') is False and
                    type(reply.get('error')) is str):
                self._closed = True
                _close(self._sock)
                raise ReceiverControlError('control_rejected')
            valid = (type(reply) is dict and reply.keys() == {'op', 'seq', 'ok', 'result'} and
                     reply.get('op') == op and type(reply.get('seq')) is int and
                     reply['seq'] == sequence and reply.get('ok') is True and
                     type(reply.get('result')) is dict)
            if not valid:
                self._closed = True
                _close(self._sock)
                raise ReceiverControlError('control_reply_invalid')
            return reply['result']

    @_serialized
    def heartbeat(self) -> HeartbeatObservation:
        result = self._request('heartbeat', {})
        valid = (
            result.keys() == _RECEIPT_FIELDS and
            result['operation'] == 'heartbeat' and
            result['generation'] == self.generation and
            result['lease_id'] is None and result['service'] is None and
            result['state'] == 'connected' and
            result['reason'] in ('ok', 'late_recovered') and
            result['authorized'] is None and _time(result['observed_at'])
        )
        if not valid:
            self.close()
            raise ReceiverControlError('control_reply_invalid')
        return HeartbeatObservation(self.generation, result['reason'], result['observed_at'])

    @_serialized
    def closeout(self, lease_id: str) -> CloseoutObservation:
        _check(_id(lease_id), 'control_argument_invalid')
        result = self._request('closeout', {'lease_id': lease_id})
        invalid = False
        try:
            observed = _closeout(result, generation=self.generation, lease_id=lease_id)
        except ReceiverControlError:
            invalid = True
        if invalid:
            self.close()
            raise ReceiverControlError('control_reply_invalid') from None
        return observed

    @_serialized
    def revoke(self, lease_id: str, *, reason: str) -> RevocationObservation:
        _check(_id(lease_id) and type(reason) is str and reason in REVOCATION_REASONS,
               'control_argument_invalid')
        result = self._request('revoke', {'lease_id': lease_id, 'reason': reason})
        valid = (
            result.keys() == _RECEIPT_FIELDS | {'revoked_at', 'closeout_state', 'closeout'} and
            result['operation'] == 'revoke' and result['generation'] == self.generation and
            result['lease_id'] == lease_id and result['service'] == 'jira' and
            result['state'] == 'revoked' and result['reason'] == reason and
            result['authorized'] is None and _time(result['observed_at']) and
            _time(result['revoked_at']) and
            result['revoked_at'] == result['observed_at']
        )
        if not valid:
            self.close()
            raise ReceiverControlError('control_reply_invalid')
        invalid = False
        try:
            observed = _closeout(result['closeout'], generation=self.generation,
                                 lease_id=lease_id)
        except ReceiverControlError:
            invalid = True
        if invalid or (observed.lease_state not in ('revoked', 'pruned') or
                       observed.closeout_state not in ('quiescent', 'draining') or
                       result['closeout_state'] != observed.closeout_state or
                       observed.overdue != 0):
            self.close()
            raise ReceiverControlError('control_reply_invalid') from None
        return RevocationObservation(self.generation, lease_id, reason,
                                     result['revoked_at'], observed)

__all__ = [
    'CloseoutObservation', 'HeartbeatObservation', 'ReceiverControlError',
    'ReceiverControlSession', 'RevocationObservation',
]
