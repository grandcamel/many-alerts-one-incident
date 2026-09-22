# Eyes, compact Report and Forwarder integration

2026-09-22. Proposed contracts and source review for tickets 12, 16 and 36.
No ADR, Skill, production runtime, tool permission or deployment is changed.
The Eyes tool choice remains open; this batch does not replace or retry the
provider-blocked ticket-19 C2 path.

## Contract chain

| Boundary | Required result | What it cannot establish |
| --- | --- | --- |
| Eyes request | Fixed operation, trusted scope and bounded query | Diagnostic truth, tenant grants or arbitrary query authority |
| Forwarder dispatch | Correct service lease and validated native request; intent before a possible write | Successful execution, billing settlement, rollback or exactly-once tenant semantics |
| Returned evidence | Source identity, exact requested scope, time, bounded returned fields and visible gaps | Support for a claim merely because a tool returned successfully |
| Report revision | Compact observations/inferences linked to retrieved evidence and earlier revisions | Human semantic approval or a clean lifecycle despite earlier defects |
| Private audit | Correlated sanitized evidence sufficient to inspect a particular revision | Complete evidence when capture/redaction/truncation removed necessary support |

Every join must carry trusted Run/attempt/operation identity from admission or
transport observation. Caller text may propose a claim or selector; it cannot
create trusted provenance, expand service scope or certify its own effect.
`evidence_id` links a retained retrieval or explicit gap. It is not a portable
access token, a provider request ID or proof of claim support.

The public Report may refer to bounded query coordinates and returned values.
A dashboard URL is navigational context only: cite the retained retrieval, query
and time scope for the claim; the link alone does not establish returned data.
The private audit holds its own correlated sanitized evidence under ticket 39.
Shared activity telemetry remains the separate ticket-35 projection. An Eyes
response containing logs/spans is diagnostic evidence; it must never be copied
wholesale into the sanitized activity feed or used to expose scoring feedback.

## Scope and capability interactions

System metrics/logs/traces, Run activity and operator Changes have distinct
scope rules. System evidence uses the trusted demo namespace/resource binding
and requested bounded time range. Run activity additionally obeys same-rehearsal,
self/earlier-Run and age limits. Changes use their authenticated producer,
current-rehearsal and stage identities. A metric/log label provided by the Run
cannot attest any of those boundaries.

A trusted query builder may supply a fixed expression or structurally validated
query. Merely adding a selector string to arbitrary PromQL, LogQL or TraceQL is
not a safe scoping algorithm. Refuse unsupported query shapes; neither a Viewer
role nor response filtering alone establishes upstream request scope. Returned
records must also be validated, including metadata and continuation pages.

Kubernetes Pod GET is not a harmless raw response: Pod specifications can carry
literal environment secrets and command arguments. The proposed Eye returns only
the allowlisted diagnostic fields needed for status, restarts, termination and
endpoint membership. A service-account role restricting resource types does not
perform field redaction. Native client compatibility with that projection needs
its own offline test; unbounded discovery/watch is not implicitly authorized.

Candidate Jira reads preserve ticket 14's thirty-minute open-Incident admission
window. Reconciliation of an already uncertain effect is a separate trusted
operation and cannot forget its obligation when the candidate ages out or
search results lag. No negative search alone proves a create was not dispatched.
See the [source checks](eyes-report-forwarder-sources.md).

## Report and mutation interactions

Use the accepted appended-evidence/correction policy from ADR 0006. Keep the
initial Description and immutable chronological Report revisions, including
unsupported earlier assertions and explicit corrections. A later summary may
cite or supersede a revision; it cannot erase the earlier record or silently
turn an incomplete history into a complete one.

Measure serialized UTF-8 request bytes after ADF construction, escaping and
framing. A prose count, Python character count or historical command length is
not that measure. Explicit omission must weaken or remove unsupported claims;
shrinking a request cannot strip qualifications while retaining certainty.
Local CLI file/stdin support does not create a permitted way for a Run to write
files or invoke shell redirection. The selected bounded body transport must be
verified without widening the approved tool surface.

