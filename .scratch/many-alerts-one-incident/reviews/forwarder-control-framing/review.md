# Unit 14 scope delivery and control closeout: independent review

## Design and review history

A read-only design panel produced three competing designs: extend-control,
receiver-side and adapter-layer. Both judge panels picked extend-control. A
synthesizer grafted in the post-install identity check, the after-revoke
consistency hold, the literal spec L122 Revoke keys, the AST ban on registry
calls, the custody scan and reply-key parity tests. A completeness critic raised
13 issues, all resolved in [plan revision 2](implementation-plan.md). The key
resolutions:
- unscoped Register is refused in both modes;
- every control-observed `overdue` holds the registry;
- an uncertain Revoke is `ok:false` after a hold;
- a post-install owner fence prevents a replaced or closed session from writing
  a scoped grant.

Root reconciled the plan against the 13b commit `74b10e8`. The source references
were unchanged. The reconciliation also restored the four-path protected state,
used one plain full-suite run, and split the controller tests across three
disjoint files.

Implementation used individual agents instead of the Workflow tool: Sonnet
implementers and testers with disjoint file ownership, four Opus lens reviewers,
a Sonnet gap agent and root fixes.

| Step | Agent | Result |
| --- | --- | --- |
| Module 1 attachment codec | Sonnet implementer A | additive `send_attachment`/`recv_attachment`; 36 tests |
| Module 2 scope policy | Sonnet implementer B | pure `forwarder_control_scope.py`; B1-B8 tests |
| Module 3 gated controller | Sonnet implementer C | +83/-13 in `forwarder_control.py` (docstrings included); fixtures and cases 1, 4-6, 25, 26 and the lock AST check |
| Closeout cases | Sonnet tester D1 | cases 2, 3, 7-13, 17, 18 |
| Race, custody and integration cases | Sonnet tester D2 | cases 14-16, 19-24, 27, 28; 11 stable runs |

No implementer or tester reported a source defect.

**Round 1 review** (Opus lenses: contract, concurrency and fencing, fail-closed
and custody, test adequacy):
- **Contract and fail-closed** independently reported, and reproduced end to end,
  one low-severity source defect. `observe_closeout` accepted an `int`
  `observed_at` or `drain_deadline` of at least 2**63. For values the codec cannot
  encode, `send_frame` then raised `integer_out_of_range` without a hold. For
  `10**400`, `math.isfinite` raised `OverflowError`, so the session ended as
  `internal_failure` rather than `closeout_inconsistent`. The committed gate
  always returns floats, so only a faulty observation can reach this.
- **Concurrency and fencing** found nothing. Every I6 window fails closed, the
  race barriers hit their claimed windows, and the race cases passed 10 of 10
  repeat runs.
- **Test adequacy** killed all 11 targeted mutants: post-install fence, lock
  placement, hold before re-raise, `ok:true` for `unknown` or `overdue`,
  after-revoke state, gateless unscoped refusal, attachment length match,
  projection fields, identity check, attachment clip and read order. It reported
  six test gaps:
  - `drain_deadline` validation was untested (medium): an `inf` reached the codec
    unheld once `isfinite` was removed;
  - the identity check's clauses were never tested alone;
  - the `TypeError` mapping in `install` was untested;
  - `revoked_at` could come from the gate's clock;
  - the `closeout` command count was untested;
  - case 18 had a latent timing margin of a few milliseconds.

**Root fix.** `observe_closeout` now requires each time value to be a finite
non-negative `float`, or an `int` within the codec's signed 64-bit bound
(`MAX_TIME_INT`). Anything else is `closeout_inconsistent`, which the controller
holds on. Root also removed plan jargon from two comments in
`forwarder_control_scope.py`.

**Test gaps.** One Sonnet gap agent closed all six gaps and proved each new test
against a mutant on a scratch copy. Every kill was an assertion or
`DID NOT RAISE` about the mutated behavior.

| Gap | Tests | Mutants killed |
| --- | --- | --- |
| Timestamp validation | B5 bounds table (`inf`, `nan`, -1, `"x"`, `True`, 2**63, 2**64, 10**400; 2**63-1 accepted); three control-level case-16 variants asserting `closeout_inconsistent` with the registry held when the frame is read | dropped `drain_deadline` clause; the previous `isfinite` rule |
| Identity clauses | B4 over `replace(generation=)`, `replace(scope_digest=)`, `replace(lease_id=)` and a non-`ScopeEntry` copy | each of the four clauses dropped alone |
| `TypeError` from install | B4 `scope_install_failed` with no chain | removed `except TypeError` |
| `revoked_at` source | case-10 variant whose `gate.closeout` advances the clock by 1 s | `revoked_at` from the gate observation |
| Command count | case-13 variant asserting `commands == 5` | counting only registry calls |
| Timing margin | case 18 waits 5 s and asserts `not_owner`; case 28 stops within 5 s | none needed; five runs |

