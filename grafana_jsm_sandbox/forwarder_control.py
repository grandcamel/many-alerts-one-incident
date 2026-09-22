"""Authenticated control of a lease registry over accepted Unix stream sockets.

The caller owns listener/mount provisioning and exclusive ownership of the
registry. This module never loads credentials, starts a listener or grants a
network dispatch permit. Only the authenticated Register reply carries a sentinel.
"""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import secrets
import socket
import struct
import sys
import threading
from dataclasses import dataclass

from .forwarder_control_protocol import ControlProtocolError, recv_frame, send_frame
from .forwarder_leases import LeaseError, LeaseRegistry

MAX_CONNECTIONS = 4
MAX_SEQUENCE = 2**31 - 1
_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
_HEX = frozenset("0123456789abcdef")
_PARAMETERS = {
    "register": {"run_id", "attempt_id", "service", "scope_digest", "expires_at"},
    "activate": {"lease_id", "launch_at"},
    "revoke": {"lease_id", "reason"},
    "heartbeat": set(),
}
_GRANT_FIELDS = ("generation", "lease_id", "run_id", "attempt_id", "receiver_boot_id",
                 "service", "scope_digest", "expires_at", "sentinel")
_RECEIPT_FIELDS = ("operation", "generation", "lease_id", "service", "state", "reason",
                   "authorized", "observed_at")


@dataclass(frozen=True)
class ControlOutcome:
    reason: str
    authenticated: bool
    commands: int
    closeout: str


@dataclass(frozen=True)
class AuthenticatedControl:
    generation: str
    receiver_boot_id: str


@dataclass(eq=False)
class _Owner:
    boot: str
    sock: socket.socket


def peer_uid(sock: socket.socket) -> int:
    """Obtain the kernel's Unix-stream peer UID, or deny on unsupported hosts.

    Darwin's libc getpeereid reports effective IDs at connection establishment.
    Linux uses SO_PEERCRED; neither branch accepts a caller-supplied wire UID.
    """
    try:
        if sock.family != socket.AF_UNIX or sock.getsockopt(
            socket.SOL_SOCKET, socket.SO_TYPE
        ) != socket.SOCK_STREAM:
            raise ControlProtocolError("peer_identity_unavailable")
        sock.getpeername()  # A listener or unconnected socket is not a peer.
        if sys.platform == "darwin":
            getpeereid = ctypes.CDLL(None, use_errno=True).getpeereid
            getpeereid.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint),
                                  ctypes.POINTER(ctypes.c_uint)]
            getpeereid.restype = ctypes.c_int
            uid, gid = ctypes.c_uint(), ctypes.c_uint()
            if getpeereid(sock.fileno(), ctypes.byref(uid), ctypes.byref(gid)) != 0:
                raise ControlProtocolError("peer_identity_unavailable")
            result = uid.value
        elif sys.platform.startswith("linux") and hasattr(socket, "SO_PEERCRED"):
            raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("iII"))
            _pid, result, _gid = struct.unpack("iII", raw)
        else:
            raise ControlProtocolError("peer_identity_unavailable")
        _uid(result)
        return result
    except (OSError, AttributeError, ValueError, struct.error):
        raise ControlProtocolError("peer_identity_unavailable") from None


def _uid(value: object) -> None:
    if type(value) is not int or not 0 <= value < 2**32 - 1:
        raise ControlProtocolError("invalid_peer_uid")


def _configuration(secret: bytes, uid: int, timeout: float) -> None:
    if type(secret) is not bytes or len(secret) != 32:
        raise ControlProtocolError("invalid_control_secret")
    _uid(uid)
    if type(timeout) not in (int, float) or not 0 < timeout <= 10:
        raise ControlProtocolError("invalid_timeout")


def _id(value: object) -> None:
    if type(value) is not str or not 1 <= len(value) <= 128 or any(
        char not in _ID_CHARS for char in value
    ):
        raise ControlProtocolError("invalid_identity")


