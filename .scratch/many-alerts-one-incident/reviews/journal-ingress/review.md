# Unit 16 raw Notification ingress sanitizer: independent review

## Design and review history

This unit is item 1 of the recovery-journal plan's Deferred list. Receiver
integration is left to a later unit, which must ship with operator resume.
Because the unit is small, it used a lighter panel: two Opus designs, one Opus
judge-synthesizer and one Opus critic.
- **Strict mapping (40/60):** an exact allowlist projection that refuses anything ambiguous.
- **Robust ingress (38/60):** refuses only what Grafana could never send, minimizing refusals of legitimate Notifications.

Both admitted all 115 ticket-14 captures and the three fixtures. The strict design
won; the robust design's stance was grafted on.

**Parser strategy.** The house parser's 16 KiB string cap applies to Grafana's templated `message`. That field passes 16 KiB at 20 alerts, so the committed parser alone would refuse any group above 19 alerts. The plan adds a strictly additive `max_string_bytes` keyword to `forwarder_json.parse_json`. The default is unchanged, and only the sanitizer raises the cap, to the 256 KiB body bound. The ceiling then becomes the journal's own record limits: 28 two-value alerts, 21 three-value alerts or 32 value-free alerts.

**Critic.** It raised 14 issues, 1 of them high, and all were accepted in
[revision 2](implementation-plan.md):
- Every 400-class check now runs over every member before any 422-class check, and every member-level 422 names its members.
- Resolved members are listed first, and the stored summary has no HTTP status.
- `refused_group` stays stable across Grafana's resends.
- `json_unicode` is classed 422.
- `refusal_to_json` checks consistency, and `oversize_refusal(declared_length)` refuses without parsing.

| Step | Result |
| --- | --- |
| Implementer I | `journal_ingress.py` (494 lines), the additive `forwarder_json` keyword, 163 unit and string-cap tests; full suite 4396 passed, 38 skipped |
| Tester T | 221 corpus and adversarial tests; all 115 captures, goldens re-derived two ways; no source bugs |
| Contract and custody lens | 29,000 fuzzed inputs against an oracle, with 0 mismatches and 0 exceptions; one low finding |
| Test-adequacy lens | 28 of 46 mutants killed; seven test gaps |
| Root | tightened `refusal_to_json` to the plan's code table; wrote the documentation |
| Gap agent | closed the seven gaps; 19 mutants killed |

**Contract finding (low).** `refusal_to_json` accepted internally impossible hand-built summaries: a `ref_id_unsupported` or `record_too_large` carrying only `refused_group`, `too_many_alerts` with one alert, or `too_many_values` with 40 alerts. Root now requires `source_group` for every member code except `group_key_unsupported`, and for a member-carrying divergence. It also requires more than 32 alerts for `too_many_alerts`, and at most 32 for the codes checked after it. The sanitizer's step order already guarantees all of this, and the totality fuzz confirms that every genuine refusal still validates.

**Test gaps closed:**
- the shape and type branches (`alerts` absent, empty, an object or holding non-objects; a non-string `groupKey`; non-object `values`), each returning its exact code without raising;
- the exact-type rules for values, `truncatedAlerts` and status;
- `resolved` counted over omitted members;
- nine forged summaries, including the root tightening;
- duplicate-Fingerprint precedence over the non-ASCII `groupKey` and too-many-alerts checks;
- `endsAt` never leaking into `starts_at`;
- a closed-set check built from the codes the tests actually produce.

## Final hash-bound source and test review

Reviewer: fresh independent agent, read-only. It verified these SHA-256 values
at HEAD `1a62de7`; the final hashes are listed after the addendum.

```
0a1ee4e248ef5cbfbc15917b14fe80dff560c488861817db30d906362dc2d80a  grafana_jsm_sandbox/journal_ingress.py
50222c40c811c0bd98dfa607dec932f50d5b7ad4b32fccc5b27ee85f7cfbd0df  grafana_jsm_sandbox/forwarder_json.py
c29935840d5f6bf6756a2634d89aeb4c08d6b2f148b934b52701732ba19a6e6d  tests/test_journal_ingress.py
63a3b82bfebc1698170107378d696001ad6ad67fb26e3afeea1e2ac835c94790  tests/test_journal_ingress_corpus.py
b9e64d2554988f07bd2ba2fe6fc214f8c6bfd8a09cf43aeb14c4a8ab667ff4f1  tests/test_journal_ingress_adversarial.py
c37e54848c91d81a6f253ef2d2cfe4dbbf8b649875c8bbdc72fc50e8d31ae453  tests/test_forwarder_json_string_cap.py
84193b80348bc054bd6afc1237aa67fb7e538280805356e112e786feb36ee85e  docs/recovery-journal.md
e5dd52606fcbdbbf510c9d4d70e4fedb8433131cb6987586d44131fbd17ffd22  docs/forwarder-control.md
5268e2e2e6dfc41072abeb4bdce92b9228c303d9ad31fab9fc3d3aef240cb481  .scratch/many-alerts-one-incident/reviews/journal-ingress/implementation-plan.md
```

Verdict: **PASS (source and test review)**. No source bug.

