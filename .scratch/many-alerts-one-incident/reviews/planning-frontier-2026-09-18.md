# Planning frontier after ticket 40 approval

Snapshot after commit `3e17793`, derived from the issues' actual Status and Blocked by fields. No blocker is removed or measurement ticket resolved by this report.

| Ticket | Status | Unresolved declared prerequisites |
| --- | --- | --- |
| 12 | open | 19 |
| 16 | open | 12 |
| 19 | claimed | none |
| 23 | open | none |
| 32 | open | 16 |
| 35 | open | 12 |
| 36 | open | 12 |
| 37 | open | 16, 36 |
| 38 | open | 36, 37 |
| 39 | open | 16 |
| 41 | open | 12 |
| 42 | open | 37, 38, 39, 41 |
| 43 | open | 16 |
| 44 | open | 32, 35, 39, 43 |

Ticket 19 is claimed, prepared and NOT RUN; it requires client/transport and model measurements before Eyes (12) can select tools. Ticket 23 is unblocked in the map but requires separately authorized paid measurements under the updated auth/budget contract. Neither is an unblocked planning decision. All remaining specification tasks have unresolved declared prerequisites, directly or transitively through Eyes/Report; preparing assumptions does not satisfy those prerequisites.

## Concrete next step

Update ticket 19's existing protocol to the later accepted time, credential, billing and evidence contracts, then seek an explicit transition from planning to a bounded local Stage A prototype: pinned real mcp-grafana stdio client, disposable local TLS/Forwarder subset and deterministic synthetic backend fixtures, positive and negative auth/scope/output cases, sanitized receipts. No model, cloud venue, real tenant credential or external service mutation is needed for this subset. It is source/protocol preparation only until authorized. It can expose a decisive incompatibility but cannot alone resolve the ticket's model-usability/latency questions or unblock Eyes.

Full Stage B remains separately gated by model/CLI verification, mediated Anthropic credentials, approved spend and private evidence capture. The draft protocol remains NOT RUN. No automatic task, prototype implementation or execution was started by this frontier audit.

## Subsequent authorized local measurement

The user authorized local Stage A after this preparation snapshot. [The verdict](ticket-19/stage-a-verdict.md) now records 31 supported fixture assertions at prototype commit `5f90bfb`; model/container/tenant/venue gates remain NOT RUN. Ticket19 remains claimed and all blocker edges above are unchanged.
