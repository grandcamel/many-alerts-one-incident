# Ticket 23 documented stream normalizer

2026-09-22. Baseline 946e41a. **OFFLINE DOCUMENTED SUBSET / NATIVE QUALIFICATION NOT ASSESSED.**
[Plan](documented-stream-plan.md), [primary-source map](documented-stream-sources.md),
and [validation receipt](documented-stream-validation.json).

The new independent normalizer accepts bounded receiver-supplied JSON for init,
complete assistant messages, user text/tool results and one final result. It
checks session consistency, reported model agreement, unique tool pairing, exact
primitive types, receiver sequence/time, byte/event/depth limits and terminal
ordering. Unknown content/families, subagent/partial output and wrapper fallback
are held. It retains metadata and digests; it does not retain message or tool
payloads. Its source profile pins the official Python SDK types/parser.

Reported stream facts stay separate from supplied process observations. Timeout,
cancellation, capture loss and missing reaping/cleanup cannot become success from
terminal JSON. The most favorable status is `stream_consistent`; actual model and
provider actuals remain unknown, native qualification is `NOT_ASSESSED`, and every
outcome holds further dispatch. This module does not launch a client, change the
synthetic Transcript, connect to a live tool or release ledger reservations.

## Review and evidence

Terra implemented the module; Luna independently authored its adversarial tests.
A separate Luna reviewer checked the plan against pinned primary-source bytes and
reviewed implementation Standards. Root checked integration and source semantics.
Review corrections cover SDK nullable/object fields, reused tool IDs, per-event
hold reasons, receiver numeric overflow and sticky malformed process observations.
Independent review also corrected contradictory API-error success flags and invalid
tool-result content array members.
The tests exercise individual predicates with otherwise valid events.

The final full suite passed **744 tests, 36 skipped in 41.69s**, including **44**
new normalizer cases. Ruff and diff checks passed. Independent final Standards
review passed at the recorded source hash. Nine retained examples cover text/tool
consistency and held unpaired/wrapper/session/capture/timeout/containment/error cases.
The exact tests, reviewed hashes and outputs are recorded in the validation receipt. Primary-source bytes and generated offline examples live at
`/Users/jasonkrueger/maoi-ticket23-evidence/20260922-native-schema/` outside Git.
The prior 96-file packet is archived and hash-verified. No private native transcript
was ingested. No external headless review or paid experiment ran in this batch.

## Remaining dependencies

The documented subset is useful preparation, not proof of installed Claude 2.1.278
wire compatibility. Exact native event/permission/fallback behavior and supervised
client provenance remain unqualified. The next integration work is the mediated
client route and its fixed tool registration, with cancellation/revocation and
source/effect receipt correlation. Real spend must be reconciled before paid
admission; unknown exposure is not zero. Production audit custody/retention and
full durable-closeout timing remain open. Human Report grading and model/tenant/
venue qualification remain NOT RUN.

The user's approved rubric and standing aggregate experiment authorization below
$50 remain in force. This batch corrects stale ticket text that still described
those approvals as pending; it introduces no repeated cost-permission gate.
