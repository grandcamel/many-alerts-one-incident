# Ticket 23 — timing instruction and rubric drafts

2026-09-21. **REVIEWED SOURCE DRAFTS / NOT DEPLOYED / NATIVE LAUNCH CLOSED.**
Baseline: local commit `9ab04ab`.

The [draft packet](timing-draft/README.md) contains a proposed system prompt, task prompt
and diagnostic Skill, separated from operator-only rubric, preflight and unfilled compact
adjudication template. No runtime code changed and no Skill was installed.

The Run text requires evidence-based grouping rather than assuming all Alerts share a
Fault. It records returned-response support, scoped inference, unknown controls, arithmetic
inputs and proposed-versus-confirmed effects. It preserves earlier Report revisions and
stops uncertain mutations or provider refusal instead of silently retrying. No native CLI
syntax, permission configuration, current pricing or tool compatibility is asserted.

The operator rubric applies Mechanism-only human grading with separate evidence/arithmetic
axes and independent execution/effect/identity/timing/spend references. It excludes the old
flag-name pass rule, preserves earlier Report defects and separates reviewer correction from
Report correction. The proposed synthetic Mechanism baseline is explicitly unapproved;
a named human must approve fixture correspondence and freeze the rubric before use.

## Verification and review

- Re-read and verified all **22 historical source digests** against the pinned commit.
- Parsed the seven-Alert Notification, four canned telemetry sources and template JSON;
  verified seven unique Alert fingerprints without executing the historical generator/stubs.
- Verified Skill frontmatter and explicit manual-only invocation intent. The Skill remains
  an uninstalled draft; its deployment and actual invocation behavior are NOT RUN.
- Draft manifest indexes **3 proposed Run text files and 4 operator-only files**, plus
  historical input roles. Verified current bytes/digests and JSON read-back.
- A limited literal answer-marker scan passed for Run text. This is supplementary static
  evidence, not proof of no leakage, secure assembly or runtime isolation.
- Full suite: **486 passed, 36 skipped in 28.71s**. `git diff --check`: PASS.
- Independent Standards and Spec reviews: **zero actionable findings each**. Both read
  all eight draft files; Spec checked accepted ADRs and the historical Ground truth.

The parent performed mechanical validation. Reviewers assessed source only. No prompt was
executed against a model, no human grade was awarded, and no fresh Fable/external-model
review or behavioral acceptance is claimed for this documentation batch.

[Validation receipt](timing-text-validation.json) and [draft manifest](timing-draft/draft-manifest.json)
identify the exact inputs. The previous 42-file packet was read from `9ab04ab`, hash-checked
and archived under `/Users/jasonkrueger/maoi-ticket23-evidence/20260921-timing-texts/prior-phase-snapshot/`.

## What remains

The file-delivery allowlist is a proposal; mounting its parent directory would expose
operator material. A reviewed assembler, fixed synthetic adapter/capability schemas,
verified empty Incident store, retained mutation receipts and actual access controls remain
unimplemented. Human Mechanism/rubric freeze, native client/Forwarder compatibility,
authoritative accounting, private audit readiness and full durable-closeout timing remain
gates before a separately authorized one-attempt card can open.

This does not complete ticket 39's audit/scoring specification, ticket 38's qualification
contract or ticket 23's measurements. C2 remains unchanged. No credentials, provisioning,
Jira operation, paid probe, push or publication occurred.
