# 35a: Receiver-only telemetry gap bytes

Status: proposed local source design, 2026-09-25. Ticket 35 stays open.
Authority: accepted ADR 0010 and the proposed ticket-35 telemetry envelope.
This unit is a pure codec for synthetic Receiver gap records; it is not a
Receiver projection caller, queue, collector, native exporter or retention
control.

## Source correction and closed grammar

Use `feed=run_gaps` for `telemetry_omitted` and `telemetry_gap`. The ticket-35
table currently lists those kinds under `run_events`; amend the table and
keep the shared `feed=run` stream label distinct from the record's `feed`
field. There is no native gap emitter in this unit.

The canonical v1 record has exactly the schematic envelope fields plus
`marker_source_id`: `schema_version=1`, `feed=run_gaps`, a computed
`projected_event_id`, `run_id`, `rehearsal_id`, null
`producer_instance_id`/`native_session_id`/`associations`,
`projection_generation`, nonnegative `projection_seq`,
`event_kind=telemetry_omitted|telemetry_gap`,
`source={class:receiver,version:receiver_projection_v1}`, nullable
`observed_at`, required `ingested_at`, a closed `payload`, and `loss` equal
to a one-element array containing `payload.loss_code`. Run/rehearsal,
generation and marker-source IDs are exact lowercase UUIDv4 values in this
local synthetic grammar. Times are exact UTC microsecond strings; they remain
caller assertions until a trusted Receiver owns them.

`payload` has only `loss_code`, `count`, `first_observed_at`,
`last_observed_at`, `affected_projection_seq_first` and
`affected_projection_seq_last`. For the two Receiver omission codes and
`projection_sequence_gap`, count is a known positive safe integer and both
affected sequence endpoints are known nonnegative integers with first <=
last. Count cannot exceed the number of sequence positions in that range.
For `delivery_unknown` after restart, count or the sequence pair may
be null when genuinely unobservable; a supplied count is still positive.
Times are nullable and, when both are present, ordered. Sequence
endpoints are always both null or both nonnegative safe integers with first
<= last.
No zero count, free text, raw event name, unknown key/value echo, credentials,
account identity, Ground truth, prompts, tool bodies or citation audit body.
The initial closed codes are `unknown_receiver_shape` and
`receiver_privacy_rejected` for `telemetry_omitted`, and
`projection_sequence_gap` and `delivery_unknown` for `telemetry_gap`.
Queue/drop/metric/native codes wait for their actual producer contract.

The Receiver must mint `marker_source_id` once at marker creation and assign
generation and sequence before enqueue. It is the marker's
`source_record_id` for ticket 35's general Receiver identity rule. The codec
computes SHA-256 over the ASCII bytes `maoi.run-gap.v1`, followed by one NUL
byte (`0x00`), followed by canonical JSON of `[run_id,
projection_generation, projection_seq, event_kind, marker_source_id]`.
The hash is stable across byte-identical
retries and does not incorporate a mutable coalesced count or range. Marker
bytes must be frozen before retry, and a changed body under the same event ID
is a conflict. This codec validates syntax and computes an ID; it cannot
attest that Receiver minted the source ID or that a queue actually froze the
record. Any later transport/queue implementation must enforce that.

Canonical UTF-8 record bytes are capped at 2,048 bytes for this local marker
subset, stricter than the proposed 64 KiB general telemetry bound. An
external immutable preflight result carries bytes, byte count and SHA-256.
Decode requires canonical bytes and all fixed fields. The proposed 64 KiB/
16 KiB/2 KiB/depth-8/array-256 record limits, queue 4,096/32 MiB global and
512/4 MiB per Run, batch 256/1 MiB and two retries/5 seconds, and query
10,000/1 MiB/30 seconds/five calls are implementation proposals, not ADR
acceptance or verified runtime settings. Accepted ADR 0010 requires bounded
best effort, visible loss, stable identity and 24-hour shared retention.

## File-by-file implementation plan

1. Correct the `run_events`/`run_gaps` table in the ticket-35 proposed spec,
   then add this reviewed design. No live source behavior changes.
2. Add pure `grafana_jsm_sandbox/telemetry_gap.py` with a strict encode/decode
   preflight and fixed errors. Run focused syntax/lint checks.
3. Add `tests/test_telemetry_gap.py` for exact identity/digest, code-kind
   matrix, null/zero/unknown distinctions, time/sequence ordering, unknown
   keys and prohibited content, malformed/duplicate/noncanonical JSON,
   hostile Python values, cap, and byte read-back. Run focused tests.
4. Obtain independent Standards/Spec source reviews, run Ruff and
   `git diff --check`, then the full repository suite before a named local
   code commit. Verify protected #19/planning files and panel before stage.

## Boundary

The codec neither emits nor delivers telemetry. Receiver identity mapping,
source authenticity, per-Run queue and coalescing, retry/duplicate handling,
collector configuration, current native event/metric inventory, backend
retention, Eyes/Forwarder read scope, audience rendering and tenant/venue
proof remain open. Ticket 39's private citation audit is separate. Native,
provider, paid, tenant, venue and human acceptance are **NOT RUN**.