def _hex(value: object) -> None:
    if type(value) is not str or len(value) != 64 or any(char not in _HEX for char in value):
        raise ControlProtocolError("invalid_proof")


def _keys(value: object, expected: set[str]) -> None:
    if type(value) is not dict or set(value) != expected:
        raise ControlProtocolError("invalid_schema")


def _proof(secret: bytes, role: str, generation: str, challenge: str, boot: str) -> str:
    message = f"{role}\0{generation}\0{challenge}\0{boot}".encode("ascii")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _close(sock: socket.socket) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


def authenticate_receiver(
    sock: socket.socket, *, control_secret: bytes, forwarder_uid: int,
    receiver_boot_id: str, timeout: float = 10.0,
) -> AuthenticatedControl:
    """Authenticate both peer UID and Forwarder proof on the Receiver side.

    The caller keeps the socket on success; failure closes it. This return value
    records a handshake, not continuing lease, route or dispatch authority.
    """
    try:
        _configuration(control_secret, forwarder_uid, timeout)
        _id(receiver_boot_id)
        if peer_uid(sock) != forwarder_uid:
            raise ControlProtocolError("peer_uid_mismatch")
        challenge = recv_frame(sock, timeout=timeout)
        _keys(challenge, {"op", "generation", "challenge"})
        if challenge["op"] != "challenge":
            raise ControlProtocolError("invalid_challenge")
        generation, nonce = challenge["generation"], challenge["challenge"]
        _id(generation)
        _hex(nonce)
        send_frame(sock, {
            "op": "hello", "receiver_boot_id": receiver_boot_id,
            "proof": _proof(control_secret, "receiver", generation, nonce, receiver_boot_id),
        }, timeout=timeout)
        reply = recv_frame(sock, timeout=timeout)
        _keys(reply, {"op", "ok", "generation", "receiver_boot_id", "proof"})
        if (reply["op"] != "hello" or reply["ok"] is not True or
                reply["generation"] != generation or reply["receiver_boot_id"] != receiver_boot_id):
            raise ControlProtocolError("authentication_failed")
        _hex(reply["proof"])
        expected = _proof(control_secret, "forwarder", generation, nonce, receiver_boot_id)
        if not hmac.compare_digest(reply["proof"], expected):
            raise ControlProtocolError("authentication_failed")
        return AuthenticatedControl(generation, receiver_boot_id)
    except Exception:
        _close(sock)
        raise


