# Private control listener and shutdown: local implementation plan

2026-09-22. Baseline `2fd58d2`, explicitly pushed by the user before this unit.
Existing separate local source/test approval covers this work. No deployment,
real credential loading, provider/native operations or C2 work is included.

## Ownership and sequence

1. Terra owns `grafana_jsm_sandbox/forwarder_listener.py`: private filesystem Unix
   listener, permission/identity checks, bounded accepts and conservative cleanup.
   A separate worker owns `tests/test_forwarder_listener.py`.
2. Root adds permanent `ForwarderControl.shutdown()` and connection tracking in
   the existing control module, plus `tests/test_forwarder_listener_control.py`
   for actual filesystem-socket integration and shutdown. Root owns docs/evidence.
3. Independent security review, focused tests, full repository suite, then local
   commit. Preserve the four unrelated dirty files. Later work remains local;
   the requested push of the prior four commits ends at `2fd58d2`.

## Listener API and trust boundary

`PrivateControlListener(parent, *, owner_uid, control_gid)` takes an absolute
operator-provisioned runtime parent path. `.open()` creates one fresh owned child
and returns self; `.endpoint` returns its pathname only while open.
`.verify()` checks its admitted filesystem identities and permissions.
`.accept(*, timeout=0.1)` returns one accepted socket or None on timeout;
`.close()` returns frozen `ListenerCloseout(state, reason)`, where state is
`removed`, `unknown` or `not_open`. Repeated close is idempotent; an instance
cannot reopen. `ListenerError(ValueError)` carries fixed `.code` and no raw paths.
One caller may accept at a time. Lifecycle changes and filesystem guards are
serialized under a short lock; the lock is released while accept waits, allowing
close to interrupt a pending accept. The caller still submits returned sockets
through the controller's permanent shutdown/admission gate.

The parent must be a real directory (O_DIRECTORY|O_NOFOLLOW), owned by the
configured UID, with that UID equal to current effective UID; its group must
equal the configured trusted control group and mode must be exactly 0710.
Parent ancestors must already be stable and protected by the operator's namespace
and mount policy. This module does not attest all ancestors, ACLs, group
membership or mount isolation. Parent pathname identity is checked against its
opened directory descriptor before/after publication and during verification.
Noncanonical lexical parent paths, including trailing slash/dot components and
leading double slashes, are rejected before opening. This prevents final-symlink
spellings from defeating O_NOFOLLOW on the observed Darwin host.

Create a random `fc-<16 hex>` child exclusively with mode 0700 using the parent
directory descriptor. Set its group to the configured control group, then its
mode to 02700 while preparing the socket. Bind a fixed `control.sock` inside it,
without unlinking any pre-existing entry and without changing process-wide umask.
The published endpoint has owner UID/control GID, mode 0660 and socket type.
Publish the child as mode 02710 only after socket setup. This grants the trusted
control group traversal without directory listing or mutation; Run exclusion
still requires independently established group and mount separation.

Conservatively bound the complete filesystem socket path to 100 encoded bytes.
Use AF_UNIX/SOCK_STREAM, listen backlog 4 and non-inheritable descriptors. No
abstract namespace, TCP or alternate endpoint fallback. Never alter the parent's
mode/ownership or read a mounted secret. Check open directory identities and
socket type/owner/group/mode before and after accept; on guard failure close any
newly accepted socket and raise a fixed error. Accept timeout is finite, positive
and at most one second; it is not a peer-authentication result.

Cleanup closes the listening descriptor and uses anchored dir_fd operations to
remove only the recorded socket inode and owned child directory. A replaced,
unknown or unexpectedly populated path must be preserved and yield `unknown`;
do not delete another endpoint, recursively remove a directory or sweep stale
paths. The parent is never deleted. Group members cannot rename child entries;
same-UID/operator filesystem mutation and ancestor/mount stability remain trust
assumptions, not a claimed portable atomic path-unlink guarantee. Creation failure
cleans only recorded owned resources, preserving unexpected entries.

## Control shutdown and integration

`ForwarderControl.shutdown()` permanently prevents new admissions, holds its
registry before closing sockets and interrupts every tracked accepted connection,
including unauthenticated connections. Track no more than the existing four
connection slots. Synchronize admission/tracking with shutdown under the owner
lock; do not hold that lock across socket I/O. Subsequent serve calls close their
socket and return fixed `control_closed` diagnostics. Existing closeout exceptions
retain held/unknown semantics, never synthetic revocation success.

The caller shuts down control before removing its listener. Listener.accept is
an I/O boundary, not authentication or Run admission: accepted sockets must go
through ForwarderControl. A managed accept/worker supervisor and deployment entry
point remain subsequent integration work; this unit does not silently wire the
legacy launcher or start a resident service.

## Validation

Use short temporary directories with synthetic group/UID predicates. Exercise
creation/read-back, real connect/accept, malformed/insecure parent, symlinks,
wrong identity/mode, socket replacement, unknown entries, bounded accept,
descriptor cleanup and idempotent close. Verify no deletion of unrelated entries
or mutation of the parent. Root integration proves authenticated registration on
the pathname, shutdown holding active authority and releasing pending handlers,
post-shutdown rejection and cleanup. Local same-UID tests do not prove distinct
deployed Receiver/Forwarder/Run identities or mounted-secret custody.
