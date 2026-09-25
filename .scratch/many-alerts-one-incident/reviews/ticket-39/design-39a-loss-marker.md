# 39a: content-free local audit loss marker

Status: proposed offline codec slice, 2026-09-25. Ticket 39 remains open.
Authority: ADR 0014 and the proposed audit specification's explicit capture
loss, canonical-byte and quota boundaries. This unit is a pure local format,
not a capture writer, private store or clean-audit assertion.

## Pinned local record

An `audit_loss` version-1 payload has exactly these fields:
`schema_version`, `record_kind`, `loss_id`, `audit_bundle_id`, `exchange_id`,
`report_revision_id`, `side`, `state`, `loss_code`, `source`, `detected_phase`,
and `observed_at`. IDs are exact lowercase UUIDv4 strings. `side` is
`request|response|report`; the first two require `exchange_id` and a null
`report_revision_id`, while `report` requires the inverse. `state` is only
`missing|truncated|redacted|transport_error|unknown`; `empty` and `returned`
are not loss markers. A future `exchange-v1` writer must preserve a complete
zero-byte `empty` response and its own bounded code separately; rejecting it
here must never convert it to `missing` or discard that observation.
`loss_code` maps one-to-one to state:
`expected_record_missing|capture_truncated|support_removed|transport_failed|
unclassified_gap`. `source` is the fixed literal `unqualified_local`; a
fixture cannot claim native provenance. `detected_phase` is
`before_persistence|after_persistence`. `observed_at` is null or exact UTC
`YYYY-MM-DDTHH:MM:SS.ffffffZ`, a caller-supplied observation, not verified
clock evidence.

There are no freeform strings, source bodies, native IDs, credentials, account
identity, grades, support status or qualification fields. Strict canonical
UTF-8 JSON is capped at 1,024 bytes. A pure result carries the payload bytes,
byte count and SHA-256 externally; no self-hash is embedded. The codec accepts
only canonical bytes on decode, rejects duplicate keys and malformed or
unknown fields, and maps JSON failures to fixed non-diagnostic errors. The
per-bundle 1,024-record and 1 MiB loss limits are future writer obligations;
this codec's record cap does not claim either quota was reserved or durably
enforced.

## File-by-file plan

1. Add `grafana_jsm_sandbox/audit_loss.py` with a pure value/byte codec and
   immutable preflight result. No I/O, current time, writer, provenance or
   qualification function. Check lint.
2. Add `tests/test_audit_loss.py` for canonical known-answer bytes/digest,
   exact UUIDv4 and time syntax, side/ID matrix, every closed state/code,
   empty-vs-missing, duplicate/unknown keys, noncanonical bytes, wrong types,
   hostile values, bounded record size and local byte round-trip. Run focused
   tests and independent Standards/Spec source reviews.
3. Record ticket 39's truthful local status and outcome; run Ruff,
   `git diff --check` and the full repository suite before a named local
   code commit. Recheck protected #19/planning files and the panel; do not
   stage them.

## Acceptance boundary

No redactor, private store, manifest chain, append/read-back, quota, expiry,
native capture, operator review, clean qualification or human grade exists in
39a. All native, provider, paid, tenant, venue, human and protected-export
acceptance remains **NOT RUN**. A future writer must independently pin its
private storage technology, redaction engine/rules, access and encryption,
manifest anchor, loss overflow and retention behavior before positive use.
