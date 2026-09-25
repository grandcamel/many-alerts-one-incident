# 19s: no-writer execution observation and assessment replay

Status: proposed local source design, 2026-09-25. Fixed point: `af2bb62`.
Authority: ADR 0012, ticket 37's proposed recovery specification, reviewed
19h ordering, and current pure `run_outcome.assess_execution`. This unit
does not capture a child, authenticate terminal output, settle effects,
release a Run hold or classify a production Run.

## Source boundary

The v3 journal replays a launch and cleanup claims but has no durable
terminal/process observation or derived assessment. The current pure
classifier accepts `ProcessFacts` and a tuple of `TerminalFacts`; those
facts lack an authenticated Receiver capture source. No stable containment
witness, trusted pipe EOF, audit custody or current Forwarder closeout is
available. A future writer must establish those independently. Replayed
`succeeded` is therefore always an **unqualified derived claim** and cannot
be consumed as a clean Run, retry entitlement, effect confirmation or budget
settlement.

## Private record family

Use three one-record recovery commits in order:
`process_observation`, `terminal_observation`, `execution_assessment`.
Each binds the current journal/Run/attempt, launch claim event/digest, exact
predecessor head, same Receiver boot and monotonic observation, and a
tagged self-digest. Each is at most once for the single current Run, with
body ceilings 4,096, 4,096 and 2,048 bytes. At 384 bytes overhead each,
the family worst-case is 11,392 recovery bytes. It creates no escrow;
future writer preflight must add this to the 19n/q/r and reconciliation
recovery obligations. No raw process output, command, prompt, tool body,
credential, account identity, scoring data or Ground truth enters a record.

`process_observation` carries the exact closed `ProcessFacts` scalar fields
and one digest of the sanitized source bundle. It records Receiver-observed
spawn/exit/timeout/cancellation/containment claims separately from a
reported terminal. `containment="confirmed"` is a caller-supplied claim,
not proof of stable group absence or Forwarder quiescence. The codec and
planner use the current pure classifier's process validation to reject
wrong types, impossible exit code/signal combinations and invalid enums.
The observation can append after a dispatch hold or outer hard deadline to
retain history, but only in the original launch boot; a restart needs a
separate recovery observation. It does not erase cleanup action unknowns.
`failed_before_process` is rejected if this launch already has a replayed
spawn attestation: a claimed no-process path cannot coexist with recorded
blocked-child evidence or produce `never_started=True` from that prefix.
Even without attestation, the no-process claim remains unqualified until a
future writer proves the actual failed-before-process boundary.
Any process observation is a one-time closeout snapshot: once it replays,
new spawn attestation, release intent and effect intent claims stop. Existing
release intents may still receive historical release observations; existing
effect intents may still receive historical receipts, and cleanup claims may
continue. The derived assessment therefore cannot precede a newly planned
positive action in the same Run.

`terminal_observation` is one bounded summary of terminal evidence after
the process observation. It has `count_class` `none`, `one`, or `multiple`.
For `none`, every other terminal field is null. For `multiple`, only a
lowercase SHA-256 digest of the entire bounded sanitized source bundle is
present; quality, invalidity code and parsed fields are null. For `one`,
the same source-bundle digest is mandatory and quality is `recognized` or
`invalid`. Invalid data has one closed code from `parse_invalid`,
`shape_invalid`, `field_invalid`, `contradictory`, and every parsed field is
null. Recognized data has a null invalidity code and exact `TerminalFacts`
subtype, boolean error indicator and usage state, plus a separately named
nullable `reason_code` from `reported_error`, `provider_unavailable`,
`interrupted`, `runtime_error`, `unknown_error`. Success requires null;
error may have null or one of these codes. A future Receiver parser maps
native terminal text to a code and retains the source bundle outside this
claim; this no-writer unit trusts no such mapping. The record never stores
the original reason string: assessment reconstruction passes the code as
the bounded `TerminalFacts.reason`. The current classifier depends only on
whether that string is nonempty, so this normalization preserves its
decision while separately exposing the sanitized reason category. The
digest authenticates neither the source nor its custody. This preserves missing,
duplicate and malformed distinctions without retaining raw bytes or
silently repairing contradictions. The parser/source of those labels is
not authenticated in this unit. A later historical summary cannot replace
an earlier one; conflicting or duplicate commits fail replay.

`execution_assessment` binds both claim event IDs/digests and stores the
exact `ExecutionAssessment` state, sorted reason tuple, usage and
never-started boolean. Pure planning reconstructs the classifier input:
none -> empty tuple, multiple -> two fixed valid sentinel facts (the
classifier checks count first), invalid one -> one fixed invalid sentinel,
recognized one -> the normalized facts with the closed reason code. It invokes
`run_outcome.assess_execution` and records only that derived result.
Replay re-derives and byte-compares the plan; a forged/recomputed state,
reason, usage or predecessor fails. The sentinels exist only inside this
pure adapter and can never be mistaken for a captured terminal. A claimed
assessment may append only after both observations, in the same boot, and
does not clear a Run/effect/accounting hold even if its state is
`succeeded`.

## Replay, inspection and acceptance

The v1 state digest stays unchanged; each new claim has its own tagged
projection digest. Live/stopped inspection shows counts, digests, reported
terminal count/quality and derived state if present, always under
`execution_unqualified`. It must not call the result a final Run outcome.
The source exposes no public writer. Mixed-version reopen, old-decoder
`journal_schema_unsupported`, forged records, duplicate/conflict,
missing/multiple/invalid terminal, process precedence, capacity, late
historical observation and restart refusal need focused tests. A future
writer must bind capture completeness, stable containment, real group/EOF,
current Forwarder closeout and private audit provenance before using this
classification for any positive decision. Native, provider, paid, tenant,
venue, power-loss and human acceptance are **NOT RUN**.
