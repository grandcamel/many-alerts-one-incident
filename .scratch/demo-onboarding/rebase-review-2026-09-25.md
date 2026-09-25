# Rebase review and implementation decision

## Plan followed

1. Rebase in the isolated clean worktree and keep the retired launcher guard through conflicts.
2. Compare the old onboarding surface against accepted ADRs and the current local closeout.
3. Return incompatible live runtime and tests to `main`'s guarded state; retain dated historical evidence.
4. Write the future many-alert storyboard, opportunity map and planning-only newcomer skill.
5. Check links and the final diff, run the full offline suite, then commit locally without pushing.

Date: 2026-09-25. The fixed merge base was `6a3ecc28250cb82032f95333050824b80a4fed3f`; `demo-onboarding` had 16 commits and local `main` had 67 subsequent commits at `796455a97fb83e80863a1d262657fb5c3def573a`. The 16 commits were rebased in the isolated `/Users/jasonkrueger/projects/maoi-demo-onboarding` worktree. The dirty main worktree was not edited.

The conflict resolutions kept `main`'s `grafana_jsm_sandbox.__main__` launch refusal and its matching startup tests. Other conflicts in README, container/e2e tests and the runbook initially kept the current side; the complete conflict path record is `/tmp/maoi-demo-rebase-conflicts.log` on this host. A focused offline run of the mechanically rebased branch reached **422 passed, 31 skipped, 60 failed**. Failures were mostly the old `doctor` assuming superseded launcher settings and an old chapter-one test classification. This was evidence of incompatible architecture, not a passing checkpoint.

The owner chose **future live demo design only** and removal of the historical Opus 5 lifecycle from the newcomer flow. The old branch's `doctor`, `verify`, `reset`, direct-token Runtime changes, fixtures and old tests were therefore returned to `main`'s current final state or removed as branch-only additions. The original commits and dated evidence remain in Git history and under this scratch directory; the final diff carries design documents and a planning-only setup skill. No current live command path is restored.

The original branch delivered a useful dedicated-site configuration concept, project discovery, admin-request wording, a rendered Skill idea, a non-dumpable process probe, and a verified one Alert historical run. Those are future design inputs, not current Run/effect acceptance. ADRs 0006–0018 and the local goal closeout now require many-to-one Match, durable recovery, reserved metered spend, scoped Forwarder routes, trusted citation audit, venue protection and human review. See `docs/demo-opportunities.md` for the scene-level mapping.

Final verification: `python3 -m pytest -q -p no:cacheprovider` in the isolated worktree passed **5,805 tests, 39 skipped in 458.76 seconds**. The complete local output is `/tmp/maoi-demo-full-suite-2026-09-25.txt`, SHA-256 `77ffd60127a97a5e62e59c5a4437105cd92d7023037a281073c79599cca4cc63`. A four-document relative-link/anchor check found zero errors, and `git diff --cached --check` passed. The final diff against `main` contains no runtime, Compose, test, or credential-setting changes. No push, provider experiment, tenant mutation, cloud action or human adjudication is part of this rebase.