- **`forwarder_json` is strictly additive.** `canonical_json` and `tagged_digest` still call the string check without the keyword, so they stay at 16 KiB. The keyword is validated as an exact int in 1..1 MiB before decoding. Only `journal_ingress` passes it; the five existing calls are unchanged.
- **Mapping and totality.** The reviewer built its own oracle from plain `json` and `hashlib`. It compared codes, groups, members, counts, `starts_at_dropped` and full records on 26,000 structured inputs, with 0 mismatches; every code was produced except the five reachable only by monkeypatch. A further 20,000 byte mutations raised no exception. Every admitted record passed `validate_source`, and every refusal passed `refusal_to_json`.
- **Refusals.** The phase order, closed codes, Resolved-first members, stable `refused_group`, the root tightening, the 4 KiB bound, `oversize_refusal` and the exception table all match the plan.
- **Custody.** Every `except` body only assigns, errors carry fixed codes with no chained context, and no ignored-field content appears anywhere.
- **Mutation probes.** Of 25, 11 were killed and 13 survived; the survivors exposed test gaps T1-T6. One more survivor (M24, a cap that cannot go below 16 KiB) is harmless, because no caller lowers the cap.
- **Size.** Accept 507 lines rather than split: 446 non-blank lines, and an overage of 7. A split would share five symbols across modules and force a re-review; the better seam is Deferred 3.
- **Runs.** Two runs of 572 tests passed in about 3.7 s. The root gates were focused 1553 passed and full 4425 passed, 38 skipped.

**Applied before the addendum:**
- **Source (root):**
  - S1: `_members_ok` requires an exact empty tuple for member-less refusals. Before, a tuple subclass with a permissive `__eq__` could smuggle arbitrary ASCII into a hand-built summary.
  - S2: the module docstring no longer claims that a non-Grafana body is always 400.
- **Docs (root):**
  - D1: the documentation, the docstring and the plan's root note now say that parser-level `ingress_json_unsupported` (422) is decided before phase 1, and so can land on bodies that are not Grafana's.
  - D2: `forwarder_control.md` no longer says finite mode is used only for upstream responses.
  - The ignored-field sentence now says the content never appears in a refusal, not that it cannot cause one.
- **Tests (gap agent):**
  - T1: phase-1 refusals under an unsupported group key.
  - T2: `refusal_to_json` on group-less shape and on divergence refusals.
  - T3: null values counting toward the 64-value bound.
  - T4: exactly 32 members.
  - T5: the refused-group tag and `GO_ZERO_TIME` literals.
  - T6: forged-summary boundaries and fingerprint-before-status.
  - S1: the permissive-equality forgery.

## Addendum re-verification

The same reviewer re-checked the post-review tree:
- **Source diff:** exactly the S1 check and the docstring rewrite. `forwarder_json.py` is unchanged.
- **Re-fuzz:** 0 oracle mismatches on 11,000 structured bodies, and 0 exceptions on 5,000 byte mutations.
- **Docs:** D1 and D2 and the ignored-field sentence are accurate.
- **Mutants:** of the earlier survivors, M03, M05, M07, M10-M12, M14 and M15, plus the S1 revert, are now killed.
- **Runs:** its step-5 command passed 590 tests twice.

Addendum verdict: **PASS**.

Root applied its two nits:
- The documentation now attributes only the NUL, large integers and long arrays to Go. It says the same code also covers the lone surrogate and over-long numbers, which Go cannot emit, and refers to "any array" rather than "alerts".
- The plan note now says 509 lines.

Final hashes of the source and tests:

```
83bbc676577a9894dd1ac8c4cf3f3065be5395acdb16fcdcb6e8606a529ab802  grafana_jsm_sandbox/journal_ingress.py
50222c40c811c0bd98dfa607dec932f50d5b7ad4b32fccc5b27ee85f7cfbd0df  grafana_jsm_sandbox/forwarder_json.py
4c20c6e66029dfba75207db1573578dd5f9b27bb0e39fafaaf0e0e12c7457c2c  tests/test_journal_ingress.py
63a3b82bfebc1698170107378d696001ad6ad67fb26e3afeea1e2ac835c94790  tests/test_journal_ingress_corpus.py
b9e64d2554988f07bd2ba2fe6fc214f8c6bfd8a09cf43aeb14c4a8ab667ff4f1  tests/test_journal_ingress_adversarial.py
c37e54848c91d81a6f253ef2d2cfe4dbbf8b649875c8bbdc72fc50e8d31ae453  tests/test_forwarder_json_string_cap.py
```

## Residual limitations (accepted)

- **Five surviving mutants (M06, M08, M09, M19, M20).** These cover forged-summary rejections: `too_many_alerts` at exactly 32 alerts; a member-carrying divergence above 32 alerts or with only `refused_group`; uppercase hex digests. They also cover `refusal_to_json` on the monkeypatch-only member-carrying divergence rows. All involve hand-built summaries or monkeypatch-only paths, and the oracle fuzz confirms the code handles them. The reviewer called them optional follow-ups.
- **Non-Grafana bodies.** Parser-level 422s can land on bodies that are not Grafana's; this is the plan's documented conservative choice.
- **Unverified Grafana behaviour.** Grafana's wire bytes and its retry and resend behaviour are unprobed, and the digests are unkeyed.
- **Size.** 509 lines against a 500-line split trigger. The split is deferred to the refusal-persistence unit.
