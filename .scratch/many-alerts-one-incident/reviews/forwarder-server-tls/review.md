# Fixed service TLS listener independent review

## Early contract review

The exclusive-context transfer is necessarily a trusted-operator contract:
Python cannot prevent a party retaining the original mutable `SSLContext`
reference from mutating it later. The implementation should therefore require
the exact `ssl.SSLContext` type and `PROTOCOL_TLS_SERVER`, mark that exact
instance as claimed before later work can race, and treat an already-marked or
unmarkable context as a fixed rejection. It must neither expose a context getter
nor use a default/fallback context.

The fixed SNI callback must compare the supplied name exactly to the selected
profile DNS name and return `ALERT_DESCRIPTION_UNRECOGNIZED_NAME` for `None` or
every mismatch. It must not switch contexts or infer a default service. TLS
settings need explicit TLS-1.2 minimum, `MAXIMUM_SUPPORTED` maximum, `CERT_NONE`,
and exactly `http/1.1` ALPN after ownership is claimed.

The main implementation risk is descriptor handoff under concurrent close:

- Mark the accept operation active before releasing the state lock for raw
  accept. Publish each accepted descriptor under that operation before any
  wrapping transition; close must be able to snapshot and interrupt either raw
  or wrapped ownership.
- During raw-to-SSL transfer, retain a safe handle until `wrap_socket` proves
  transfer. Never use a failed wrapper object's `fileno()` as a substitute for
  verified `detach()` ownership; a recycled descriptor could otherwise be
  closed incorrectly.
- Keep the nonblocking accept gate independent of the state lock. `close()`
  must not wait for it, must leave already-returned TLS sockets alone, and must
  return `unknown` while an active accept operation is still unwinding.
- Latch an unconfirmed descriptor close permanently. A later close may observe
  an operation exit, but cannot turn a prior close failure into `closed`.

## Final hash-bound source and test review

Reviewed source SHA-256
`3d38ffbeb8d3bd2f9d2c25aa752a94b2e0fcee0ecf6c3ddfc25342b40924e37a`,
unit-test SHA-256
`c9ed8e45676b1e147159c4516fb1f85e643292ddb7dbe7ea743118b3dca756dd`,
and root integration-test SHA-256
`9e9f1416606e5c4fc7112ee3e4c3c9d9fc633fc2f4c3db3f0da7e875411394a6`.

Verdict: **PASS (source and test review)**.

The implementation claims the exact trusted server context atomically before
hardening it, provides no mutable context accessor, and has no fallback context
or service selection. It configures the specified TLS/ALPN profile and uses an
exact SNI callback that rejects absent and mismatched names with the required
alert. The context remains an explicit operator-trust boundary rather than an
assertion of key or certificate custody.

The listener binds only the fixed IPv4 loopback profile address, has one-shot
lifecycle, and uses a nonblocking accept gate. The accepted descriptor is held
as an active operation before raw acceptance, then explicitly transferred to
the wrapper with handshake disabled. Close can interrupt the listener or the
in-flight raw/wrapped descriptor, leaves returned connections alone, and keeps
an unknown closeout sticky after any unconfirmed descriptor close. The shared
deadline is spent over polling accept and explicit TLS handshake, with finite
and non-regressing monotonic checks. The final unit revision adds raw and
handshake failure cases where listener-timeout restoration raises an unexpected
`RuntimeError`: the original fixed setup error remains visible, the accept gate
is released, and the listener permanently reports unknown.

The inspected integration coverage composes this listener with the strict
client and HTTP parser across all services, rejects missing/cross-service SNI,
checks ALPN, bounds plaintext/stalled handshakes, exercises close during accept
and handshake, verifies actual fixed-port exclusivity without killing an
occupant, and confirms a returned connection survives listener close. Unit
coverage exercises context claims, lifecycle, deadline faults, gate contention,
raw/wrapped cleanup, sticky unknown cleanup, and close races.

Static checks run by this reviewer (`python -m py_compile`, `ruff check`, and
`git diff --check`) passed for the reviewed files. The source lane reported 30
focused unit tests passing; this reviewer did not rerun them. Root-owned
integration and full-suite evidence remains separate. No source/test edit,
network/native/provider, credential, C2, full-suite, commit, or push action was
performed by this reviewer.