The six focused control files then passed 154 tests in each of three runs.

## Final hash-bound source and test review

Reviewer: fresh independent agent, read-only. It verified ten SHA-256 values at
HEAD `74b10e8`; the final hashes are listed after the addendum.

```
f41752906fb7f4267cedae92cd7c38dde1b2d5ec101075009277fbb7824050ea  grafana_jsm_sandbox/forwarder_control_scope.py
984dd90b8ba73863ab87398548a592689543d61599652ba8fd9770862fd4569e  grafana_jsm_sandbox/forwarder_control.py
6cf62daa5ac723714e565a33b96ecdc66d66a49e7850e9b398d27eca11130470  grafana_jsm_sandbox/forwarder_control_protocol.py
a8857aad44ce570a229e870283d0146743d25c355024e56f4a49e78d7645c9af  tests/test_forwarder_control_attachment.py
396c5fa0153b47ae52f226545d4421d5974671d56291ba944e55739c2eaabc69  tests/test_forwarder_control_scope.py
d51ffa84554caf6b9357296d526c71c7468e560031004ffa3b888256fd5f84b5  tests/test_forwarder_control_gate.py
67be26783d491ecc18b683e1cff9788a90389066d79e3168c5b65d298143149c  tests/test_forwarder_control_gate_closeout.py
be4bc5fc6e714ded460f6236ea7bcf61b7cc0cef25c4897f0cafe830372a57a7  tests/test_forwarder_control_gate_races.py
5c8da20e2afbc50b2b874196101d361a5a2d264487e3b941fb9cace968e51e2d  docs/forwarder-control.md
2a7dcf392ea3678eeeb2da4182bcd283610165d913e2ad692ca5b34088a00857  .scratch/many-alerts-one-incident/reviews/forwarder-control-framing/implementation-plan.md
```

Verdict: **PASS (source and test review)**. No source defects.

- **Attachment codec.** The length argument is checked before any deadline or socket call. One absolute deadline covers header and body. The declared length is checked (zero, over the maximum, mismatch) before any body byte. The timeout is restored in `finally`. The JSON codec is unchanged.
- **`register_scoped`.** Only pure validation and the attachment read precede the owner fence. Registration runs under the fence, and installation runs with the control lock released. The post-install fence takes only the control lock and calls nothing. The sentinel appears only in the success reply, and every error path releases the owner before the error frame.
- **Revoke and closeout.** Every refusal holds the registry and then re-raises. After a revoke only `revoked` or `pruned` is coherent, so `ok:true` means `draining` or `quiescent` with no overdue flight. `revoked_at` comes from the registry receipt. The projection is always codec-encodable.
- **Gateless identity.** `_PARAMETERS` keeps its identity. The only change is the unscoped refusal before the owner fence.
- **Lock order.** No gate call, attachment read or new `hold()` runs under the control lock. The locks gain no new edge and cannot form a cycle.
- **Custody and purity.** Error frames carry only codes. Scope errors have no chained context. The case-27 scan finds no sentinel or manifest label. The scope module never raises inside an `except` handler, and it calls only `install_scope` and `closeout`.
- **Mutation probes.** Of 28 probes, 22 were killed and 2 were equivalent: the final attachment deadline check, already done by `_recv_exact`, and the unknown-hold `after_revoke` term, already implied by the coherence rule. Four survived:
  - M04, gated `scope_required` moved after the schema check. This was a real test gap.
  - Three `INSTALL_ERROR_CODES` entries that control cannot reach: `grant_expired`, the install-level `manifest_binding_mismatch`, and `scope_conflict`.
- **Race soundness.** Every barrier proves it fired before the test acts, so the outcomes are deterministic. No sleep-based ordering remains.
- **Size.** It is design content, not bloat. The control delta is required docstrings plus the plan's own Module 3 sketch wrapped at 100 columns. The scope module's seven functions come to about 150 lines. The only fat was two unused constants.
- **Runs.** Ten control, listener and supervisor files gave 213 passed twice.