class ForwarderControl:
    """Own one registry's authenticated controller session and bounded connections."""

    def __init__(self, registry: LeaseRegistry, *, receiver_uid: int,
                 control_secret: bytes, timeout: float = 10.0):
        _configuration(control_secret, receiver_uid, timeout)
        if not isinstance(registry, LeaseRegistry):
            raise ControlProtocolError("invalid_registry")
        self._registry = registry
        self._receiver_uid = receiver_uid
        self._secret = control_secret
        self._timeout = timeout
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        self._owner: _Owner | None = None

    def serve_connection(self, sock: socket.socket) -> ControlOutcome:
        """Serve and close an accepted socket; return fixed nonsecret diagnostics.

        A malformed or rejected command terminates the session. ``commands``
        counts schema-valid commands submitted to the registry, including a
        rejected registry operation. Closeout is unknown if disconnect failed.
        """
        if not self._slots.acquire(blocking=False):
            _close(sock)
            return ControlOutcome("connection_capacity", False, 0, "not_owner")
        owner = None
        authenticated = False
        commands = 0
        reason = "eof"
        closeout = "not_owner"
        operation, sequence = "error", None
        try:
            if peer_uid(sock) != self._receiver_uid:
                raise ControlProtocolError("peer_uid_mismatch")
            generation = self._registry.generation
            nonce = secrets.token_hex(32)
            send_frame(sock, {"op": "challenge", "generation": generation, "challenge": nonce},
                       timeout=self._timeout)
            hello = recv_frame(sock, timeout=self._timeout)
            _keys(hello, {"op", "receiver_boot_id", "proof"})
            if hello["op"] != "hello":
                raise ControlProtocolError("authentication_required")
            boot = hello["receiver_boot_id"]
            _id(boot)
            _hex(hello["proof"])
            expected = _proof(self._secret, "receiver", generation, nonce, boot)
            if not hmac.compare_digest(hello["proof"], expected):
                raise ControlProtocolError("authentication_failed")
            owner = _Owner(boot, sock)
            with self._lock:
                previous = self._owner
                if previous is not None:
                    self._disconnect(previous)
                try:
                    self._registry.handshake(receiver_boot_id=boot, generation=generation)
                except Exception:
                    self._registry.hold()
                    raise
                self._owner = owner
                authenticated = True
            if previous is not None:
                _close(previous.sock)
            send_frame(sock, {
                "op": "hello", "ok": True, "generation": generation,
                "receiver_boot_id": boot,
                "proof": _proof(self._secret, "forwarder", generation, nonce, boot),
            }, timeout=self._timeout)
            for expected_sequence in range(1, MAX_SEQUENCE + 1):
                operation, sequence = "error", None
                request = recv_frame(sock, timeout=self._timeout)
                _keys(request, {"op", "seq", "params"})
                operation, sequence = request["op"], request["seq"]
                if type(operation) is not str or operation not in _PARAMETERS:
                    operation, sequence = "error", None
                    raise ControlProtocolError("unknown_operation")
                if type(sequence) is not int or sequence != expected_sequence:
                    sequence = None
                    raise ControlProtocolError("invalid_sequence")
                params = request["params"]
                _keys(params, _PARAMETERS[operation])
                with self._lock:
                    if self._owner is not owner:
                        raise ControlProtocolError("session_replaced")
                    commands += 1
                    result = getattr(self._registry, operation)(
                        receiver_boot_id=boot, generation=generation, **params
                    )
                    fields = _GRANT_FIELDS if operation == "register" else _RECEIPT_FIELDS
                    projection = {key: getattr(result, key) for key in fields}
                # No diagnostic copy of this payload is retained. A Register
                # grant includes its sentinel solely for the authenticated peer.
                send_frame(sock, {"op": operation, "seq": sequence, "ok": True,
                                  "result": projection}, timeout=self._timeout)
            reason = "sequence_exhausted"
        except (ControlProtocolError, LeaseError) as exc:
            reason = exc.code
            # Error reporting can block or fail too. Remove authority before
            # attempting any diagnostic response to the rejected connection.
            released = self._release_owner(owner)
            if released is not None:
                closeout = released
            if reason != "eof":
                try:
                    send_frame(sock, {"op": operation, "seq": sequence, "ok": False,
                                      "error": reason}, timeout=self._timeout)
                except (ControlProtocolError, OSError):
                    pass
        except Exception:  # noqa: BLE001 - diagnostics must not expose exception inputs.
            # Exception details can contain inputs or authentication material.
            reason = "internal_failure"
        finally:
            released = self._release_owner(owner)
            if released is not None:
                closeout = released
            _close(sock)
            self._slots.release()
        return ControlOutcome(reason, authenticated, commands, closeout)

    def _release_owner(self, owner: _Owner | None) -> str | None:
        with self._lock:
            if owner is None or self._owner is not owner:
                return None
            self._owner = None
            try:
                self._disconnect(owner)
                return "revoked"
            except Exception:  # noqa: BLE001 - failure is held and unknown, never success.
                return "unknown"

    def _disconnect(self, owner: _Owner) -> None:
        try:
            self._registry.disconnect(receiver_boot_id=owner.boot,
                                      generation=self._registry.generation)
        except Exception:
            self._registry.hold()
            raise
