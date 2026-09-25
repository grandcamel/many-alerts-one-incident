# Unit 18c design and plan review

Status: **ACCEPT_LOCAL_18C_STORAGE_PLAN**, 2026-09-24. This accepts the
non-reserving store design and implementation plan for local source work only.
It does not accept a production reservation format, external opening-history
verifier, 18d bridge, Run dispatch, billing import, archive or launch.

Fixed point: `221dab94c8828b101bb1f3a35bbe131e0b1d23bd`. The proposed
design and plan were first committed locally at `b19954f`; the final anchor
reconciliation follows in the next local documentation commit. The two-axis
independent review inspected `git diff <fixed-point>...HEAD` at that point,
the handoff, selected design, ticket-38 proposal, ADR 0013 and relevant source.

## Standards

The independent Standards reviewer found no documented-rule breach and no
supported Fowler-smell finding in the two new Markdown files. It read the
user-provided AGENTS.md instructions, `CLAUDE.md`, domain/issue-tracker
guidance and relevant ADRs. It made no edits and ran no tests.

## Spec

The independent Spec reviewer found one blocker to calling the plan exact:
the first draft left anchor length encoding, checksum representation and
hashed byte range open. The handoff explicitly requires the physical
schema/version/anchor and custody to be settled. The revised
`design-18c.md` fixes 8-byte magic, unsigned big-endian 4-byte length,
1..960-byte canonical payload, 32 raw tagged-SHA-256 bytes and their exact
input, padding, offsets, slot parity and counter rules. The revised
`implementation-plan-18c.md` mirrors those bytes. The reviewer re-read the
revised paragraphs and found the blocker resolved, with no contradiction
between interrupted-slot classification and held one-event-tail adoption.
It found no other 18c-storage plan blocker. Production reservation remains
explicitly deferred by the design and plan.

## Final read-back and limits

| File | SHA-256 |
| --- | --- |
| `design-18c.md` | `594a706e54d92ac149aab044cc90cfe2f2bf3d00015ef51c9119032c1a204e7e` |
| `implementation-plan-18c.md` | `5ae1fe9b7ef6c675aafad50f59fe811f21a1107e90ecde7cac67970517d4f66e` |

`git diff --check` and exact-file whitespace checks pass. The four protected
pre-existing ticket-19/planning file hashes match `validation-18b.json`.
No 18c source or tests changed; the full suite and focused tests are **NOT RUN**
for this documentation-only checkpoint. Local SQLite/crash/power-loss,
provider, native, tenant, venue, paid, deployment, archive, journal bridge,
model dispatch and human adjudication are **NOT RUN**. The separate headless
Claude review timed out without a verdict; Gemini CLI rejected authentication,
and the bounded Antigravity review timed out without a verdict. None is counted
as review acceptance. Only the completed independent two-axis review above
supports this plan verdict. No push/publication or ticket-19 C2 retry occurred.
