# Ticket 24 facts (offline, 2026-09-18)

`d9b3e6f` is the later planning commit; it does **not** contain the prototype paths. The cited
prototype snapshot is `79a14c8` (`prototype/run-timing`).

- **Keyword checks: verified, but explicitly a pre-check rather than a grade.** `score.py` says it
  extracts facts for a human grader (`79a14c8:prototype/run-timing/score.py:1-10`) and applies regexes
  to final text, Issue Description text, and comments
  (`79a14c8:prototype/run-timing/score.py:29-43,58-94`). It checks flag/flip time,
  trace prefixes, `cache_hit`, Change ID, confidence, blast radius, deploy mention/rule-out and host
  CPU wording. It does not judge the Ground-truth mechanism paragraph or a root-cause attribution.

- **Mention-versus-attribution false positive: verified and corrected in the script.** The checks
  retain separate payment-deploy mention and rule-out patterns
  (`79a14c8:prototype/run-timing/score.py:38-46`); the comment says an earlier pass wrongly failed the medium arm, which explicitly ruled the
  deploy out. Ground truth defines that deploy as a red herring and says citing it as cause fails
  (`79a14c8:prototype/run-timing/fixtures/ground-truth.md:31-38`). The measurement records both Opus
  arms ruling it out in words (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:39-45`).

- **Invented controls: the mechanical scorer misses them.** It neither reads tool-use events nor
  compares Report claims with retrievals; it only parses result text and `hands-state.json`
  (`79a14c8:prototype/run-timing/score.py:63-99`). The published measurement says Haiku made four
  Eyes calls, none for payment/ad, but claimed both healthy; it calls that fabricated control
  disqualifying (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:39-47`). This is a
  historical audit finding, not a machine-produced scorer verdict.

- **Arithmetic slip: verified.** The ground truth fixes the payment deployment at 13:10 and flip at
  14:02, a 52-minute interval (`79a14c8:prototype/run-timing/fixtures/ground-truth.md:35-38`); the
  measurement records `opus5-high` saying 54 minutes and `opus5-medium` getting it right
  (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:53-55`). No scorer check evaluates it.

- **Evidence boundary.** Raw per-arm Transcripts are git-ignored because they contain local paths
  (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:3-5`), so this committed snapshot
  supplies reported call counts and Report state, not preserved fetched response bodies for a new
  citation audit. Current telemetry policy similarly excludes raw Transcript bodies, commands,
  arguments and tool output from shared ingestion (`main:docs/adr/0010-run-telemetry-is-sanitized-correlated-and-best-effort.md:8-9,18-19`); its sanitized projection cannot substitute for complete response evidence.

- **Historical pass marks are not current qualification.** The measurement explicitly grades naming the flag as the cause (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:28-35`); ADR 0008:5,18 now scores the Mechanism instead. Preserve those historical grades as historical, not current model qualification.
