# 19l closed synthetic startup barrier plan

Status: local source plan, 2026-09-25. Baseline: `26a0948`.
Authority: ADR 0012, ticket 37, reviewed 19d supervision design and 19h
claim-before-process order. The unit starts only a fixed synthetic Python
child. It does not expose a Run launcher or grant any lease or permit.

1. Add a prototype fixture with a fixed child program, two inherited
   one-way pipes, and a parent-owned handle. The child creates a new session,
   sends one blocked acknowledgment before reading exactly one release byte,
   and runs its inert marker action only after an exact release byte. EOF,
   wrong byte or malformed handoff exits closed. The child inherits neither
   pipe's parent end. No caller command, environment or endpoint is accepted.
2. Require parent observation of the blocked acknowledgment and same-session
   `pid == pgid == sid` before the fixture can send the release byte. Make
   release one-use. Provide bounded abort/reap and close every local descriptor
   on success and error. A parent-side close without release must deliver EOF
   and prevent the inert action. This is a synthetic handshake check, not a
   stable production containment attestation.
3. Exercise blocked-before-release, exact release, parent release-pipe loss,
   malformed release, duplicate release and failed attestation. Verify the
   marker cannot appear before release or after a closed handoff. Keep child
   waits bounded and reap it; do not infer external write absence from this
   fixture.
4. After fixture and tests, run focused tests and Ruff, independent Standards
   and Spec source reviews, protected dirty-file read-back, and the full
   local suite before a code commit. Stage only named 19l files.

Production still needs verified stable group identity across root exit,
durable launch/spawn observations, actual Forwarder grants and closeout,
Receiver accounting and the guarded Run caller. Native/provider/tenant and
intended-venue acceptance remain NOT RUN.
