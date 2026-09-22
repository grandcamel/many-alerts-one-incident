# Eyes, Report and Forwarder source checks

Read-only checks on 2026-09-22. This note records local CLI self-documentation,
installed source and public documentation. It does not establish a Run's tool
permission, network exchange, tenant grant, rendering, or accepted design.

## Jira command and payload construction

The installed `jira-as help` and `jira-as api call --help` advertise
`api call OPERATION --body @file|-`. `jira-as help adf` distinguishes Markdown
conversion from already encoded ADF and recommends raw read-back after writes.
The inspected `as-engine` package version is `0.1.1`; this is an engine package
version, not a claimed Jira CLI version. Its installed
`as_engine/params.py` SHA-256 is
`089ededf7c3457ce3e02565aa043cf092cf7bfe862bcf03179b02ded88203602`.
`build_body`, lines 313–349, reads `@file` as UTF-8 or `-` from supplied stdin,
then parses JSON. These branches do not enforce the new Report byte cap.

This proves a local payload-input capability. It does not prove that the Run's
`Read` plus approved `jira-as` command surface can create a payload file or use a
shell pipeline, that current permission checks accept it, or that a native
mediated request works. A future trusted body producer must bound and validate
bytes before invoking the CLI. Do not broaden shell permissions or replay a
possibly dispatched create to make the transport work.

Metadata returned by `jira-as api describe`:

| Operation ID | Native form | Narrowing required by the proposed Forwarder |
| --- | --- | --- |
| `searchAndReconsileIssuesUsingJqlPost` | POST `/rest/api/3/search/jql` | Trusted OPS/Incident and created-time candidate template, bounded continuation and fields; never arbitrary caller JQL. The spelling is the installed operation ID. |
| `getIssue` | GET `/rest/api/3/issue/{issueIdOrKey}` | Registered candidate/effect identity; validate returned project and type; fixed fields. |
| `createIssue` | POST `/rest/api/3/issue` | Fixed OPS/Incident bindings and explicit fields only; no bulk, properties, arbitrary transition or history metadata. |
| `editIssue` | PUT `/rest/api/3/issue/{issueIdOrKey}` | Accepted membership/state/Severity/Urgency operations only; preserve unrelated labels; no description rewrite or arbitrary field edit. |
| `addComment` | POST `/rest/api/3/issue/{issueIdOrKey}/comment` | New immutable Report revision body only; no author impersonation, visibility override or supplied identifiers/times. |
| `getComments` | GET `/rest/api/3/issue/{issueIdOrKey}/comment` | Bounded chronological revision retrieval; explicit missing/incomplete history. |
| `getComment` | GET `/rest/api/3/issue/{issueIdOrKey}/comment/{id}` | Direct read-back of a trusted receipt/history comment ID under its registered parent Incident; no expansion. |
| `doTransition` | POST `/rest/api/3/issue/{issueIdOrKey}/transitions` | Preflight-pinned workflow transition and required resolution; eligibility independent of HTTP success. |

The CLI metadata labels several writes `Risk: safe`. That classification does
not make them reads, establish authorization, or remove intent-before-dispatch
and unknown-effect handling. Tenant-specific field, workflow, project and type
IDs must come from trusted intended-venue preflight; historical IDs are evidence,
not portable bindings.

The [official enhanced-search API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/#api-rest-api-3-search-jql-post)
warns that recent changes may not be immediately visible. A negative search does
not prove an uncertain create never happened. Reconciliation must preserve that
uncertainty; generic search retry or automatic duplicate creation is not a fix.

The [official ADF structure](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/)
defines ordered JSON nodes under a versioned document root. It also warns that
schema inclusion alone does not guarantee implementation support. A syntactically
valid small JSON example is not proof of OPS rendering or native command acceptance.

## Repository authority

- [ADR 0006](../../../docs/adr/0006-one-incident-per-fault-and-match-is-a-judgment.md)
  and [ticket 14 Answer](../issues/14-many-to-one-under-a-cascade.md#answer) settle
  appended evidence/corrections, candidate admission and human-owned wrong-Match
  correction. Earlier WIP objections in that issue do not override its Answer.
- [ADR 0012](../../../docs/adr/0012-run-outcomes-and-recovery-are-explicit.md)
  permits one shorter evidence-backed attempt only after trusted proof that the
  intended mutation was not dispatched, within the original time budget.
- [ADR 0014](../../../docs/adr/0014-report-scoring-requires-supported-claims-and-human-review.md)
  and [audit specification](ticket-39/audit-specification.md) separate retrieval
  identity/linkage from named-human claim adjudication and private evidence.
- [Client configuration sources](ticket-23/client-configuration-sources.md)
  separate documented endpoint/trust settings from exact installed-client proof.
- [Local transport outcome](ticket-23/mediated-client-outcome.md) remains a
  bounded synthetic Python TLS fixture, not a five-service Forwarder, native
  incremental stream, OS isolation, tenant or billing acceptance.

## Grafana datasource mapping

The [official datasource API](https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/data_source/)
documents `GET /api/datasources/proxy/uid/:uid/*`. The wildcard describes
Grafana's general API, not the Run's allowlist: the proposed adapter admits only
registered UID/native-path/query combinations. The same page identifies these
as legacy `/api` routes in Grafana 13, still available but no longer updated.
Pin the deployed version and validate each selected datasource mapping before
use; no automatic switch to `/apis`, generic query or direct backend is implied.
