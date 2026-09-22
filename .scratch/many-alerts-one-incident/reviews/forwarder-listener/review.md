# Independent security and design review: private control listener and shutdown

Date: 2026-09-22

Verdict: PASS for the bounded local source and synthetic integration scope in
`implementation-plan.md`. No unresolved security or design findings remain in
the reviewed files.

## Reviewed artifacts

- `grafana_jsm_sandbox/forwarder_listener.py`
  - SHA-256 `20be6cccf0ee71f3499d2748c568e0ce3e4012125016ca287ef90524a6fcfd83`
- `grafana_jsm_sandbox/forwarder_control.py`
  - SHA-256 `139b48ba36808795ff8183f63f0f7630c450a64ca1e1273fff2841162a705150`
- `tests/test_forwarder_listener.py`
  - SHA-256 `1925e3d6e0bc44e8aff015a3961a11df1de6c72aebe91c8ac6f9b5a2f8e9b826`
- `tests/test_forwarder_listener_control.py`
  - SHA-256 `514a183fbcaaafe5b367b04c98ff3bf0a868f67bf93f3be2c1ffa56e036c3577`

## Security and design assessment

The listener validates the configured parent descriptor and pathname identity,
owner, group and exact mode. It rejects noncanonical final path spellings that
can bypass `O_NOFOLLOW` through a trailing slash or `/.`. It creates the child
with directory-descriptor-relative operations, records identities before later
mutation, sets exact prepared and published modes without changing global
umask, bounds the complete filesystem socket path, and uses non-inheritable
listener and accepted descriptors.

Verification covers parent, child and socket pathname identities before and
after publication and around accept. Cleanup removes only recorded identities;
replacements and unexpectedly populated children are preserved with an
`unknown` closeout. Creation-failure cleanup accepts only the recorded child in
its known preparation/publication modes. Lifecycle state is locked around open,
endpoint, verification and close; accept releases that lock only for blocking
socket I/O, and close interrupts the pending accept before filesystem cleanup.

`ForwarderControl.shutdown()` atomically closes admission and holds the registry
before closing a snapshot of every tracked socket. The closed-state check occurs
before capacity admission under the same owner lock, so post-shutdown calls
return `control_closed` even while old handlers still occupy all four slots.
Authentication and every registry command recheck the shutdown latch under the
lock, while socket I/O and socket closing remain outside it. Held registry
closeout is retained as `unknown`; the code does not fabricate successful
revocation.

## Validation performed by this reviewer

- `pytest -q tests/test_forwarder_listener.py tests/test_forwarder_listener_control.py tests/test_forwarder_control.py`
  - `55 passed in 3.48s`
- `git diff --check` on the four reviewed files
  - passed with no output
- Direct host probe confirmed that macOS follows a final symlink when spelled
  with `/` or `/.`; the final implementation rejects those noncanonical inputs.

The repository-wide suite is intentionally not claimed here; the root
coordinator owns it under the repository instructions.

## Acceptance boundaries

This review covers source behavior and local synthetic same-UID filesystem and
socket tests only. It does not establish ancestor or mount stability, ACL
semantics, trusted group membership, distinct deployed Receiver/Forwarder/Run
identities, mounted-secret custody, provider or native behavior, actual
credentials, C2 acceptance, deployment, publication or commit status. The
listener is an I/O boundary; accepted sockets still require
`ForwarderControl` authentication and are not Run admission.
