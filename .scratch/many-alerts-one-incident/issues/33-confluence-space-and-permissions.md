# Confluence space and permissions

Type: grilling
Status: resolved
Blocked by: 13, 17

## Question

Settle the dedicated Confluence namespace and account permission boundary, seed ownership/source-version selection, and how approved reference material is distinguished from Run-authored drafts and retained prior-rehearsal artifacts. Preserve ADR 0009's approved seed classes, draft review gate and fresh-rehearsal isolation. Verify the installed CLI/client and available tenant facts before asserting enforcement; ticket 06's historical no-space-guard finding is not current tenant proof.

Produce the space/permission plan and acceptance requirements, including native draft creation/read-back and versioned updates. Ticket 17 owns credential forwarding and HTTPS. Do not provision a space or change grants during planning.

## Work in progress

Claimed after ticket 30 was committed. Planning and offline CLI/source inspection only. No tenant writes, space provisioning, grant changes, credentials or model/cluster runs. Verify actual capabilities rather than treating historical no-space-guard notes or skill examples as current enforcement proof.

[Offline CLI facts](../reviews/ticket-33/facts.md) verify installed confluence-as 1.1.1, native draft status options, ID-based page access and read-before-write version increment. This installed build has no api discovery command. Caller-supplied expected-version control, native draft read-back, effective tenant grants and registered-scope enforcement remain unverified. [Round 1](../reviews/ticket-33/round-1.md) records accepted namespace, principals, approval manifest and seed version policy. All four recommendations were accepted. [Round 2](../reviews/ticket-33/round-2.md) records accepted identity, conflicts, reference reads, revocation and acceptance details. All five second-round recommendations were accepted.

## Answer

Both rounds are accepted in [ADR 0017](../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md). Two proposed private spaces separate approved references (MAOIREF) from Run drafts (MAOIDRAFT); key availability and effective tenant permissions remain unverified. A dedicated non-admin automation principal uses scoped Forwarder access, while a separate human curator controls publication and grants.

An operator-owned exact-page/version/digest approval manifest gates reference reads; a durable Incident-to-draft mapping and enforced expected-version updates protect draft identity. The installed CLI's native draft options are verified, but its current-version increment is not sufficient stale-body protection. Uncertain creates/conflicts hold the affected Memory step. Revocation cancels exposed active Runs through existing bounded recovery and requires operator review; it never rolls back OPS effects. Human-visible provenance persists without automatic reuse or deletion.

[Ticket 43](43-confluence-scope-approval-and-draft-integration.md) specifies manifests, native operations, permissions, version binding and offline/separately authorized tenant acceptance. No live tenant verification, space/page/grant/credential changes or runtime implementation occurred.