A denied mutation allows the single shorter Report attempt only after trusted
NOT_DISPATCHED evidence. Validation failure before send and a response lost
after possible send are different states. No HTTP status, timeout, model prose,
empty search or missing receipt silently authorizes a duplicate create/comment.
Confirmed OPS handling survives optional Confluence/export failure.

## Required cross-contract acceptance

Before implementation acceptance, exercise actual parser/client/transport seams
with synthetic backends for at least these cases:

1. Correct and wrong-service lease, restart generation and work deadline;
   stale handles and in-flight revocation without assuming rollback.
2. Fixed read templates versus cross-scope selectors, nested/encoded paths,
   unknown query fields, POST-based reads, forged producer/rehearsal metadata
   and backend replies outside the registered scope.
3. Pod environment/command/annotation secret sentinels removed before return;
   required termination reason retained; truncated status remains incomplete.
4. Empty retrieval versus missing/failed/truncated response; exact correlation
   survives transport failure, redaction and clock differences without invented
   native request identity.
5. Multi-byte Report content measured after final serialization; known
   NOT_DISPATCHED rejection gets at most one shorter attempt, whereas a lost
   create/comment response produces an unresolved effect and no automatic retry.
6. Appended revision/correction, incomplete paginated history, unsupported prior
   assertion, arithmetic operands and units, and human review remaining pending.
7. Direct network/credential/control access denied from the actual Run identity,
   including sibling-process introspection and alternate inherited descriptors.
   Local TLS fixtures alone do not satisfy this OS boundary.

Native clients, intended-venue routing and isolation, effective tenant/RBAC
grants, streamed provider behavior, cost reconciliation and human Report
adjudication remain separate gates. No paid experiment or external mutation is
part of this batch. Proposed contracts cannot widen the accepted authority.

## Review corrections and retained outcome

The [Eyes proposal](ticket-12/eyes-proposal.md),
[Report proposal](ticket-16/report-proposal.md), and
[Forwarder specification](ticket-36/forwarder-specification.md) were drafted by
bounded Terra/Luna workers and cross-reviewed by different internal workers,
with root integration review. This is internal source review, not an external
headless panel, named-human Report adjudication or deployment acceptance.

Review corrected the following material issues before retention:

- Preserve useful sanitized diagnostic log/span content while excluding Pod
  secrets, activity-feed raw content and operator-only evidence.
- Separate fixture/query/native provenance; keep missing/truncated/redacted
  evidence visible, name exact ADF node/mark forms and avoid self-hashing payloads.
- Put the first complete compact Report in the create Description, preserve
  immutable revisions, and stop new shorter attempts at the work deadline.
- Require strict native header framing and immutable attempt/lease identity.
  Optional Confluence failure cannot become mandatory route readiness.
- Specify layered process, syscall and network controls instead of attributing
  Unix-socket or sibling-container isolation to an Internet-connect filter.
- Bind possible writes to one-use trusted Receiver dispatch permits after durable
  intent. Bind every model request to the remaining whole-attempt exposure
  envelope; no reset of liability per call, connection or retry.
- Preserve the narrow structured Memory append authority and human-only member
  removal, with operator Change actuation outside the Run Kubernetes route.

The [validation receipt](eyes-report-forwarder-validation.json) records exact
reviewed hashes, document checks and any final nonsemantic normalization.
These files change no runtime or tests. The last code suite result remains
794 passed, 36 skipped at `17037db`; it is prior fixture evidence and does not
validate these new contracts. No full code suite was rerun for this docs-only
batch. No paid experiment was launched; unreconciled historical charges remain
unknown. Standing experiment authority stays cumulative and strictly below $50,
with technical and human-adjudication gates unchanged.

Tickets 12 and 16 remain open proposals rather than accepted replacement ADRs.
Ticket 36 remains open for final native/interface and intended-venue evidence.
The backlog advances next to Memory, venue lifecycle and audience specifications
(32, 42, 44); no further user input is needed for that local drafting work.
