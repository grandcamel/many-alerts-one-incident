# Installed client evidence register

2026-09-22. **SELF-DOCUMENTATION ONLY / NO INFERENCE OR AUTH CHANGE.**
Baseline `b0e1f8b`. [Machine-readable register](client-evidence-register.json)
contains command identities, executable/output digests and exact help excerpts with
line locations. A temporary empty HOME/work directory and minimal environment were
used for `claude --version`, `claude --help`, `headless --help` and a
`headless --print-command --json` preview with fixed inert text. All exited zero
with empty stderr. No prompt was submitted to a model; no model request, auth command or configuration dump ran.

The selected local Claude executable resolves to version **2.1.278**, 226,521,952
bytes, SHA-256 `c522425e3d42275d2ac2238757ef8ba7f80d165a934044ec5a7a5fd7d7b9950b`.
The wrapper entry script is separately hashed; that hash does not freeze all its
Node dependencies. The separately retained dry command preview records one generated
command shape, not an executed or qualified native command. The native executable
and wrapper remain distinct evidence sources.

Private command outputs and manifest:
`/Users/jasonkrueger/maoi-ticket23-evidence/20260922-stream-evidence/client-register/`.

## Documented switches and their limits

| Concern | Captured help supports | Still unknown or untested |
| --- | --- | --- |
| Input/output | Print mode supports text/stream-json input and text/json/stream-json output; optional partial/hook events and replayed user messages have their own switches. | Exact event field schema, ordering, mandatory flags and actual emitted bytes. |
| Tools | Built-in tool selection, allowed tools, MCP configuration and strict MCP configuration are documented. | Actual registered tool schemas, dispatch/result pairing and effective permissions. |
| Permission handling | Mode and print-mode permission responder selection are documented; responder `none` automatically denies what would prompt while mode still governs other decisions. | No-dispatch proof, denial event schemas and actual scope enforcement. |
| Model/fallback | Exact model name selection and opt-in automatic fallback are documented. | Availability, provider identity, configuration-driven fallback or actual transitions. No fallback is enabled here. |
| Budget | `--max-budget-usd` is documented for API calls in print mode. | Enforcement, overshoot/in-flight exposure and provider actuals. Help is not a hard billing guarantee. |
| Configuration | Setting-source selection, explicit settings, restricted mode and safe mode are documented. Managed settings still apply in the documented isolation modes. | Effective settings/policy in a future real launch; endpoint/CA trust and credential custody. |
| Session persistence | Print-mode no-session-persistence and session-ID selection are documented. | Complete artifact suppression or privacy; this does not prove no logs or other writes. |

No runnable experiment card is assembled from these switches. In particular, documented
restricted/safe modes do not establish the project's OS boundary or compatibility
with its required tools. No bypass-permission mode is selected. Help output does
not expose a qualified native event schema, fixed Forwarder endpoint/CA wiring,
or billing evidence; those register entries remain UNKNOWN.

`headless --json` is documented as raw agent trace output, whereas `--usage`
appends normalized token and API-equivalent cost JSON. Wrapper-added data must
therefore remain distinguishable from native output and provider billing. The
prior wrapper inventory is not a substitute for that separation.

The dry preview for read-only/high/Fable generates print-mode stream-json plus
verbose/effort flags and a Read/Grep/Glob/LS/WebFetch/WebSearch allowed-tool list.
It does not select the experiment's fixed binding, TLS route, strict MCP configuration
or budget guard. This preview is a wrapper mapping only; neither its provider/model
labels nor the allowed-tool list prove actual identity or effective confinement.

## Next contract evidence

For every future qualified event family, record: exact executable/version and
stream mode, source document or redacted fixture digest, field path/type/required
status, stream/session/request identity, ordering and terminal semantics, accepted
bounds, and the independent process observations used in classification. Missing
entries remain UNKNOWN. A generated event tests a proposed parser, not the native
client. No parser event family is newly qualified by this register.

The next implementation may reuse [fixed stream evidence](stream-plan.md) for
local descriptor attribution, then needs reviewed exact-client schema sources and
redacted fixtures before normalization. Preserve [native readiness](native-adapter-readiness.md),
the [Forwarder contract](../ticket-36/contract-draft.md), private audit requirements,
and accounting checks. [Standing cost approval](experiment-authorization.json)
removes repeated cost-permission questions within its aggregate cap; this register
does not establish technical readiness or spend a reservation.
