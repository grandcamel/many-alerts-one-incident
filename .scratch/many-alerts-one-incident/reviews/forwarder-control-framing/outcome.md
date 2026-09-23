# Unit 14 scope delivery and control closeout outcome

2026-09-23. PASS for the fourteenth separately authorized local application
unit, baseline `74b10e8`. [validation.json](validation.json) records the final
verdict and evidence. The work is local only: nothing was pushed and no planning
ticket was closed.

## What the unit adds

Everything travels over the existing authenticated control connection. There is no second channel.

**Unscoped refusal in both modes.** `register` for a profiled service without a scope type (Confluence, Grafana, Kubernetes, Anthropic) fails with `scope_type_unavailable` before any registry call. Jira registration is unchanged, and so is gateless behavior for every other command.

**Attachment codec.** `forwarder_control_protocol` gains `send_attachment` and `recv_attachment`: one opaque attachment of 1 to 16,384 bytes whose length is declared twice. The declared lengths must match before any body byte is read. The 8 KiB JSON codec is unchanged.

**Scope policy.** `forwarder_control_scope` is pure. It pairs a gate with its registry, refuses unscoped services, validates and binds the manifest, maps install failures to fixed control codes, checks the installed entry's identity, and turns a gate closeout into either a codec-safe projection or a hold decision.

**Gated controller.** `ForwarderControl(..., gate=gate)` replaces `register` with `register_scoped`, a JSON header followed by a manifest attachment within two seconds. The manifest is fully validated before the registry changes. The lease is registered behind the owner fence, and the scope is installed with the control lock released. A post-install owner fence then runs before the sentinel reply. In gated mode:
- a Revoke reply adds `revoked_at`, `closeout_state` and a nested closeout observation, and `ok:true` only for `draining` or `quiescent` with no overdue flight;
- a new `closeout` command reports the same observation without spending authority;
- every uncertain observation (overdue, unknown for a known lease or after a revoke, inconsistent or unencodable) holds the registry before the `closeout_*` error frame.

## Review

- A design panel of three designs, two judges and a critic (13 issues) produced the plan. Root reconciled it against the 13b commit.
- Sonnet implementers and testers wrote three source changes and five test files, and reported no source defects.
- Four Opus lens reviewers:
  - Contract and fail-closed each reproduced one low-severity source defect: big-integer timestamps escaped `observe_closeout` without the hold. Root fixed it.
  - Concurrency found nothing.
  - Test adequacy killed all 11 targeted mutants and reported six test gaps.
- A Sonnet gap agent closed the six test gaps and killed nine mutants.
- A fresh reviewer bound the hashes: PASS with no source defects. Of 28 mutants, 22 were killed and 2 were equivalent. Of the 4 survivors, only one exposed a reachable gap: `scope_required` ordering before the schema check.
- Before commit, root closed that gap and pinned the install-code table, killing four more mutants. Root also removed two unused constants and corrected six documentation overclaims, mainly about the window after the post-install fence. The same reviewer re-verified the result ([review](review.md)).

## Validation

- Unit tests: **142** new tests in five files. With the committed `test_forwarder_control.py`, the six control files passed 165 in each of three runs.
- [Focused Forwarder suite](focused-tests.txt): **2626 passed**.
- [Full suite](full-suite.txt): **3500 passed, 36 skipped in 177.21s**, exit 0.
- Ruff (including line length), compile and `git diff --check` pass. Every existing test file is byte-identical, and among existing modules only `forwarder_control.py` and `forwarder_control_protocol.py` changed.

## Not qualified

- AuthorizeDispatch permits, `Ready`, or any non-Jira scope type;
- a Receiver control client, its heartbeat scheduling around a slow `register_scoped`, its polling policy and its scope-capacity bound;
- gate and registry pairing beyond generation equality (exclusive ownership stays a trusted-caller precondition);
- detection of an overdue flight that no control observation sees (a gate-side hold is deferred);
- closeout answers after 310 seconds, and any durable closeout record (ticket 37);
- Linux peer credentials, and deployed UID, mount, kernel or secret isolation;
- hard real-time drain bounds, and ledger clock divergence;
- a real upstream connection, native clients and deployment.

## Not performed and next

No provider, tenant or native call was made. No actual credential, C2 retry, paid experiment, deployment or human Report adjudication took place. The four protected dirty artifacts are unchanged and unstaged.

The Forwarder's local integration units now cover leases, control, listener, supervision, TLS, HTTP, receipts, routes, dispatch, the synthetic upstream and control framing. The next local work is the ticket-37 durable Receiver journal and recovery, then ticket-38 accounting, AuthorizeDispatch permits, a worker supervisor with readiness, and the guarded launcher. Planning ticket 36 remains open.
