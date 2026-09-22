# Proposed local runtime source implementation

2026-09-22. **Scope proposal only; implementation not started.**

The native-launch evidence contract now identifies the missing runtime boundaries.
More synthetic stream examples cannot establish them. The next substantive source
work is to implement the accepted Forwarder, recovery and accounting contracts in
the application, with local tests and independent review before any deployment.

## Why a scope decision is needed

[Ticket 36](../issues/36-forwarder-integration-and-acceptance.md) says “No live
credential, cluster, demo or runtime implementation is authorized by this planning
ticket.” [Ticket 37](../issues/37-run-recovery-and-admission-specification.md)
similarly requests a specification, “not runtime code.” The standing continuation
instruction requires respecting each ticket's planning-only versus implementation
scope. Finishing their documents does not change that scope.

The proposed decision authorizes **local application source implementation and
local tests** of the existing contracts. It does not resolve their remaining native
or deployment acceptance, change an ADR, or make a planning ticket a runtime pass.
Track implementation separately from specification completion and acceptance.

## Concrete implementation sequence

1. Add explicit service/route profiles, scoped lease generations, registration,
   expiry/revocation and request-aware policy modules alongside
   `grafana_jsm_sandbox/forwarder.py`. Enforce mandatory Jira, Grafana/Eyes,
   Kubernetes and Anthropic readiness; optional Confluence failure degrades
   Memory. Use fixed loopback TLS servers and synthetic credentials in tests.
   No test may select a real upstream service.
2. Add Receiver-owned durable admission, recovery and accounting modules, then
   integrate their state transitions with `receiver.py` and `run_spawner.py`.
   Cover atomic reservation/claim, failure windows, retained uncertain effects,
   dedupe/pending work, restart holds and one-time charge attribution. Unknown
   historical accounting must still prevent paid admission.
3. Replace assumptions in the native launch preparation path with explicit
   profile/readiness checks: upstream credentials never enter a Run; scoped
   mediation is mandatory; missing OS isolation or current evidence fails closed.
   No test or local acceptance run starts the installed native client. Existing
   legacy HTTP/OAuth behavior is not accepted evidence for the new contract.
4. Validate each bounded change with relevant offline/interface tests and the full
   repository suite. Use cheaper implementation/test workers and independent
   review; root checks cross-module authority, recovery and evidence boundaries.
   Commit locally only reviewed, passing units.

The initial file-level plan for each unit must precede edits. The existing
[Forwarder](ticket-36/forwarder-specification.md),
[recovery](ticket-37/recovery-specification.md), and
[accounting](ticket-38/accounting-specification.md) specifications define the
contract; unresolved interfaces remain explicit and cannot be filled by assuming
that a native client, tenant or kernel will behave as a fixture does.

## Boundaries retained

- No provider request, native model client execution, paid experiment, real tenant
  mutation, credential read/change, new account, provisioning or deployment.
- No provider-blocked C2 retry, modification or dependency substitution. Preserve
  its unrelated dirty files and the planning-frontier edits.
- No push/publication under this proposal. The prior explicit push ended at
  `ee2d838`; continuing work remains local.
- No automatic Report adjudication or model qualification. Preserve the approved
  pinned rubric and all real billing, human, native-isolation and venue gates.

This decision would remove the source-implementation scope gate. It would not
remove the separate technical or external gates on executing the resulting code.
