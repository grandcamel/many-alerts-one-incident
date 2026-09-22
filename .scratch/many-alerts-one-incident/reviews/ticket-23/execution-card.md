# Ticket 23 — technical preflight measurement card

Prepared 2026-09-21. **COST AUTHORIZED UNDER AGGREGATE CAP / TECHNICAL PREFLIGHT NOT READY.**
The user approved cost-bearing experiments with a cumulative total strictly below $50;
[standing authorization](experiment-authorization.json) records the exact instruction.
No repeat cost approval is needed within that scope. This draft still has unset technical
fields, creates no reservation and supplies no launch command.

| Field | Required value or current state |
| --- | --- |
| Purpose | New synthetic timing diagnostic or fixed command-length diagnostic; select exactly one per authorized card. |
| Attempt ID / operator / execution date | UNSET — must be unique and recorded before admission under standing authorization. |
| Timing model / effort | Requested historical `claude-fable-5-1` / explicit `high`; availability and actual model NOT VERIFIED. |
| Length model / effort | Historical Haiku 4.5 family; exact identifier and supported explicit effort UNSET. |
| Fallback | No automatic substitution; detected native fallback/refusal stops and holds the experiment. |
| CLI / effective policy | Version 2.1.278 executable/help and wrapper command preview captured 2026-09-22; see client-evidence-register.md. A pinned official-source offline normalizer is recorded in documented-stream-outcome.md. Effective runtime policy/tools and installed-client stream compatibility remain unverified; recheck exact artifacts before execution. |
| Historical input | `79a14c8904f3a125d1f03b192d10797d30979c86`; digests in source-manifest.json. |
| Executable revision / prompt / Skill / adapter / rubric | Offline core and pinned in-process queries have no native launcher. Reviewed prompt/Skill/rubric source drafts exist in timing-draft/; human rubric/baseline approved with exact hashes in timing-draft/operator/rubric-approval.json; a local synthetic binding and integrated fixed-client rehearsal now exist; native transport/authenticated Incident adapter and full native executable manifest remain UNSET. Historical runner/Skill are not approved. |
| Run access | Sealed read-only fixture bundle; synthetic stubs only; no Ground truth, rubric, audit store or host credentials. |
| Auth | Dedicated metered API via fixed Forwarder and per-Run sentinel; upstream key outside Run. Current readiness NOT VERIFIED. |
| Time | 270s startup/work + up to 20s interrupt/local flush + up to 10s kill/reap; total at most 300s monotonic. |
| Admission | Persistent synthetic fixture reservation, receipts and concurrent admission tested; see ledger-outcome.md. Current provider/weekly ledger read-back, actuals/lag/exposure reconciliation and applicable ceilings still required. Real accounting NOT VERIFIED. |
| Reservation | $3 before this attempt, one diagnostic attempt; no reservation made by this card. Guard is not a hard billing cap. |
| Evidence root / capacity / retention | UNSET production private operator-owned path outside Git and Run mounts; 100 MiB/Run, 2 GiB total, 30 days. Fixed fixtures now retain at most 1 MiB capture with digest read-back; this does not implement production quota, sanitization or retention. |
| Containment / receipt / terminal / identity acceptance | Offline predicates plus real fixed-host-fixture group/pipe cleanup and collision tests passed. Version-2 closeout adds bounded independent stdout/stderr integrity; this is descriptor attribution only. A separate two-hop Python TLS fixture now tests local transport, synthetic lease revocation and held failures; see mediated-client-outcome.md. Adversarial confinement, authenticated native transport and native event compatibility NOT RUN. See process-outcome.md. |
| Current status | Offline core, fixed-process harness, synthetic diagnostic ledger, fixture byte-integrity closeout and inert length-case records, pinned queries, synthetic Incident revisions/effects, bounded retained snapshots, local capability binding and integrated child-process rehearsal implemented/tested. See integration-outcome.md. Native model executor, authoritative auth/billing/tenant/venue acceptance NOT RUN; standing cost approval is GRANTED; native execution remains technically CLOSED. |

## Required evidence before this card can open

- Reviewed implementation and frozen full input/executable manifest; offline acceptance
  results covering all cases in the redesign and outcome fixture, including hold behavior.
- Current routing, TLS, streaming, revocation and direct-route prevention evidence for
  the exact native client; no transfer of older compatibility approval or runtime root.
- Defensible remaining-budget calculation from current ledger and provider evidence;
  preserve unresolved reservations, no assumption of zero usage or a fresh allowance.
- Named operator, exact single attempt/model/effort/fixture/paths, capture capacity,
  cancellation mechanism and dispositions for failure, unknown dispatch and exposure.
- Apply the standing experiment authorization after recording this concrete one-attempt
  card and verifying aggregate actuals plus unresolved/reserved exposure stay strictly
  below $50. Do not ask again for cost approval within this scope. Native readiness and
  any unrelated account/infrastructure changes are not established by that approval.

## Required closeout after any future authorized attempt

Record actual identity/fallback evidence; observed and derived execution outcomes;
per-case dispatch or synthetic Incident effects; monotonic work/cleanup/reap timing;
containment confirmation; session estimates and separately attributed provider actuals
(unknown stays unknown); retained reservation and hold state; capture completeness and
hashes; unattempted cases; named human Report adjudication if applicable. No automatic
next arm or retry. A future results entry starts a new diagnostic series and preserves
historical measurements. Ticket 23 cannot close from this preparation packet alone.