**Non-blocking findings, applied before commit:**
- **T1 (test).** A new case 4c sends a gated `register` with empty parameters and expects `scope_required`. M04 now fails it with `'invalid_schema' == 'scope_required'`.
- **T2 (test).** A literal-table B4 test pins all nine `INSTALL_ERROR_CODES` entries plus an unlisted code. M13, M15 and M16 each fail it with an assertion.
- **T3 (source).** Root removed the unused `SCOPED_GRANT_EXTRA_FIELDS` and `REVOKE_EXTRA_FIELDS`; the reply-key tests pin the literal key sets. This is a recorded deviation from the plan's constant list.
- **D1-D6 (docs).** Root applied the reviewer's wordings:
  - the post-install fence covers only a replacement or shutdown during installation, and a reply after the fence can still reach the old peer, as with Register;
  - without a gate, unscoped `register` gets `scope_type_unavailable`, while a gated controller answers `scope_required` for plain `register` and `scope_type_unavailable` for `register_scoped`;
  - a failed release holds the registry instead of revoking;
  - closeout side effects come from the gate call's registry snapshot and clock tick;
  - `closeout_inconsistent` also covers out-of-range values and a wrong post-revoke lease state.

  The ticket-36 record carried the same overclaim as D1 and was corrected too.

## Addendum re-verification

The same reviewer then re-checked the post-review tree:
- **Source diff:** the only change is the removal of the two constants and their `__all__` entries. Nothing else refers to either name.
- **Test diffs:** the new tests are insertions, and no existing line changed.
- **Mutants:** on a freshly synced copy, M04, M13, M15 and M16 are now killed by assertions.
- **Docs:** D1-D6 are applied as worded, and no other sentence of the new section reads wrong.
- **Runs:** its ten-file command passed 224 tests twice, the earlier 213 plus the 11 new ones.

Addendum verdict: **PASS**.

Two cosmetic wording nits were applied afterwards, in the documentation only. The sentence about the window after the fence now uses the present tense, and "after its fence" became "after its command's owner fence", because there are now two fences.

Final hashes:

```
1cda5cccf796363a5e2db1cb69fd6f20941160d9a408ef7b22ecd6191197f3ef  grafana_jsm_sandbox/forwarder_control_scope.py
984dd90b8ba73863ab87398548a592689543d61599652ba8fd9770862fd4569e  grafana_jsm_sandbox/forwarder_control.py
6cf62daa5ac723714e565a33b96ecdc66d66a49e7850e9b398d27eca11130470  grafana_jsm_sandbox/forwarder_control_protocol.py
a8857aad44ce570a229e870283d0146743d25c355024e56f4a49e78d7645c9af  tests/test_forwarder_control_attachment.py
25c326226a75d3919d702dbb9acf69c22dd18d42def5c44693de24f072e0851b  tests/test_forwarder_control_scope.py
b825296a78b69b02f49077aa64cd473d96dca3373bab37f5efb41063eadf09e2  tests/test_forwarder_control_gate.py
67be26783d491ecc18b683e1cff9788a90389066d79e3168c5b65d298143149c  tests/test_forwarder_control_gate_closeout.py
be4bc5fc6e714ded460f6236ea7bcf61b7cc0cef25c4897f0cafe830372a57a7  tests/test_forwarder_control_gate_races.py
```

## Residual limitations (accepted)

- **Reply after the fence.** A replacement or shutdown after the post-install fence can still let a reply with an inert sentinel reach the old peer. This is the same window as plain Register.
- **Faulty gates.** A `Closeout` whose states are `str` subclasses with a custom `__eq__` could pass the vocabulary check and then fail at `send_frame` without a hold. Only a faulty gate could produce one. The unreachable `INSTALL_ERROR_CODES` entries are pinned but never exercised through control.
- **Handler locals.** The raw manifest bytes and the grant stay as handler locals until the next `register_scoped` or the end of the session. Nothing exposes them.
- **Plan residual risks.** The plan's accepted risks all remain: session blast radius on install failure; scope capacity including retired leases; terminal, coarse holds; overdue detection only on observation; the cross-owner hold; revoke of a retired lease staying fatal; closeout readable for any lease of the generation; closeout side effects; pairing by generation only; slow commands against the heartbeat window; import coupling; gateless Jira registration without a scope; and in-process, 310-second closeout memory.
- **Timing.** Two loose wall-clock bounds (`elapsed < 1.0` in cases 5 and 7) remain, where a regression would take about two seconds.
