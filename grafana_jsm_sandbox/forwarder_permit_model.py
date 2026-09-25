"""Isolated in-memory mechanics for a proposed one-use dispatch permit.

Staging a binding here does not authenticate a Receiver reply or authorize
dispatch. No runtime gate or route imports this module. A future integration
must separately prove the journal, accounting, grant, route and receipt gates.
"""

from __future__ import annotations

import dataclasses
import threading
from dataclasses import dataclass

from .forwarder_routes import ROUTE_CATALOG

MAX_OPEN_PERMITS = 32
MAX_LIFETIME_PERMITS = 2048
MAX_MONO_US = 2**53 - 1
_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
_HEX_CHARS = frozenset("0123456789abcdef")
_OPEN_PHASES = frozenset({"offered", "consumed_l1", "write_admitted"})


class PermitModelError(ValueError):
    """A fixed local-model rejection, never containing a caller value."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> None:
    raise PermitModelError(code) from None


def _safe_id(value: object) -> bool:
    return (type(value) is str and 1 <= len(value) <= 128
            and all(character in _ID_CHARS for character in value))


def _digest(value: object) -> bool:
    return (type(value) is str and len(value) == 64
            and all(character in _HEX_CHARS for character in value))


def _time(value: object) -> bool:
    return type(value) is int and 0 <= value <= MAX_MONO_US


@dataclass(frozen=True, slots=True)
class PermitBinding:
    permit_id: str
    receiver_boot_id: str
    forwarder_generation: str
    run_id: str
    attempt_id: str
    operation_id: str
    effect_intent_id: str
    grant_id: str
    flight_id: str
    service: str
    route_id: str
    request_digest: str
    target_digest: str
    expires_us: int


@dataclass(frozen=True, eq=False, slots=True)
class PermitHandle:
    """A book-owned identity; an equal-valued copy is never recognized."""

    permit_id: str


@dataclass(frozen=True, slots=True)
class PermitDecision:
    code: str
    reason: str
    phase: str | None


@dataclass(slots=True)
class _Entry:
    binding: PermitBinding
    phase: str = "offered"


def _valid_binding(binding: object, boot_id: str, generation: str) -> bool:
    if type(binding) is not PermitBinding:
        return False
    ids = (
        binding.permit_id, binding.receiver_boot_id, binding.forwarder_generation,
        binding.run_id, binding.attempt_id, binding.operation_id,
        binding.effect_intent_id, binding.grant_id, binding.flight_id,
    )
    route = ROUTE_CATALOG.get(binding.route_id) if type(binding.route_id) is str else None
    return (
        all(_safe_id(value) for value in ids)
        and binding.receiver_boot_id == boot_id
        and binding.forwarder_generation == generation
        and route is not None
        and type(binding.service) is str
        and route.service == binding.service
        and _digest(binding.request_digest)
        and _digest(binding.target_digest)
        and _time(binding.expires_us)
    )


def _snapshot_binding(
    binding: object, boot_id: str, generation: str,
) -> PermitBinding | None:
    """Copy caller fields before validation; only this private copy enters a lock."""
    if type(binding) is not PermitBinding:
        return None
    snapshot = dataclasses.replace(binding)
    return snapshot if _valid_binding(snapshot, boot_id, generation) else None


class PermitBook:
    """Bounded owner of mechanical L1/L2 state, without dispatch authority."""

    def __init__(self, *, receiver_boot_id: str, forwarder_generation: str) -> None:
        if not _safe_id(receiver_boot_id) or not _safe_id(forwarder_generation):
            _fail("permit_argument")
        self._boot_id = receiver_boot_id
        self._generation = forwarder_generation
        self._entries: dict[PermitHandle, _Entry] = {}
        self._permit_ids: set[str] = set()
        self._operation_ids: set[str] = set()
        self._open = 0
        self._lock = threading.Lock()

    def stage(self, binding: PermitBinding, *, now_us: int) -> PermitHandle:
        """Stage an untrusted claim for mechanics tests; never authenticate it."""
        snapshot = _snapshot_binding(binding, self._boot_id, self._generation)
        if not _time(now_us) or snapshot is None:
            _fail("permit_argument")
        if snapshot.expires_us <= now_us:
            _fail("permit_expired")
        with self._lock:
            if snapshot.permit_id in self._permit_ids or snapshot.operation_id in self._operation_ids:
                _fail("permit_duplicate")
            if self._open >= MAX_OPEN_PERMITS or len(self._entries) >= MAX_LIFETIME_PERMITS:
                _fail("permit_capacity")
            handle = PermitHandle(snapshot.permit_id)
            self._entries[handle] = _Entry(snapshot)
            self._permit_ids.add(snapshot.permit_id)
            self._operation_ids.add(snapshot.operation_id)
            self._open += 1
            return handle

    def _entry(self, handle: object) -> _Entry | None:
        if type(handle) is not PermitHandle:
            return None
        return self._entries.get(handle)

    def _close(self, entry: _Entry) -> None:
        if entry.phase in _OPEN_PHASES:
            self._open -= 1
            entry.phase = "closed"

    def close(self, handle: PermitHandle) -> None:
        """Retire local use, without making a receipt or external-effect claim."""
        with self._lock:
            entry = self._entry(handle)
            if entry is None:
                _fail("permit_unknown")
            self._close(entry)

    def phase(self, handle: PermitHandle) -> str:
        with self._lock:
            entry = self._entry(handle)
            if entry is None:
                _fail("permit_unknown")
            return entry.phase

    def _attempt(
        self, fence: str, handle: PermitHandle, expected: PermitBinding, *,
        receiver_boot_id: str, forwarder_generation: str, now_us: int,
    ) -> PermitDecision:
        # Validate exact scalar types before locking: dataclass annotations do
        # not prevent a caller from installing an object with a running __eq__.
        expected_snapshot = _snapshot_binding(expected, self._boot_id, self._generation)
        valid_arguments = (
            expected_snapshot is not None and _time(now_us) and _safe_id(receiver_boot_id)
            and _safe_id(forwarder_generation)
        )
        with self._lock:
            entry = self._entry(handle)
            if entry is None:
                return PermitDecision(fence + "_denied", "unknown_handle", None)
            if not valid_arguments:
                self._close(entry)
                return PermitDecision(fence + "_denied", "invalid_argument", entry.phase)
            required = "offered" if fence == "l1" else "consumed_l1"
            if entry.phase != required:
                self._close(entry)
                return PermitDecision(fence + "_denied", "phase", entry.phase)
            if (receiver_boot_id != self._boot_id
                or forwarder_generation != self._generation):
                self._close(entry)
                return PermitDecision(fence + "_denied", "stale_context", entry.phase)
            if now_us >= entry.binding.expires_us:
                self._close(entry)
                return PermitDecision(fence + "_denied", "expired", entry.phase)
            if expected_snapshot != entry.binding:
                self._close(entry)
                return PermitDecision(fence + "_denied", "binding_mismatch", entry.phase)
            entry.phase = "consumed_l1" if fence == "l1" else "write_admitted"
            return PermitDecision(fence + "_pass", "exact", entry.phase)

    def attempt_l1(
        self, handle: PermitHandle, expected: PermitBinding, *,
        receiver_boot_id: str, forwarder_generation: str, now_us: int,
    ) -> PermitDecision:
        return self._attempt(
            "l1", handle, expected, receiver_boot_id=receiver_boot_id,
            forwarder_generation=forwarder_generation, now_us=now_us,
        )

    def attempt_l2(
        self, handle: PermitHandle, expected: PermitBinding, *,
        receiver_boot_id: str, forwarder_generation: str, now_us: int,
    ) -> PermitDecision:
        return self._attempt(
            "l2", handle, expected, receiver_boot_id=receiver_boot_id,
            forwarder_generation=forwarder_generation, now_us=now_us,
        )


__all__ = [
    "MAX_LIFETIME_PERMITS", "MAX_OPEN_PERMITS", "PermitBinding", "PermitBook",
    "PermitDecision", "PermitHandle", "PermitModelError",
]
