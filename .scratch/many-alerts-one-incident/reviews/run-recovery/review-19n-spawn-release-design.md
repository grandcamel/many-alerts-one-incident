# 19n spawn/release design review

Date: 2026-09-25. Fixed source point: `9b57f0e`.
Subject: [design-19n-spawn-release-evidence.md](design-19n-spawn-release-evidence.md).

Independent Standards and Spec reviewers both report **PASS** on the
revised document. Their initial findings required:

- a durable, recoverable witness locator and a pre-created protected anchor
  findable by exact launch-claim/Run/attempt identity after a crash before
  attestation;
- a fresh qualification of the new journal head and independent ledger
  relation after `release_intent`, plus current reference manifest/version
  and immediate revocation checks before release;
- a distinction between an outstanding normal Run slot and a global
  dispatch hold latched by restart or uncertainty.

The revised design addresses each finding. It remains a **proposed contract**:
no journal record type, anchor registry, child launcher, Forwarder grant
activation, durable supervision writer, permit or external effect is added.
The stable witness and inherited barrier need intended-venue proof; provider,
tenant, native, paid, deployment and human acceptance are **NOT RUN**.
