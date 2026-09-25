"""Closed synthetic child startup barrier; never a production Run launcher.

The fixed child performs no external work. Its sole post-release action is to
write one byte to a private observation pipe. This fixture tests pipe and
session ordering, not durable launch evidence or stable containment identity.
"""

from __future__ import annotations

import os
import select
import subprocess
import sys
from dataclasses import dataclass
from typing import Self

_CHILD = r"""
import os
import sys
release_fd = int(sys.argv[1])
observe_fd = int(sys.argv[2])
os.write(observe_fd, b'B')
if os.read(release_fd, 1) == b'R':
    os.write(observe_fd, b'A')
    os._exit(0)
os._exit(66)
"""


class SyntheticBarrierError(ValueError):
    """Fixed failure code; never contains a process, path or environment value."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(slots=True)
class SyntheticBarrier:
    """Parent side of one fixed, fail-closed synthetic child handshake."""

    process: subprocess.Popen[bytes]
    _release_fd: int | None
    _observe_fd: int | None
    _attested: bool = False
    _decided: bool = False

    def _read(self, timeout: float) -> bytes | None:
        fd = self._observe_fd
        if fd is None:
            raise SyntheticBarrierError("observation_closed") from None
        ready, _, _ = select.select([fd], [], [], timeout)
        return os.read(fd, 1) if ready else None

    def observe(self, *, timeout: float = 0.0) -> bytes | None:
        """Return one observation byte, EOF, or None on timeout."""
        if type(timeout) not in (int, float) or not 0 <= timeout <= 2:
            raise SyntheticBarrierError("invalid_timeout") from None
        return self._read(timeout)

    def attest_blocked(self) -> None:
        """Check the fixed child reached its barrier as a session leader."""
        if self._attested or self._decided:
            raise SyntheticBarrierError("handoff_decided") from None
        try:
            blocked = self._read(2.0)
            pid = self.process.pid
            valid = (blocked == b"B" and self.process.poll() is None
                     and os.getpgid(pid) == pid and os.getsid(pid) == pid)
        except (OSError, ValueError):
            valid = False
        if not valid:
            self.close()
            raise SyntheticBarrierError("attestation_failed") from None
        self._attested = True

    def decide(self, value: bytes) -> None:
        """Send exactly one byte or close; only ``R`` releases the child."""
        if not self._attested or self._decided or type(value) is not bytes or len(value) != 1:
            raise SyntheticBarrierError("handoff_invalid") from None
        fd = self._release_fd
        if fd is None:
            raise SyntheticBarrierError("handoff_closed") from None
        self._decided = True
        self._release_fd = None
        sent = False
        try:
            sent = os.write(fd, value) == 1
        except OSError:
            pass
        finally:
            os.close(fd)
        if not sent:
            self.close()
            raise SyntheticBarrierError("handoff_failed") from None

    def close(self) -> None:
        """Close release authority and reap with two bounded two-second waits."""
        self._decided = True
        fd, self._release_fd = self._release_fd, None
        try:
            if fd is not None:
                os.close(fd)
            try:
                self.process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                # The fixed child has no descendants. This is not a production
                # process-group containment claim.
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass
                self.process.wait(timeout=2.0)
        except (OSError, subprocess.SubprocessError):
            raise SyntheticBarrierError("reap_failed") from None
        finally:
            fd, self._observe_fd = self._observe_fd, None
            if fd is not None:
                os.close(fd)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_unused: object) -> None:
        self.close()


def launch_synthetic_barrier() -> SyntheticBarrier:
    """Create only the fixed inert child, blocked until an exact decision."""
    try:
        release_read, release_write = os.pipe()
    except OSError:
        raise SyntheticBarrierError("pipe_failed") from None
    try:
        observe_read, observe_write = os.pipe()
    except OSError:
        os.close(release_read)
        os.close(release_write)
        raise SyntheticBarrierError("pipe_failed") from None
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", _CHILD,
             str(release_read), str(observe_write)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env={}, close_fds=True,
            pass_fds=(release_read, observe_write), start_new_session=True,
        )
    except (OSError, subprocess.SubprocessError):
        for fd in (release_read, release_write, observe_read, observe_write):
            os.close(fd)
        raise SyntheticBarrierError("spawn_failed") from None
    os.close(release_read)
    os.close(observe_write)
    return SyntheticBarrier(process, release_write, observe_read)


__all__ = ["SyntheticBarrier", "SyntheticBarrierError", "launch_synthetic_barrier"]
