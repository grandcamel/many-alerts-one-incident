# Telemetry, Change and reference integration

2026-09-22. Source and integration review for tickets 35, 41 and 43. This is
planning evidence, not deployment, tenant, exporter or model acceptance.

## Shared boundaries

| Surface | Writer and consumer | Required separation |
| --- | --- | --- |
| Run activity | Receiver projection; current-rehearsal Run reads and operator view | Sanitized diagnostics; never raw audit or scoring feedback; 24-hour policy |
| Change stages | Operator coordinator; current-rehearsal Eyes reads | Authenticated producer, stage-specific observations; seven-day policy; not proof of causation or recovery |
| Approved reference | Human curator/manifest; scoped Run read | Exact approved page/version/body identity; immediate revocation dominates frozen snapshot |
| Draft postmortem | Eligible completed Incident workflow; separate human curation | Registered Incident/page identity, draft-only writes and source-version binding; no publication or title adoption |
| Private audit | Operator capture/review | Correlation references only cross into other surfaces; no raw body or Ground truth in shared feeds |

A Run cannot gain authority by supplying a producer label, rehearsal identifier,
page title or claimed expected version. Trusted ingress/control binds those
values to the admitted identity. A dashboard filter is not access enforcement.
Read APIs must check the requested and returned scope, including metadata and
pagination, rather than trusting the request alone.

Telemetry delivery failure is best effort and cannot block required Incident
handling. Change delivery failure holds ordinary injection while leaving safe
operator recovery available. Optional Confluence failure leaves confirmed OPS
work intact. None permits replay of an uncertain mutation.

## Primary source findings

Reviewed current public documentation on 2026-09-22; exact deployed-version
compatibility still requires a pinned manifest and acceptance evidence.

Loki retention requires an enabled Compactor and supported index configuration.
Per-stream retention selectors use labels. Compaction removes index references
before an asynchronous sweeper deletes chunks; configured delays and scheduling
matter, and changing a policy does not retroactively apply it to existing data.
A `24h` or `168h` setting alone therefore does not prove exact physical expiry.
[Grafana retention documentation](https://grafana.com/docs/loki/latest/operations/storage/retention/)

Loki's native OTLP route requires structured metadata support. Its resource-to-
label mapping needs explicit control: defaults may index high-cardinality pod
and service-instance identities. Keep Run/session/rehearsal/Incident IDs in
bounded fields or structured metadata, not index labels, and verify the actual
collector-to-Loki mapping.
[OTLP ingestion](https://grafana.com/docs/loki/latest/send-data/otel/),
[default label controls](https://grafana.com/docs/loki/latest/get-started/labels/modify-default-labels/)

Kubernetes supports resource-version conflict detection and conditional patch
operations. RBAC resource-name restrictions are not a field-level write policy;
list/watch restrictions need matching name selectors, and collection deletion
cannot be constrained by resource name. The coordinator therefore needs its own
fixed resource/field checks and explicit mutation preconditions in addition to
scoped RBAC. The historical email undo's individual Pod deletion must bind a
freshly verified owner and UID; it cannot become arbitrary Pod deletion.
[API concepts](https://kubernetes.io/docs/reference/using-api/api-concepts/),
[RBAC scope](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)

## Resulting acceptance requirements

The query boundary must immediately exclude records outside the authorized
rehearsal or age window. Separately verify backend policy selection, marker
durability, deletion behavior, cache/object-store lifecycle and restart recovery.
Query filtering alone does not fulfill storage retention. If the accepted
retention requirement cannot be met, keep that deployment gate open; do not
silently reinterpret the ADR or delete unrelated system telemetry.

Use distinct trusted feed labels for Run and Change streams so retention rules
cannot collide. Test wrong/missing/forged labels, out-of-scope returned records,
late arrival, native exporter attributes, collector restart and disabled
structured metadata. Actual venue tests must establish the supported schema
and behavior; historical Compose probes do not supply that evidence.

The reference adapter must bind an update to a server-retained read receipt for
the source page/version/digest. A later client GET followed by incrementing the
latest version cannot authorize overwriting intervening edits with an old body.
This binds observable request provenance, not the model's internal composition
process. Unknown create identity remains a human reconciliation obligation.

## Review outcome and remaining gates

The retained planning drafts are [Run telemetry](ticket-35/telemetry-specification.md),
[Change coordination](ticket-41/change-specification.md), and
[Confluence reference/draft integration](ticket-43/confluence-specification.md).
Independent internal model review and root integration review checked their
shared authority, persistence, unknown-effect and privacy boundaries. These are
planning reviews, not an external headless review panel or human Report grading.

Review corrections include:

- Remove account/personal/repository values from telemetry; distinguish partial
  request usage from complete Run accounting and preserve restart identities.
- Treat native subprocess exporter inheritance as unverified; require explicit
  launcher isolation and installed-client acceptance rather than claiming a
  default strips exporter destinations or credentials.
- Bind the Change adapter to the historical nested ConfigMap JSON structure and
  exact cart variant, preserve unrelated configuration, and compare the injected
  state before restoring the recorded baseline. See the
  [recipe source check](ticket-41/recipe-source-check.md).
- Bind draft updates to one-use server-owned source receipts; serialize reference
  admission with revocation and record possible exposure before delivery.
- Keep distinct Run/Change/private-audit storage and retention boundaries, with
  bounded queues, queries and shared-database allocations.

Document checks and final source hashes are recorded in the
[validation receipt](telemetry-change-reference-validation.json). Runtime code
and tests were unchanged; no code suite rerun was required for this docs-only
batch. The latest code baseline remains `17037db` with 794 passed and 36 skipped.
This is a previous code-test result, not a validation of these new contracts.

Tickets 35, 41 and 43 remain open: Eyes/Forwarder interface integration, exact
native capability and intended-venue/tenant bindings still need evidence.
No model experiment, exporter, Kubernetes actuation, collector/retention probe,
Confluence tenant mutation or provisioning was run. No incremental paid
experiment was launched; historical provider charges remain unknown, not zero.
The next backlog batch is Eyes, compact Report and Forwarder (12, 16, 36).
