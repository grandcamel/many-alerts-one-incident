# Ticket 23 documented stream normalizer plan

2026-09-22. Baseline 946e41a. Offline source work only.

1. Pin the official SDK source map and define one fixed documented subset; do not
   change the synthetic Transcript or wire a native launcher.
2. Terra implements the bounded normalizer and its module documentation. Luna
   independently tests the fixed public contract. Root integrates source evidence
   and checks the boundary between reported stream facts and process observations.
3. Obtain independent Standards review, resolve findings, run the complete suite,
   retain offline examples and exact hashes, update the packet chain and commit
   locally. No paid model invocation, push, ticket resolution or native acceptance.

## Fixed public contract

New module `prototype/run_timing/documented_stream.py` defines `DocumentedStream`,
`ProcessObservation`, `StreamRecord`, and `StreamOutcome` (frozen dataclasses for
returned values). Constructor: `DocumentedStream(attempt_id, requested_model, *,
max_events=1000, max_line_bytes=65536, max_total_bytes=1048576, max_depth=32)`.
Exact positive integer configurable bounds: events <=10000, line <=1048576,
total <=16777216, depth <=64. Required IDs/models are nonempty strings <=200 chars.

`feed(raw: bytes, *, sequence: int, received_at: float) -> StreamRecord` consumes
one JSON object, with receiver sequence starting at 1 and increasing contiguously,
and finite nonnegative monotonically nondecreasing receiver time. A record contains
attempt_id, sequence, received_at, raw_bytes (length), raw_sha256, kind, accepted, reasons,
reported_session_id, reported_model, proposed_tool_ids, returned_tool_ids. Retain
metadata only; record digests identify submitted bytes, not authenticated origin.
Malformed external input is returned as a rejected record and leaves sticky hold
reasons. Programmer misuse (non-bytes or invalid receiver metadata) raises
ValueError AND leaves sticky reasons; no later input repairs that failure. Once a
capture bound is exceeded stop parsing/retaining further event state. Returned
records and outcomes are detached immutable values. No public list of raw payloads.

Strict UTF-8, one JSON object, no duplicate keys, nonfinite numbers (including
1e999), excessive depth or malformed types. Parse bounds apply to the entire
object, including unused fields. Unknown event families/content blocks reject
with sticky `unsupported_event`/`unsupported_content`. Optional unknown keys on
recognized objects may be ignored after structural bounds; this is a documented
subset, not a full versioned native JSON Schema.

Supported: `system/init`, complete `assistant`, `user`, final `result`, with fields
and subtypes as in `documented-stream-sources.md`. Text blocks require string text.
Assistant tool_use requires bounded id/name and object input. User tool_result
requires known unmatched bounded tool_use_id; optional nonnull is_error must be exact bool
and true records `tool_error`. User text/string content is permitted. Do not retain
text, tool inputs/results or arbitrary optional metadata. Subagent output (nonnull
parent_tool_use_id), partial streams, fallback wrappers and other families reject.
Init model is only observed metadata; only assistant models populate reported_models.
Assistant model mismatch creates a hold. Optional session_id, when present on any
supported message, must be a bounded string and agree with all prior observations.
Final result requires session_id, exact nonnegative ints duration_ms,
duration_api_ms,num_turns, exact bool is_error and one known subtype. Exactly one
terminal and no records after it. Unresolved tool proposals hold at outcome time.
Optional terminal_reason must be one of the documented values; aborted reasons
record cancellation; api_error/max_turns imply failure even if subtype says success.
Optional total_cost_usd is a finite nonnegative JSON number (not bool/string) parsed
as Decimal without float rounding, retained as reported_estimate_usd only. Optional
usage must be object; known input_tokens/output_tokens, if present, exact nonnegative
ints. Usage fields are not billing actuals. Optional nonempty permission_denials,
deferred_tool_use, errors or assistant error produce diagnostic hold, never approval.
Known optional diagnostic fields are typed, unknown keys remain ignored and bounded.
SDK-nullable fields accept explicit null as absence. Tool-result content permits text,
array of objects or null; a nonnull api_error_status always records failure.
Result origin is an object with string kind; deferred_tool_use is an
object with id/name/input; structured_output may be any bounded JSON value.
Reported diagnostics make status incomplete. Seen tool IDs cannot be reused after
a result. Returned record reasons preserve per-event semantic holds. Invalid process
observations also leave a sticky incomplete reason, even if later corrected.

`outcome(observation: ProcessObservation) -> StreamOutcome` preserves separate
reported facts and supplied process observations. ProcessObservation fields:
exit_code (int or None), capture_complete, root_reaped, group_gone, pipes_closed,
timed_out=False, cancelled=False, spawn_failed=False (all flags exact bool).
Malformed observation raises ValueError. Outcome fields: attempt_id, source_profile (pinned source revision), status, reasons,
reported_models (tuple), reported_session_id, reported_estimate_usd (Decimal/None),
actual_model=None, provider_actual_usd=None, native_qualification='NOT_ASSESSED',
further_dispatch='hold'. Status precedence: containment_failed (unreaped/group/pipes),
spawn_failed, timed_out, cancelled, incomplete (capture/parse/schema/order/identity/
pairing/diagnostic/terminal/exit missing), failed (nonzero exit or reported error),
stream_consistent. Even stream_consistent is only offline internal consistency;
never native completion, accepted experiment, authenticated tool effects or spend.

Do not require init first; plugin events can precede init in the wider native
schema, but this subset still holds those unsupported events. No fallback-success
classification, no ledger release and no process launch in this module.
