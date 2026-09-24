# Raw Notification ingress sanitizer: one Grafana Notification body to a sanitized `SourceRecord` (unit 16)

2026-09-23, revision 2 (critic pass). **Baseline:** `1a62de7` (unit 15b). This is the sixteenth local application unit under the [approval record](../native-runtime-source-implementation-approval.json), and the second unit of the ticket-37 Receiver-owned recovery journal. Its authority is proposal step 2 (`native-runtime-source-implementation-proposal.md` L32-37) and Deferred 1 of the unit-15 plan.

**Scope.** Source and synthetic tests only. Tests read the committed ticket-14 captures and `fixtures/notification-*.json` read-only; one seam test uses a private `tmp_path` journal with real syncs. No test writes a repository file. Out of bounds: push, provider/native/tenant calls, real credentials, C2 retries, paid experiments, deployment, Grafana provisioning, and any edit to `receiver.py`, `notification.py`, the existing `journal_*` and `recovery_journal` modules, or any existing test file. Run the full suite before committing. Every existing test file stays byte-identical.

**Protected state.** Four dirty paths exist at baseline (re-checked 2026-09-23 with `git status --porcelain`):
- `.scratch/many-alerts-one-incident/issues/19-mcp-grafana-behind-the-sentinel.md` (modified);
- `.scratch/many-alerts-one-incident/reviews/planning-frontier-2026-09-18.md` (modified);
- `.scratch/many-alerts-one-incident/reviews/ticket-19/c2-ingestion-execution-draft.md` (untracked);
- `.scratch/many-alerts-one-incident/reviews/ticket-19/c2-ingestion-session-outcome.md` (untracked).

None of them is edited, staged or committed. Ticket 19 C2 is out of scope. Staging uses explicit paths only.

**How this plan was made.** Two independent designs were judged: `design-strict` (an exact allowlist over the committed parser; probes in `u16-design/probe-a/`) and `design-robust` (refuse only what Go cannot emit, with a second bounded parser; probes in `u16-design/probe-b/`). Strict is the structural base; robust supplies the refusal-safety stance. "Design judgment" gives the scores, the errors found in each, and the claims re-measured.

**Revision 2** resolves all fourteen issues of the completeness critic (`u16-design/critic.md`, probes in `u16-design/critic-probe/`); see "Critic issues resolved (revision 2)". The critic independently recomputed all six goldens and confirmed that the `forwarder_json` keyword is additive. The main changes:
- validation runs in two phases, so every 400-class check over every member precedes any 422-class check, and every member-level 422 names its members;
- the summary lists Resolved members first, drops the HTTP class, gains a stable `refused_group` key, and is fully validated;
- `json_unicode` is now 422;
- `oversize_refusal` is public;
- the `startsAt` note names Fingerprints.

Facts marked "probe sN" were checked by the synthesizer with scripts in `u16-design/synth-probe/`. They ran against a prototype of the module below (`tree/grafana_jsm_sandbox/journal_ingress.py`: revision 2 is 406 lines without docstrings or `__all__`; revision 1 is kept as `journal_ingress_rev1.py`) and a scratch copy of the package carrying the proposed `forwarder_json` keyword:
- s1 `survey.py`: all captures and fixtures; s2 `goldens.py`; s3 `ceilings.py`: the realistic N-alert template and the measured boundary;
- s4 `adversarial.py` and `arraycap.py`: bound and code cases; s5 `props.py`: permutation, allowlist, digest variants and fuzz;
- s6 `seam.py`: sanitized sources through the committed `admit`; s7 `apply_patch.py` plus the existing suites on the patched copy (`full-suite-patched.txt`);
- s8 `rev2.py` (revision 2): phases, members, `refused_group`, custody, summary validation, exception injection and summary sizes.

Probes ran on macOS 25.6 with Python 3.13.7.

**Proposal marking.** Every limit, code string, class, name and mapping below is a proposed routine choice that requires review (spec L341-347). "Proposals requiring ratification" lists them.

**Citation keys.** `plan` is `reviews/recovery-journal/implementation-plan.md` (unit 15). `spec Lnn` is `reviews/ticket-37/recovery-specification.md`. `f31` and `sc31` are ticket-31 `fixture-spec.md` and `source-checks.md`. `strict` and `robust` are the two designs; `S-En` and `R-En` name the errors found in them below. `critic N` names critic issue N.

These facts were re-read against the working tree on 2026-09-23:
- **Receiver today.** The handler reads `Content-Length` bytes (receiver.py L139), runs the legacy `validate_notification` (notification.py L22-43: plain `json.loads`, truthy `fingerprint` and `status`), and on failure answers 400 with `str(error)`, which echoes caller data (receiver.py L140-144). This unit leaves both files alone.
- **The record contract** (journal_source.py):
  - `SourceRecord`, `SourceAlert` and `HTTP_PROVENANCE` (L97-121); bounds 32 alerts, 64 values, 4,096 canonical bytes, fingerprint 64, refId 32, `groupKey` 1,024, `starts_at` 30, `truncated_alerts` 2^31-1 (L30-37);
  - `BODY_TAG = "rj.body.v1"`, "computed by the (deferred) ingress unit" (L42-43);
  - `source_group_digest` accepts only printable ASCII of 1..1,024 characters (L170-177);
  - `_parse_values` allows a `null` value inside `values` (L280); `_parse_provenance` accepts only `HTTP_PROVENANCE` (L253-264);
  - `validate_source` round-trips through JSON and raises `source_too_large` last (L341, L346-352). It reaches `canonical_json`, which raises `JSONPolicyError`, not `SourceError`.
- **The house parser** (forwarder_json.py):
  - `MAX_JSON_STRING_BYTES = 16_384` is a module constant (L27), applied by `_check_string` (L68-74) to every key (L133) and string (L146) in `_postwalk`;
  - `parse_json(data, *, max_bytes, numbers="integer", ascii_only=False)` has no string-cap parameter (L170-187);
  - its five production callers are `forwarder_routes` L467, L808 and L1019, `journal_records` L528 and `journal_store` L466. The parser is shared by the Forwarder and the journal.
- **Captures.** 115 JSONL rows in `reviews/ticket-14/jira/notifications-*.jsonl`. Each row holds a parsed `body`, not raw bytes, plus `raw_len`, `n_alerts` and `path: "/notification"`. Every capture contains `&`; none contains `<` or `>` (critic).
- **Grafana provisioning.** The contact point is a webhook with only `url` and `httpMethod` (grafana/provisioning/alerting/contact-point.yaml L14-17): the default title and message templates, and no maximum-alerts setting. The policy groups by `grafana_folder` and `alertname` with a 10 s `group_interval` (notification-policy.yaml L16-20). The image is `grafana/otel-lgtm:latest`, unpinned (docker-compose.yml L25).
- **Prior unit commits** (`git show --stat f68c9aa 1a62de7`) carried the plan, `validation-*.json`, focused and full suite logs, outcome and review files, plus updates to `execution-backlog.md` and the ticket-37 issue file.
- **Full suite at baseline:** 4012 passed, 38 skipped (`recovery-journal/full-suite-15b.txt`).

**Root note from review, 2026-09-23.** `refusal_to_json` enforces the code table, not just the rule list below:
- Every member code except `ingress_group_key_unsupported`, and an `ingress_divergence` that carries members, must set `source_group` and leave `refused_group` unset.
- `ingress_too_many_alerts` requires `alerts > 32`.
- `ingress_too_many_values`, `ingress_record_too_large`, and an `ingress_divergence` that carries members, require `alerts <= 32`.

The sanitizer's step order already guarantees these, so the change only rejects hand-built summaries that could never be produced. `docs/forwarder-control.md` gained one sentence recording that only the ingress sanitizer passes `max_string_bytes`.

**Final-review corrections.**
- N15 applies to member-level 422s only. Parser-level `ingress_json_unsupported` is decided before phase 1, so it can land on a body that is provably not Grafana's, such as a NUL in `message` alongside a bad status. This is the plan's own conservative choice, and the documentation and module docstring now say so.
- `_members_ok` requires an exact empty tuple for member-less refusals.
- The module stays at 509 lines, not split. The final reviewer judged a split for 7 lines not worth a new module and re-review. The refusal summary's natural seam is Deferred 3, when it becomes a durable record type.

## Why this unit

Spec L193 opens the admission transaction with "Validate and bound ingress". The unit-15 journal already defines the bounded `SourceRecord` and `admit(source)`, but nothing turns the bytes Grafana posts into that record. Plan Deferred 1 names this unit, and plan Deferred 2 (Receiver integration) cannot start without it.

Building the sanitizer as a pure module first has three benefits:
- its refusal policy, which decides which real Notifications are lost to OPS, can be reviewed against all 115 captures before any HTTP behaviour changes;
- plan P1 (ii) left the HTTP class of a bound refusal to this unit, and plan residual risk "Refused Notifications" (L1425) requires those refusals to be visible;
- the later integration then only wires a reviewed, total function between `Content-Length` and `admit`.

## Design judgment

Scores are 1-10 per criterion.

| Criterion | Strict | Robust |
| --- | --- | --- |
| Spec and plan fidelity | 6 | 5 |
| Refusal safety for legitimate Notifications | 4 | 9 |
| Boundedness and custody | 9 | 6 |
| Simplicity and reviewability | 7 | 4 |
| Testability | 9 | 8 |
| No invented inputs | 5 | 6 |
| **Total (of 60)** | **40** | **38** |

**Errors in `design-strict`:**
- **S-E1.** It refuses an absent `startsAt` (400), an offset time (422) and a non-calendar time (400). Spec L157 stores the source event time "if supplied", and plan P15 makes `starts_at` provenance only, so each of these refusals loses a Notification over a field that is not in the dedupe key.
- **S-E2.** It tightens plan P3 and P15 without cause: an absent `truncatedAlerts`, an absent `values` and a `null` inside `values` all give 400. The plan's resolution of J1 S-E8 maps absence to `null`, and P3 allows `null` values (journal_source L280).
- **S-E3.** It reads two fields the record never holds and refuses on them: `version == "1"` (422, which refuses every Notification after an upstream version change on the unpinned image) and a top-level `status` witness (400).
- **S-E4.** It keeps the 16 KiB string cap on the ignored `message`, giving an effective ceiling of 19 alerts, below the journal's own P1 (ii) bounds (probe s3). Those refusals carry no counts. It recognises this (its U16-P7) but recommends accepting it.
- **S-E5.** It classes `json_unicode` as input "Go's encoder cannot emit". Go escapes a NUL byte as `\u0000`, so a NUL in a label or annotation is Go-emittable; only lone surrogates are not.
- **S-E6.** It maps the unreachable `json_too_large` to `ingress_too_large` while that path carries a digest, which contradicts its own rule "`body_digest` is None iff `ingress_too_large`" (its G10). Unreachable codes should map to `ingress_divergence`.
- **S-E7.** Its refusal summary carries counts and a `source_group` digest but no Fingerprints. An operator can neither tell which Resolved members were lost nor invert the group digest.
- **S-E8.** 23 codes, three of them (`ingress_version`, `ingress_notification_status`, `ingress_starts_at_offset`) for inputs that never reach the record.

**Errors in `design-robust`:**
- **R-E1.** A second hand-rolled JSON parser (hooks plus a copied depth prescan) duplicates security-critical code from `forwarder_json` and needs a differential test to stay aligned. The refusal it removes, the string cap, is removed equally well by one additive keyword on the reviewed parser (probe s7).
- **R-E2.** `MAX_BODY_BYTES = 1 MiB` contradicts plan Deferred 1 (256 KiB) without need. A realistic 32-alert body is 68 KiB (probe s3); the 1 MiB case is a synthetic body with 14 extra labels and 4-8 KiB descriptions per alert.
- **R-E3.** U3 stores integer lexemes above 2^53-1 in `JSONDecimal`, whose contract is "a validated RFC 8259 non-integer lexeme" (forwarder_json L59), and amends plan P2.
- **R-E4.** U4 and U5 invent two digest tags and a refId namespace (`"_"` plus 31 hex characters) that freeze into v1 records and amend P3 and P16. Neither shape occurs in the captures or the repo-provisioned rules. A refusal can later be loosened; an admitted mapping cannot be taken back.
- **R-E5.** U7 drops every `starts_at` when the record exceeds 4 KiB, so the stored provenance of one member depends on the size of its group. P1 (ii) permits only refusal.
- **R-E6.** U6 trims trailing fraction zeros from a verbatim provenance field and adds timezone arithmetic for a shape no capture shows.
- **R-E7.** P1 (ii) refusals are 413 (Content Too Large) for bodies of about 70 KB; the bounds are semantic, not byte size. The alert count is also checked before members are validated, so a malformed 33-alert body is classed as lost real data. (Revision 1 of this plan repeated the second half for refIds and `groupKey`, critic 1; revision 2 fixes it with two phases.)
- **R-E8.** Five note codes and ten summary fields for mostly unobserved shapes enlarge the review surface.

**Claims re-measured:**

| Claim | From | Synthesizer result |
| --- | --- | --- |
| All 115 captures admit | both | s1: 115 of 115 under this plan's rules, no dropped `startsAt` |
| A Go-style re-encoding reproduces `raw_len` | both | s1: 115 of 115 (length only, not byte identity) |
| `message` grows about 838 B per alert and crosses 16 KiB near 19 alerts | strict | s1: 838.2 B per alert minus 21.9 B, crossing at 19.57 alerts |
| At 20 alerts `message` is 16,815 B and the house parser refuses | robust | s3: realistic template, CG1 and CG2, firing and resolved: 19 admitted, 20 refused (`message` 16,576-16,818 B) |
| 28 two-value members fit 4 KiB, 29 do not | both | s3: 28 admitted (3,992-4,048 B; the 29th projection is 4,117-4,175 B) |
| 21 three-value alerts fit, 22 exceed 64 values | robust | s3: equal |
| The six goldens | both | s2: equal, and each recomputed independently; CG1, CG2 and the legacy group equal the plan. The critic recomputed them again with no repo import |
| Captured record maximum 800 B (plan says 849) | both | s1: 375-800 B; the plan's 849 is not reproduced |
| The legacy validator accepts every admitted body | strict | s1: 115 of 115 and 3 of 3 |
| Seam: admitted, suppressed, pending_reduced, admitted, pending_reduced | robust | s6: equal, through the committed `admit` |

**What the synthesis keeps.** From strict: the house parser and its error discipline, the 256 KiB bound, refusals as return values, the 400/413/422/500 class rule, fixed step precedence, the grammar-parity test and its test structure. From robust: refuse only what Grafana's encoder cannot emit or the journal cannot hold; plan-faithful absence; `startsAt` never refuses; `version` and top-level `status` not read; Fingerprints in the refusal summary; the resend hypothesis as a design input; the seam test; the realistic N-alert generator.

## Decisions

**D1. Parser strategy: an additive `max_string_bytes` keyword on `forwarder_json.parse_json` (option c).**

| Option | Custody | Attack surface | Refusal of legitimate Notifications | Verdict |
| --- | --- | --- | --- | --- |
| (a) `parse_json` as-is | Nothing free-text is stored; strings of at most 16 KiB are held briefly | Nothing added | `message` crosses 16 KiB at 20 alerts; one alert with an annotation over 16 KiB is refused; these refusals carry no counts | Rejected: the ignored `message` binds below the journal's P1 (ii) |
| (b) a second parser in the new module | Same stored custody; the exception discipline must be re-implemented | A second parser of hostile bytes, about 65 lines | Ceiling = journal bounds | Rejected: duplicates reviewed security code (R-E1) |
| **(c) additive keyword** | Same stored custody; inherits the reviewed discipline | One integer parameter with a default; the five existing calls are unchanged | Ceiling = journal bounds | **Chosen** |
| (d) a short custom `message` template or a maximum-alerts setting on the contact point | - | A provisioning change | Unverified without a live Grafana | Deferred as a mitigation |

Custody is equal across (a)-(c): the read set is an allowlist, and ignored strings are parsed and dropped. The difference is refusal safety. A refused Resolved leaves OPS stale. The premise from the brief, that Grafana does not retry a 4xx within a flush, is part of the unprobed resend hypothesis (see "Refusal codes"), and a refusal loses the update either way. The string cap is a Forwarder-response rule with no meaning for an ignored ingress field.

**Ceiling under (c)**, for this demo's templates (probe s3):
- 28 alerts with two values each (A decimal, B integer; both multi-alert rules), bound by the 4 KiB record; 29 give `ingress_record_too_large`;
- 21 alerts with three values, bound by 64 values; 22 give `ingress_too_many_values`;
- 32 value-free alerts, bound by 32 alerts;
- a 32-alert realistic body is about 68 KiB, 3.8 times under the body bound.

Under (a) the ceiling is 19 for every template measured, whatever the value count. The captures peak at 4 alerts.

**D2. Body bound: 262,144 bytes** (plan Deferred 1), checked before any hashing or decoding. Ingress passes the same value as `max_string_bytes`, so the body bound is the only string bound. Robust's 1 MiB is not adopted (R-E2).

**D3. Read set.** `groupKey`, `truncatedAlerts`, `alerts`, and per alert `fingerprint`, `status`, `values` and `startsAt`. Nothing else is read, including `version` and the top-level `status` (S-E3). Unknown fields are ignored, not refused.

**D4. Absence follows the plan.** An absent or `null` `truncatedAlerts` gives `None` (P15), and an absent or `null` `values` gives `None` (P3). A `null` inside `values` is kept as `None`. A present value of the wrong type is refused (400), because Grafana's encoder always emits an integer and a `map[string]float64`.

**D5. `startsAt` never refuses.**
- The exact string `0001-01-01T00:00:00Z` (Go's zero time) gives `None`, and is not reported.
- Absent or `null` gives `None`, and is not reported ("if supplied", spec L157).
- A string that matches the journal's Z grammar (ASCII digits only), is at most 30 characters and is a real calendar time is kept byte-exact.
- Anything else gives `None`, and the member's Fingerprint is added to `IngressOutcome.starts_at_dropped`. This includes a numeric offset, non-ASCII digits and 31 or more characters.

That tuple is sorted and has at most 32 entries (critic 14). It is not persisted: the `admission` record has no field for it, so the integration logs or counts it (Deferred 1). Offset conversion is a later loosening candidate.

**D6. Grafana could send it, but v1 cannot hold it: refuse with 422 and name the members, never map.** This covers:
- a `groupKey` that is not printable ASCII or is over 1,024 characters;
- a refId outside `[A-Za-z0-9._-]{1,32}`;
- an integer above 2^53-1;
- a NUL in any string;
- more than 256 alerts.

None occurs in the captures or the repo-provisioned rules. Each mapping in robust U3-U5 is an ingress-only, additive loosening candidate that needs ratification first (R-E4).

**D7. P1 (ii) is enforced by refusing the whole Notification with 422.** More than 32 alerts, more than 64 values, or more than 4,096 canonical bytes. Nothing is split, truncated, merged, or stripped of `starts_at` (R-E5).

**D8. The refusal summary is a value here; its persistence is re-deferred (U16-P16).**
- `IngressRefusal` and `refusal_to_json` are defined here.
- The summary carries the **code only, never an HTTP status** (critic 3). The class is a property of the response, chosen at the seam from the proposal map `INGRESS_HTTP_STATUS`, so a later policy change (for example 202 plus a hold) never makes stored summaries false.
- Members are listed **Resolved first, then by Fingerprint**, and truncated to 32 after ordering (critic 2).
- `refused_group` gives every refusal after the `groupKey` check a stable key that survives Grafana's re-renders (critic 4; D12).
- Durable persistence needs a new record type in `journal_records`' closed v1 registry, a reducer transition, a flood policy and the HTTP seam, so it belongs to the integration unit (Deferred 3).

**D9. Provenance is always `HTTP_PROVENANCE`.** The `capture` kind needs a `journal_source` change (L253-264), which under plan R1 bumps the admission `schema_version`, and its only consumer, the f31 replay harness, does not exist. f31 L127-129 requires Receiver acceptance through the real `/notification` boundary, and every capture row's envelope names `path: "/notification"`, so `http` is truthful for replayed captures.

**D10. `body_digest = sha256(b"rj.body.v1" + b"\x00" + body)`** over the exact bytes passed, with no decoding, stripping or re-encoding. It is computed after the size check and before parsing, so every refusal except `ingress_too_large` carries it.

**D11. Two phases (critic 1).**
- **Phase 1** runs every 400-class check over the whole body and every member before anything else. The checks cover the root shape, the syntactic `groupKey` check, `truncatedAlerts`, the `alerts` shape, and for each member the object, Fingerprint, status and value types. Duplicate Fingerprints come last.
- **Phase 2** runs the 422-class checks in a fixed order: `groupKey` support, refId grammar, then the P1 (ii) bounds.

So a body that is provably not Grafana is always 400, whatever else is wrong. The class of a mixed `values` object no longer depends on key order. Every phase-2 refusal carries `alerts`, `resolved`, `members` and `members_omitted`. The only 422 refusals without members are the parser-level `ingress_json_unsupported`, where nothing was parsed.

**D12. `refused_group = sha256(b"rj.refused-group.v1" + b"\x00" + groupKey.encode("utf-8"))`.**
- It is set whenever `groupKey` is a non-empty string that `source_group_digest` refuses. Such a `groupKey` has no `source_group`, and `tagged_digest` cannot hash it, because canonical ASCII JSON rejects exactly these keys.
- It is a refusal-only key, never an admitted mapping, so R-E4 does not apply.
- The flood key of Deferred 3 is `(code, source_group or refused_group or None)`. Parser-level and pre-`groupKey` refusals share one key per code.

## Unit boundary

**In** (one reviewed local commit):
1. `grafana_jsm_sandbox/journal_ingress.py`: new and pure, about 400-450 lines (split point in "Module").
2. `grafana_jsm_sandbox/forwarder_json.py`: the additive keyword (17 added and 6 changed lines, plus one docstring sentence).
3. Four new test files: `tests/test_journal_ingress.py`, `tests/test_forwarder_json_string_cap.py`, `tests/test_journal_ingress_corpus.py` and `tests/test_journal_ingress_adversarial.py`. No new data file.
4. A new "Ingress" section in `docs/recovery-journal.md`, owned by root.
5. Evidence and tracking, owned by root and following units 15a and 15b (critic 11):
   - this plan;
   - `reviews/journal-ingress/validation.json`, `focused-tests.txt`, `full-suite.txt`, `outcome.md` and `review.md`;
   - the unit-16 entry in `.scratch/many-alerts-one-incident/execution-backlog.md`;
   - the progress note in `.scratch/many-alerts-one-incident/issues/37-run-recovery-and-admission-specification.md`.

**Out** (see "Deferred"):
- `receiver.py`, the HTTP handler, `Content-Length` handling, response bodies and the swap away from `validate_notification`;
- the body spool, `admit` wiring, and the 503 mapping;
- the durable refusal record and its flood policy;
- the `capture` provenance kind;
- operator actions;
- Grafana provisioning;
- retiring `notification.py`.

## Module: `grafana_jsm_sandbox/journal_ingress.py` (new, pure)

**Responsibility:** one raw Notification body (`bytes`) in; a validated `SourceRecord` or a fixed-code refusal out. No clock, randomness, filesystem, environment, network, logging or state. It runs on Python 3.11, because it does not touch SQLite.

**Size.** Target 400-450 lines; the revision-2 prototype is 406 lines without docstrings or `__all__`. If the module passes 500 lines, the refusal-summary section moves to `grafana_jsm_sandbox/journal_ingress_summary.py`, with the same owner and API, as unit 15 did at its split trigger. That section is `_groups_ok`, `_members_ok` and `refusal_to_json`, about 90 lines.

**Imports (AST-checked, exact):**
- `from __future__ import annotations`;
- `dataclasses`, `datetime` (calendar validation only), `hashlib`, `re`, and `from types import MappingProxyType`;
- `from .forwarder_json import MAX_JSON_ARRAY_ITEMS, MAX_SAFE_INTEGER, JSONDecimal, JSONPolicyError, canonical_json, parse_json`;
- `from .journal_source import ALERT_STATUSES, BODY_TAG, HTTP_PROVENANCE, MAX_ALERTS, MAX_FINGERPRINT_BYTES, MAX_REF_ID_BYTES, MAX_STARTS_AT_BYTES, MAX_TRUNCATED_ALERTS, MAX_VALUES, SourceAlert, SourceError, SourceRecord, canonical_number, source_group_digest, validate_source`.

It must not import `journal_records`, `journal_store`, `journal_reducer`, `recovery_journal`, `receiver`, `notification`, `json`, `sqlite3`, `os`, `socket`, `logging` or `time`.

**Public API:**

```python
MAX_INGRESS_BODY_BYTES = 262_144
MAX_INGRESS_STRING_BYTES = MAX_INGRESS_BODY_BYTES     # passed to parse_json
MAX_REFUSAL_MEMBERS = MAX_ALERTS                       # 32
MAX_REFUSAL_JSON_BYTES = 4_096                         # canonical summary bound
GO_ZERO_TIME = "0001-01-01T00:00:00Z"
REFUSED_GROUP_TAG = "rj.refused-group.v1"

INGRESS_REFUSAL_CODES: frozenset[str]                  # 16 codes (table below)
MEMBER_CODES: frozenset[str]                           # the 5 phase-2 codes; they always carry members
INGRESS_ERROR_CODES = frozenset({"ingress_argument"})
JSON_REFUSAL_CODES: MappingProxyType[str, str]         # total over forwarder_json.JSON_ERROR_CODES
INGRESS_HTTP_STATUS: MappingProxyType[str, int]        # PROPOSAL for the HTTP seam; never persisted

class IngressError(ValueError):                        # caller bugs only; .code; args == (code,)
    code: str

@dataclasses.dataclass(frozen=True)
class IngressRefusal:
    code: str                                          # in INGRESS_REFUSAL_CODES
    body_bytes: int                                    # len(body), or the declared length (oversize)
    body_digest: str | None                            # hex64; None only for ingress_too_large
    source_group: str | None                           # hex64 once groupKey is supported
    refused_group: str | None                          # hex64 when groupKey is a string it refuses (D12)
    alerts: int | None                                 # member count; phase-2 codes only
    resolved: int | None                               # Resolved members; same condition
    members: tuple[tuple[str, str], ...]               # (fingerprint, status), Resolved first, <= 32
    members_omitted: int                               # alerts - len(members)

@dataclasses.dataclass(frozen=True)
class IngressOutcome:                                  # exactly one of source / refusal is set
    source: SourceRecord | None
    refusal: IngressRefusal | None
    starts_at_dropped: tuple[str, ...]                 # sorted Fingerprints (D5); () on refusal

def body_digest(body: bytes) -> str
def sanitize_notification(body: bytes) -> IngressOutcome
def oversize_refusal(declared_length: int) -> IngressRefusal
def refusal_to_json(refusal: IngressRefusal) -> dict[str, object]
```

- **Argument errors.** `body_digest` and `sanitize_notification` raise `IngressError("ingress_argument")` for anything but exact `bytes` (`bytearray`, `memoryview` and `str` included). That is the only exception either function raises.
- **`oversize_refusal(declared_length)`** (critic 7) lets the integration refuse from a `Content-Length` header without reading the body.
  - It requires an exact `int` with `262,144 < declared_length ≤ 2^53-1`, else `ingress_argument`.
  - It returns the `ingress_too_large` refusal with no digest, group or members.
  - `sanitize_notification` uses it for its own S1, so the two paths are equal.
- **`refusal_to_json(refusal)`** re-validates every field and every cross-field rule, then encodes. It raises `ingress_argument` for any violation (critic 7):
  - the exact type, and a code in the closed set;
  - `body_bytes`: an int in 262,145..2^53-1 for `ingress_too_large`, and 0..262,144 otherwise;
  - `body_digest`: `None` for `ingress_too_large`, hex64 otherwise;
  - groups: each hex64 or `None`, and at most one set:
    - neither for `ingress_too_large`, `ingress_json_invalid`, `ingress_json_unsupported` and `ingress_group_key`;
    - only `refused_group` for `ingress_group_key_unsupported`;
    - at most one for `ingress_shape` and `ingress_divergence`;
    - exactly one for every other code;
  - counts: `alerts is None` exactly when `resolved is None`, `members == ()` and `members_omitted == 0`;
    - required for `MEMBER_CODES`, optional for `ingress_divergence`, forbidden otherwise;
    - `1 ≤ alerts ≤ 256`, `0 ≤ resolved ≤ alerts`, `len(members) == min(alerts, 32)` and `members_omitted == alerts - len(members)`;
  - members: 2-tuples of a grammar-valid Fingerprint and a status; strictly increasing by `(status != "resolved", fingerprint)`; unique Fingerprints; and the Resolved entries listed equal `min(resolved, len(members))`;
  - encoding: `canonical_json(summary, ascii_only=True)` succeeds and is at most 4,096 bytes; a `JSONPolicyError` becomes `ingress_argument`.

  It returns exactly nine keys: `alerts`, `body_bytes`, `body_digest`, `code`, `members` (a list of `[fingerprint, status]` lists), `members_omitted`, `refused_group`, `resolved` and `source_group`. There is no `http_status`.

**House rules** (as in unit 15):
- exact-type checks only;
- closed sets in `frozenset`s and `MappingProxyType`s, and `__all__`.

**Error discipline** (critic 8). Every `except` body only assigns a local `code`. No raise appears in a handler, and `IngressError` is raised `from None`. Refusals are return values: no exception carries caller data, and the summary never travels on one. The `try` statements and their exact tuples:

| Call | Caught | Result |
| --- | --- | --- |
| `parse_json` | `JSONPolicyError` | `JSON_REFUSAL_CODES[error.code]` |
| `source_group_digest` | `SourceError` / `JSONPolicyError` | unsupported (`refused_group` computed) / `ingress_divergence` |
| `canonical_number` | `(SourceError, JSONPolicyError)` | `ingress_divergence` |
| `validate_source` | `SourceError` / `JSONPolicyError` | `source_too_large` → `ingress_record_too_large`, else `ingress_divergence` / `ingress_divergence` |
| `datetime.datetime(...)` | `ValueError` | the time is dropped |
| `canonical_json` (in `refusal_to_json`) | `JSONPolicyError` | `ingress_argument` |

**Duplicated grammars.** `[A-Za-z0-9._-]{1,64}`, `{1,32}` and the Z-time grammar are rebuilt from `journal_source`'s public `MAX_*` constants, because its patterns are private. They let ingress return a 4xx code or drop a time rather than diverge. Test I7 pins parity with `validate_source`.

## Accepted input shape

The whole body first passes `parse_json(body, max_bytes=262_144, numbers="finite", max_string_bytes=262_144)`. Its rules apply to every field, read or ignored:
- strict UTF-8 with no BOM;
- no duplicate key at any depth;
- depth of at most 16;
- at most 256 items per array;
- no NUL and no lone surrogate in any string;
- number lexemes of at most 32 characters;
- |integer| ≤ 2^53-1;
- finite decimals only (no `NaN`, `Infinity` or overflow).

Only then is the object projected.

| Field | Read | Accepted | Mapping | Otherwise |
| --- | --- | --- | --- | --- |
| body | - | `bytes`, ≤ 262,144 | `body_digest` over the exact bytes | `ingress_too_large` |
| root | yes | an object | - | `ingress_shape` |
| `groupKey` | yes | a non-empty string | printable ASCII ≤ 1,024 → `source_group_digest(groupKey)`, exact, not normalized | absent, not a string or empty: `ingress_group_key` (phase 1); otherwise `ingress_group_key_unsupported` (phase 2, with `refused_group`) |
| `truncatedAlerts` | yes | absent, `null`, or an exact int 0..2^31-1 | absent or `null` → `None`; int → itself | `ingress_truncated` (bool, negative, decimal, string, above 2^31-1) |
| `alerts` | yes | a non-empty array of objects | one `SourceAlert` per element, sorted by Fingerprint | `ingress_shape`; over 256 items `ingress_json_unsupported` |
| `alerts[].fingerprint` | yes | `[A-Za-z0-9._-]{1,64}`, unique in the body | verbatim | `ingress_fingerprint`; a repeat gives `ingress_duplicate_fingerprint` |
| `alerts[].status` | yes | exactly `firing` or `resolved` | verbatim | `ingress_status` |
| `alerts[].values` | yes | absent, `null`, or an object whose values are ints, `JSONDecimal`s or `null` | absent or `null` → `None`; `{}` → `()`; otherwise pairs sorted by refId; numbers through `canonical_number`; `null` → `None` | `ingress_values` (phase 1) |
| refId (a `values` key) | yes | `[A-Za-z0-9._-]{1,32}` | verbatim | `ingress_ref_id_unsupported` (phase 2) |
| `alerts[].startsAt` | yes (provenance only) | anything | D5 | never refuses |
| `version`, `status`, `receiver`, `groupLabels`, `commonLabels`, `commonAnnotations`, `externalURL`, `orgId`, `title`, `state`, `message`, any other key | no | any value the parser accepts | dropped | never refuses beyond the parser |
| `alerts[].labels`, `annotations`, `endsAt`, `generatorURL`, `silenceURL`, `dashboardURL`, `panelURL`, `valueString`, `orgId`, `imageURL`, `embeddedImage`, any other key | no | same | dropped (`endsAt` is Go zero time for every firing member) | same |

The minimal admissible body is `{"groupKey":"g","alerts":[{"fingerprint":"f","status":"firing"}]}`, which gives `truncated_alerts`, `values` and `starts_at` all `None` (probe s4).

## Processing order and mapping rules

The first failing step decides the code (test I6).

| Step | Check → result |
| --- | --- |
| S0 | `type(body) is bytes`, else raise `IngressError("ingress_argument")` |
| S1 | `len(body) > 262,144` → `oversize_refusal(len(body))`; no digest is computed |
| S2 | `digest = sha256(b"rj.body.v1\x00" + body)` |
| S3 | `parse_json(...)`; a `JSONPolicyError` maps through `JSON_REFUSAL_CODES` |
| **Phase 1** | **400-class, over the whole body; refusals carry no member counts** |
| S4 | the root is an object, else `ingress_shape` |
| S5 | `groupKey` is a non-empty string, else `ingress_group_key`. Then `source_group_digest`: success sets `source_group`; `SourceError` sets `refused_group` (D12) and defers the refusal to S11; `JSONPolicyError` gives `ingress_divergence`. Every later refusal carries exactly one of the two |
| S6 | `truncatedAlerts` per the table → `ingress_truncated` |
| S7 | `alerts` is a non-empty array, else `ingress_shape` |
| S8 | each element in **body order**: an object (`ingress_shape`), `fingerprint`, `status`, then `values` (an object or `null`, and every value an int, `JSONDecimal` or `null`: `ingress_values`) |
| S9 | any Fingerprint twice → `ingress_duplicate_fingerprint` |
| **Phase 2** | **422-class; every refusal carries `alerts`, `resolved`, `members` and `members_omitted`** |
| S10 | the members are collected as `(fingerprint, status)` |
| S11 | `refused_group` is set → `ingress_group_key_unsupported` |
| S12 | any refId, in any member, outside the grammar → `ingress_ref_id_unsupported` |
| S13 | more than 32 members → `ingress_too_many_alerts` |
| S14 | more than 64 values in total (a `null` value counts, as in the journal) → `ingress_too_many_values` |
| S15 | build each `SourceAlert` (numbers through `canonical_number`, `startsAt` per D5), sort by Fingerprint (code-point order, which is `journal_source`'s `<=` rule under the grammar), build `SourceRecord(source_group, alerts, truncated_alerts, digest, HTTP_PROVENANCE)`, and call `validate_source`: `source_too_large` gives `ingress_record_too_large`; anything else caught gives `ingress_divergence` |
| S16 | return the admitted outcome with `starts_at_dropped` |

**Numbers change only through `canonical_number`** (plan P2): `100.0` gives `"100"`, `1e-7` gives `"1e-07"`, `-0` gives `"0"`, and `1e-400` gives `"0"`. `canonical_number` cannot fail on `parse_json` output, so a failure is `ingress_divergence`. Strings are copied byte-exact; the only normalization is Go zero time to `None`.

## Worked examples

All values were measured with the prototype (probes s1, s2, s3, s8). Capture bytes are the Go-style reconstruction, `wire(body)`: `json.dumps(body, separators=(",", ":"), ensure_ascii=False)`, then `<`, `>`, `&`, U+2028 and U+2029 replaced by the **lowercase** escapes `<`, `>`, `&`, ` ` and ` ` (Go's form), then UTF-8. Fixture bytes are the exact file bytes.

**E1. One alert: payment line 1** (2,985 B, CG1). The read fields are `groupKey "{}:{alertname=\"Service error rate is elevated\", grafana_folder=\"demo\"}"`, `truncatedAlerts 0` and one alert `{fingerprint "5e8d72dc87b1ff35", status "firing", startsAt "2026-09-17T21:56:20Z", values {"A":0.11440082443757411,"B":1}}`. The 834-byte `message` and `endsAt "0001-01-01T00:00:00Z"` are ignored. The canonical record is 393 B:

```json
{"alerts":[{"fingerprint":"5e8d72dc87b1ff35","starts_at":"2026-09-17T21:56:20Z","status":"firing","values":{"A":"0.11440082443757411","B":"1"}}],
 "body_digest":"0dd74a18eb42deb3bcbdcda622b156df45c85021550cff705a672e626f528da4",
 "provenance":{"kind":"http","line":null,"path":"/notification"},
 "source_group":"5deaf914a2a751fefe64e9b9077fdadad2f5fe11c224ba5451d6d66bb6c7876e","truncated_alerts":0}
```

`source_group` is the plan's CG1 golden, and `dedupe_key` is `b4f1f3da…`.

**E2. Multi-alert, unsorted, mixed statuses: payment line 16** (7,169 B, CG1). The body order is `6cd7e206a0716d2d` resolved, `5e8d72dc87b1ff35` firing, `8e2d9556f6c757b5` resolved. S15 sorts them, and each keeps its own `startsAt`. The canonical record is 662 B:

```json
{"alerts":[
  {"fingerprint":"5e8d72dc87b1ff35","starts_at":"2026-09-17T21:56:20Z","status":"firing","values":{"A":"0.1999991666701389","B":"1"}},
  {"fingerprint":"6cd7e206a0716d2d","starts_at":"2026-09-17T21:58:30Z","status":"resolved","values":{"A":"0.09999958333506945","B":"0"}},
  {"fingerprint":"8e2d9556f6c757b5","starts_at":"2026-09-17T21:58:20Z","status":"resolved","values":{"A":"0.09999958333506945","B":"0"}}],
 "body_digest":"db9eea9713d51f6eb11f3a029fd496aa37949124a9dced0308a2e5d96d193157",
 "provenance":{"kind":"http","line":null,"path":"/notification"},
 "source_group":"5deaf914a2a751fefe64e9b9077fdadad2f5fe11c224ba5451d6d66bb6c7876e","truncated_alerts":0}
```

The members equal sc31 line 16 once sorted. Shuffling the alerts or reversing each `values` object changes only `body_digest` (22 of 22 multi-alert captures, probe s5).

**E3. The largest capture: payment line 21** (9,333 B, CG2, four resolved members `4396dcd5ddc23476`, `4bde20aac01f95a2`, `b3587dd72657d226`, `f09facf2b8f5b694`). The record is 800 B, and `source_group` is the CG2 golden `9d37267f…`.

**E4. Integers and three refIds: email line 57.** `values {"A":55042048,"B":55042048,"C":0}` becomes `(("A","55042048"), ("B","55042048"), ("C","0"))`, and the record is 399 B.

**E5. Legacy fixture bytes.** `notification-firing.json` is 2,611 bytes of pretty-printed JSON; `body_digest` covers those exact bytes (`8384bd0b…`). `notification-firing-repeat.json` is byte-identical, so the two produce equal `SourceRecord`s, with dedupe key `a99b74e0…` (the plan golden); the journal suppresses the repeat (probe s6). A compact re-encoding of the same JSON gives the same members, group and key, and a different `body_digest` (probe s5).

**E6. Plan-faithful leniency.** Payment line 1 with `truncatedAlerts` removed and `startsAt` set to `2026-09-17T23:56:20+02:00` is admitted. `truncated_alerts` and `starts_at` are both `None`, `starts_at_dropped` is `("5e8d72dc87b1ff35",)`, and the dedupe key is unchanged (`b4f1f3da…`). Because `truncated_alerts` is `None`, the reducer never suppresses the arrival (plan P1 (i)).

**E7. A P1 (ii) refusal.** The realistic CG2 template with 33 resolved alerts is a 70,510-byte body. It gives `ingress_too_many_alerts` (proposed class 422), and `refusal_to_json` is 1,319 canonical bytes (abridged):

```json
{"alerts":33,"body_bytes":70510,"body_digest":"fd1ae36b…","code":"ingress_too_many_alerts",
 "members":[["040ffd5925d40e11","resolved"],["07fc5bb598e2360d","resolved"], … 32 pairs …],
 "members_omitted":1,"refused_group":null,"resolved":33,"source_group":"9d37267f…"}
```

With 32 firing members and one Resolved, the Resolved member is listed first and a firing one is omitted (probe s8).

**E8. A non-ASCII folder, resent.** Payment line 21 with `grafana_folder="Démo"` in its `groupKey` gives `ingress_group_key_unsupported` with all four Resolved members named (426 canonical bytes):

```json
{"alerts":4,"body_bytes":9334,"body_digest":"c4ca7840…","code":"ingress_group_key_unsupported",
 "members":[["4396dcd5ddc23476","resolved"],["4bde20aac01f95a2","resolved"],["b3587dd72657d226","resolved"],["f09facf2b8f5b694","resolved"]],
 "members_omitted":0,"refused_group":"bfd435c57f24bde912e9e7b47c2977986bab5b585c6c8e50f76c652b592dd8fc","resolved":4,"source_group":null}
```

A re-render of the same group with two members and a different `message` has a different `body_digest` and the same `refused_group` (probe s8).

## Refusal codes and proposed HTTP classes

**The class rule** (a proposal for the HTTP seam; the class is never persisted):
- **413:** the body exceeds the byte bound.
- **400:** the bytes are not a well-formed Grafana Notification in a way Grafana's Go encoder cannot produce. This covers bad JSON, a duplicate key, a wrong shape or type, or a broken grammar on a read field. The cause is a sender defect or a sender that is not Grafana.
- **422:** a Notification that real Grafana could send, which v1 cannot represent. **This is lost real data.** A parser code that covers any Go-emittable cause is 422 (critic 6).
- **500:** this unit's own invariant broke.

Because phase 1 precedes phase 2 (D11), a 422 is only ever returned for a body that passed every 400-class check.

| Code | Class | Trigger | Summary fields set |
| --- | --- | --- | --- |
| `ingress_too_large` | 413 | `len(body) > 262,144`, or `oversize_refusal(declared_length)` | `body_bytes` only |
| `ingress_json_invalid` | 400 | `json_syntax` (including an empty body), `json_encoding` (invalid UTF-8, BOM), `json_depth`, `json_duplicate_key` at any depth | + `body_digest` |
| `ingress_json_unsupported` | 422 | `json_unicode` (a NUL, which Go emits as `\u0000`, or a lone surrogate); `json_number` (an integer above 2^53-1, which Go prints for integral floats below 1e21; a lexeme over 32 characters; overflow; `NaN`/`Infinity`); `json_array_too_long` (over 256 alerts) | + `body_digest`; no group and no members, because nothing was parsed |
| `ingress_shape` | 400 | the root is not an object; `alerts` is absent, not an array or empty; an element is not an object | + a group when S5 passed |
| `ingress_group_key` | 400 | `groupKey` is absent, not a string, or empty | + `body_digest` |
| `ingress_truncated` | 400 | `truncatedAlerts` is present, not `null`, and not an int in 0..2^31-1 | + one group |
| `ingress_fingerprint` | 400 | absent, not a string, or outside the grammar | + one group |
| `ingress_status` | 400 | not exactly `firing` or `resolved` | + one group |
| `ingress_values` | 400 | `values` is not an object or `null`; a value is a bool, string, array or object | + one group |
| `ingress_duplicate_fingerprint` | 400 | two members share a Fingerprint | + one group |
| `ingress_group_key_unsupported` | 422 | `groupKey` is not printable ASCII (for example a non-ASCII folder name), or is over 1,024 characters | + `refused_group`, `alerts`, `resolved`, `members`, `members_omitted` |
| `ingress_ref_id_unsupported` | 422 | a refId outside the grammar (for example a renamed query, `"Query 1"`) | + `source_group` and the four member fields |
| `ingress_too_many_alerts` | 422 | more than 32 members | same |
| `ingress_too_many_values` | 422 | more than 64 values in total | same |
| `ingress_record_too_large` | 422 | canonical record over 4,096 B | same |
| `ingress_divergence` | 500 | `json_argument`, `json_too_large`, `json_type` or `json_string_too_long` (each unreachable by construction); a `JSONPolicyError` from `source_group_digest`, `canonical_number` or `validate_source`; a `SourceError` from `canonical_number`; a non-size `SourceError` from `validate_source` | as far as reached |

`JSON_REFUSAL_CODES` maps all 11 `JSON_ERROR_CODES` members; test I8 fails if `forwarder_json` ever adds a code without a decision here. `ingress_argument` is raised, never returned, and has no class.

**Why 4xx for 422-class refusals, if Grafana does not retry them within a flush** (the brief's premise, not probed):
- A 2xx would claim acknowledgement without an admission (ADR12 L27, spec L193-196).
- A 5xx puts a deterministic refusal into Grafana's retry path and looks exactly like the journal's retryable 503 backpressure.
- 422 is honest, and every member-level 422 names the lost members, Resolved first. Spec L300-301 forbids silent discards for held Notifications, and plan L1425 requires refusals to be visible.
- A refusal changes no journal state. "Omission is never Resolved" still holds; the loss is only the missing update.
- The integration may still choose "record durably, hold, answer 202" (Deferred 1). Because the stored summary carries no class, either choice keeps it true.

**The resend hypothesis** (robust, from memory of Alertmanager's dispatcher; not probed). Alertmanager writes its notification log only after a successful notify, and keeps resolved alerts in the aggregation group until a notify succeeds. If Grafana's embedded Alertmanager does the same, a deterministic refusal is re-sent every `group_interval` (10 s here), each time re-rendered with new values and `message`, until the group changes. The Resolved never gets through either way. Two consequences:
- the durable summary needs a flood policy keyed without `body_digest` (D12, Deferred 3);
- the integration unit must choose between "422 and stay refused" and "record durably, hold dispatch, answer 202" (Deferred 1).

**Response bodies** (for the integration unit): the code only, ASCII, never `str(error)`.

## Bounds

| Quantity | Bound | Source | Captured maximum |
| --- | --- | --- | --- |
| body | 262,144 B, checked before hashing | D2, plan Deferred 1 | 9,333 B |
| any decoded string or key | 262,144 B (the body bound) | D1 | `message` 3,373 B |
| depth, array items, lexeme, integer | 16; 256; 32 characters; 2^53-1 | `parse_json` | 4; 4 alerts; 20 characters; 55,042,048 |
| members | 32 | `MAX_ALERTS` | 4 |
| values in total | 64 | `MAX_VALUES` | 8 |
| canonical record | 4,096 B | `MAX_SOURCE_RECORD_BYTES` | 800 B |
| `groupKey` | printable ASCII, 1..1,024 | `source_group_digest` | 83 B |
| fingerprint / refId | 64 / 32 characters of `[A-Za-z0-9._-]` | journal grammars | 16 / 1 |
| `startsAt` kept | ≤ 30 characters, Z grammar with ASCII digits, calendar-valid | D5 | 20 characters |
| `starts_at_dropped` | ≤ 32 Fingerprints | D5 | 0 |
| refusal summary | ≤ 32 members; ≤ 4,096 B enforced; 2,866 B measured worst (256 Resolved members with 64-character Fingerprints, an unsupported `groupKey`, `body_bytes` 262,144; critic 10) | D8 | - |
| oversize `body_bytes` | 262,145..2^53-1 | `oversize_refusal` | - |
| work | no input-dependent recursion; depth prescanned; lexemes bounded before `int()`/`float()` | `parse_json` | worst 256 KiB shape about 107 ms (87,000 small objects); printed, never asserted |

## Invariants

Each invariant has a test, except N12 (b), which is an obligation on the integration unit.
- **N1. Pure.** No clock, randomness, filesystem, environment, network, logging or global state; imports are AST-allowlisted (I12). Equal bytes give equal outcomes, and a call leaves module state unchanged, for admitted and refused inputs alike (I13).
- **N2. Total.** For any `bytes`, `sanitize_notification` returns an outcome with exactly one of `source` and `refusal` set, and raises nothing. This holds even if a wrapped call raises either exception class (I5). For any other type it raises only `ingress_argument` (I11, X10).
- **N3. Admitted means valid.** `validate_source(source) == source`, `source.provenance == HTTP_PROVENANCE`, and `source.body_digest == sha256(b"rj.body.v1\x00" + body)` over the exact bytes, so `admit` can never raise `source_invalid` for an ingress-built record (C1, C10).
- **N4. Allowlist only.** Changing, deleting or adding any field outside the read set, within the parser's rules, leaves the record unchanged apart from `body_digest` (C8).
- **N5. Order-free.** Permuting `alerts` or any `values` object changes only `body_digest` (C7).
- **N6. Whole or nothing.** An admitted record has exactly one member per body element. A bound breach refuses the whole Notification; nothing is split, truncated, merged, dropped, or stripped of provenance (plan P1 (ii); X3, X4).
- **N7. Deterministic precedence.** The first failing step S0-S15 decides the code (I6).
- **N8. Closed codes.** Every refusal code is in `INGRESS_REFUSAL_CODES`; `INGRESS_HTTP_STATUS` gives each exactly one proposed class in {400, 413, 422, 500}; `JSON_REFUSAL_CODES` is total (I8).
- **N9. Custody.** Refusal fields are codes, ints, hex64, `None`, or `(fingerprint, status)` pairs. Admitted and summarized strings are limited to the journal's grammars. Grammar-valid Fingerprints and refIds are caller-chosen but grammar-bounded, and appear verbatim. Anything else the caller sends (ignored fields, a non-ASCII `groupKey`, a malformed `startsAt`, grammar-invalid read values) never appears in `repr` of the outcome, in `refusal_to_json`, or in exception `args`, `__cause__` or `__context__` (I10).
- **N10. Minimal normalization.** Only Go zero time and absence become `None` unreported; any other dropped `startsAt` is named in `starts_at_dropped`; numbers change only through `canonical_number` (I3, I4).
- **N11. Plan-faithful absence.** An absent or `null` `truncatedAlerts`, `values` or `startsAt` gives `None` and never a refusal (I3, I4).
- **N12. Refusals are inert.** (a) Producing a refusal has no side effect (N1; I13 includes refused inputs). (b) The integration must not call `admit` for a refusal (Deferred 1; not testable here).
- **N13. Legacy-compatible subset.** Every admitted body passes `notification.validate_notification` (C9).
- **N14. Forwarder and journal unchanged.** Every existing `parse_json` call omits the keyword and behaves exactly as at baseline (S1, S6, and every existing test green).
- **N15. 400 before 422.** A 422-class code is returned only for a body that passes every 400-class check, and every member-level 422 names its members (I6, X12).
- **N16. The summary is self-consistent.** Everything `sanitize_notification` and `oversize_refusal` return passes `refusal_to_json`, and every summary encodes in at most 4,096 canonical bytes (I9, X12).

## Existing-module changes and test impact

| File | Change | Test impact |
| --- | --- | --- |
| `forwarder_json.py` | Additive keyword, below | Existing tests unchanged. Probe s7 on a patched copy: the six `parse_json`-dependent files (forwarder_json, forwarder_json_adversarial, forwarder_routes, forwarder_routes_adversarial, journal_source, journal_records) gave 702 passed. The full suite gave 3,990 passed and 38 skipped. The 22 failures were all in `test_container.py` and came from the copy not being a git checkout (missing `.env.example`, `.dockerignore`, git): 3,990 + 22 = the baseline 4,012 |
| `docs/recovery-journal.md` | New "Ingress" section; L271-279 edits (root) | none |
| `execution-backlog.md`, `issues/37-…md` | Unit-16 entry and progress note (root) | none |

**The `forwarder_json` change, exactly:**
- `_check_string(value, *, ascii_only, too_long_code, max_bytes: int = MAX_JSON_STRING_BYTES)` compares against `max_bytes`. `_canonicalize` keeps calling it without `max_bytes`, so `canonical_json` and `tagged_digest` still cap strings at 16 KiB.
- `_postwalk(root, *, ascii_only, max_string_bytes)` passes `max_bytes=max_string_bytes` to both of its `_check_string` calls (keys and strings).
- `parse_json(data, *, max_bytes, numbers="integer", ascii_only=False, max_string_bytes=MAX_JSON_STRING_BYTES)`:
  - the argument check adds `type(max_string_bytes) is not int or not 1 <= max_string_bytes <= MAX_JSON_DOCUMENT_BYTES` → `json_argument`, before any decoding;
  - it passes the value to `_postwalk`;
  - its docstring gains one sentence: "`max_string_bytes` bounds each decoded key and string in UTF-8 bytes; only the Receiver's raw-ingress sanitizer raises it."
- The error discipline, the import allowlist, the NUL and surrogate ban, and every other limit are unchanged.
- The default binds the constant at definition time. No test monkeypatches `MAX_JSON_STRING_BYTES`, and it is never reassigned.

The probe diff is in `u16-design/synth-probe/forwarder_json.patch` (17 lines added, 6 removed).

**No change** to `journal_source.py`, `journal_records.py`, `journal_store.py`, `journal_reducer.py`, `recovery_journal.py`, `receiver.py`, `notification.py`, `forwarder_routes.py`, `pyproject.toml`, or any existing test file.

## Ownership and validation

The two owners work on disjoint files. The tester starts from this plan's API signatures and does not wait for the implementation. Tests never write repository files. Timing cases print their measurements, or use pytest's `record_property`, and root transcribes them (critic 11).

**Implementer I** owns `grafana_jsm_sandbox/journal_ingress.py`, the `forwarder_json.py` change, `tests/test_journal_ingress.py` (unit) and `tests/test_forwarder_json_string_cap.py`.
- **I1.** The minimal admissible body gives `truncated_alerts`, `values` and `starts_at` all `None`, `starts_at_dropped == ()`, and `provenance == HTTP_PROVENANCE`.
- **I2.** `body_digest` known answers: `b""` gives `5f669e48d59a42bd8cfd8f738d4498286a8241edbdee93abfc679eb0b3793fb7`, and each result equals an independent `hashlib.sha256(b"rj.body.v1\x00" + body)`.
- **I3.** Mapping table over payment line 1 mutations:
  - `values` absent, `null`, `{}` and `{"A": null}`;
  - `100.0` → `"100"`, `1e-7` → `"1e-07"`, `-0` → `"0"`, `1e-400` → `"0"`, 2^53-1 exact;
  - `{"C":…,"A":…,"B":…}` sorted;
  - `truncatedAlerts` absent, `null`, 7 and 2^31-1;
  - fingerprint `fixture-w1` (f31 L111);
  - `imageURL` and an unknown top-level object ignored.
- **I4.** `startsAt` table:
  - zero time → `None`, unreported; `.123456789Z` verbatim; `0001-01-01T00:00:01Z` kept; absent or `null` → `None`, unreported;
  - `+02:00`, `-05:30`, `2026-02-30`, `…T23:59:60Z`, year `0000`, `"yesterday"`, `5` and a 100,000-character string → `None`, with the member's Fingerprint in `starts_at_dropped`;
  - three members with two dropped times give exactly those two Fingerprints, sorted;
  - none refuses, and none changes `dedupe_key`.
- **I5.** Refusal table: one minimal mutation per code, 16 rows, each asserting the code, `body_bytes`, and exactly which summary fields are set (the code table). The set of exercised codes equals `INGRESS_REFUSAL_CODES`. `ingress_divergence` is reached by monkeypatching, and each of these rows returns an outcome rather than raising (critic 8):
  - `validate_source` raising `SourceError("source_order")`, and separately `JSONPolicyError("json_number")`;
  - `canonical_number` raising `SourceError`, and separately `JSONPolicyError`;
  - `source_group_digest` raising `JSONPolicyError`.
- **I6.** Precedence (rewritten for D11):
  - a bad status on any member beats a bad refId on any member: member 1 with `"Query 1"` and member 2 with status `"BOGUS"` gives `ingress_status`, and so does the reverse order;
  - a mixed `values` object gives `ingress_values` whatever the key order (`{"Query 1":1,"b":"x"}` and `{"Query 1":1,"A":"x"}`);
  - a non-ASCII `groupKey` with a bad status gives `ingress_status` carrying `refused_group`;
  - an empty `groupKey` with a bad status gives `ingress_group_key`;
  - `truncatedAlerts -1` with a bad status gives `ingress_truncated`;
  - 40 members with the 40th status bad gives `ingress_status`;
  - a non-ASCII `groupKey` with a bad refId and 40 members gives `ingress_group_key_unsupported`; a bad refId with 40 members gives `ingress_ref_id_unsupported`; 40 members with 120 values gives `ingress_too_many_alerts`. Each has `alerts == 40`, 32 members listed and 8 omitted;
  - `version "2"`, top-level `status "x"` and `title 7` are admitted.
- **I7.** Grammar parity with `validate_source`, over a table of values:
  - Fingerprints and refIds: ASCII, non-ASCII digits, empty, 64/65 and 32/33 characters, a space;
  - `startsAt` (critic 8): Arabic-Indic digits, 30 against 31 characters, and a 9 against 10 digit fraction.

  Whatever ingress keeps passes `validate_source`, and whatever it refuses or drops `validate_source` would reject. No row gives `ingress_divergence`.
- **I8.** Closed sets:
  - `set(INGRESS_HTTP_STATUS) == INGRESS_REFUSAL_CODES`, with classes in {400, 413, 422, 500};
  - `MEMBER_CODES` equals the five phase-2 codes, and all are 422;
  - `set(JSON_REFUSAL_CODES) == forwarder_json.JSON_ERROR_CODES`, with values in the refusal codes; `json_unicode` maps to a 422 code;
  - `IngressError(c).args == (c,)`.
- **I9.** Refusal summary (critic 2, 3, 7, 10):
  - `refusal_to_json` has exactly the nine keys, no `http_status`, and is canonical ASCII;
  - with 32 firing members and one Resolved, the Resolved member is listed first and a firing one is omitted;
  - the worst case, 256 Resolved members with 64-character Fingerprints, an unsupported `groupKey` and `body_bytes` 262,144, is at most 3,072 B (2,866 B measured);
  - forged instances each raise `ingress_argument` with no cause or context. The cases (16 in probe s8):
    - `body_bytes` of 2^60 or `True`;
    - `alerts` of `None` with members, `alerts` 257, or `resolved > alerts`;
    - members unsorted, with a duplicate Fingerprint, or with a space in a Fingerprint;
    - an inconsistent `members_omitted`, or a listed Resolved count that does not match `resolved`;
    - members on `ingress_json_invalid`, or a group on it;
    - both groups set;
    - a digest on `ingress_too_large`, or a small `body_bytes` on it;
    - missing counts on `ingress_too_many_alerts`.
- **I10.** Custody, split (critic 5):
  - (a) the grammar-invalid canaries `CANARY 7f3a` (with a space) and `CANARY-7f3a/` are placed in turn in a Fingerprint and a refId. `CANARY-7f3a` is placed in a status, `message`, `title`, labels, annotations, a non-ASCII `groupKey` and `startsAt`. No canary appears in `repr(outcome)`, `refusal_to_json` or error args (9 bodies, 0 leaks in probe s8);
  - (b) a grammar-valid `CANARY-7f3a` as Fingerprint and refId is admitted verbatim. This pins N9's "caller-chosen but grammar-bounded".
- **I11.** Arguments: `str`, `bytearray`, `memoryview` and `None` raise `ingress_argument` from both `sanitize_notification` and `body_digest`, with `args == (code,)` and no cause or context.
- **I12.** AST checks:
  - the exact import allowlist above;
  - `except` bodies contain only `Assign`, `AnnAssign` or `Pass`, and no `Raise` inside a handler;
  - no `now`, `utcnow` or `today` calls; no `open`, `print` or `logging`;
  - `__all__` equals the public API.
- **I13.** Determinism and inertness: two calls on each golden input and on one input per refusal code give equal outcomes. Module globals are unchanged after every call.
- **I14.** `oversize_refusal`:
  - 262,145 and 2^53-1 give the fixed summary;
  - 262,144, 2^53, `True`, `"300000"` and -1 raise `ingress_argument`;
  - `sanitize_notification` of a 262,145-byte body equals `oversize_refusal(262_145)`.

`tests/test_forwarder_json_string_cap.py`:
- **S1.** The default is unchanged. Without the keyword, a 16,384-byte string and key are accepted and 16,385 bytes give `json_string_too_long`. Passing `MAX_JSON_STRING_BYTES` explicitly gives identical results.
- **S2.** A raised cap: `max_string_bytes=262_144` accepts a 16,385-byte and a 200,000-byte string and key. `max_string_bytes=20_000` refuses a 20,001-byte string in a 1 MiB document.
- **S3.** Argument validation: 0, -1, 1,048,577, `True`, `1.0`, `"16384"` and `None` give `json_argument`, and do so even for undecodable bytes (the check runs first).
- **S4.** A raised cap changes nothing else: NUL, lone surrogate, `ascii_only`, depth, the array cap, duplicate keys and numbers still refuse.
- **S5.** `canonical_json` and `tagged_digest` still refuse a 16,385-byte string.
- **S6.** AST over `grafana_jsm_sandbox/*.py` (critic 13):
  - every call to `parse_json` that passes `max_string_bytes` is in `journal_ingress.py`, and there is exactly one;
  - no `parse_json` call has a `**` argument;
  - every reference to `parse_json` outside its definition is the callee of a call, so it is never passed to `functools.partial` or any other function, assigned or returned;
  - no import aliases it (`as`);
  - inside `forwarder_json.py`, the keyword reaches only `_postwalk`.

**Tester T** owns `tests/test_journal_ingress_corpus.py` (it defines `wire()`, `capture_rows()` and `grafana_group()`) and `tests/test_journal_ingress_adversarial.py` (which imports those three helpers).
- **C1.** All 115 captures, parametrized by `file:line`:
  - `len(wire(body)) == raw_len`;
  - admitted, with `starts_at_dropped == ()`;
  - `validate_source(source) == source`;
  - equal to an oracle projection built from plain `json`: floats through `repr`, integers through `str`, zero time as `None`;
  - `len(source.alerts) == n_alerts`, and `truncated_alerts` equals the body's;
  - `body_digest` equals an independent sha256.
- **C2.** Census pin, so a changed capture fails loudly: 115 admitted (3, 23, 63 and 26 per file); 168 members (149 firing, 19 resolved); at most 4 alerts and 8 values; records 375-800 B, with the maximum at payment line 21; 6 distinct `groupKey`s of 63-83 B.
- **C3.** sc31 known answers: the 14 lines (payment 1, 2, 16, 18, 20, 21, 23, 24, 26; email 57, 62, 63; cart 1, 6) give sorted `(fingerprint, status, values)` equal to the sc31 text, mapped through `canonical_number`.
- **C4.** Goldens. Each value is asserted as a constant and against an independent recomputation (`json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True)` plus sha256 with the tag). `source_digest` and `dedupe_key` come from the committed `journal_source` functions (probe s2; the critic recomputed all six with no repo import):

  | Input | `body_digest` | `source_group` | `source_digest` | `dedupe_key` |
  | --- | --- | --- | --- | --- |
  | payment 1 (2,985 B) | `0dd74a18eb42deb3bcbdcda622b156df45c85021550cff705a672e626f528da4` | `5deaf914a2a751fefe64e9b9077fdadad2f5fe11c224ba5451d6d66bb6c7876e` | `f346b9f748cae4aa07850b2b28916197174af887bcec71eff5629a741a021290` | `b4f1f3da5cc53679caca4f1632c891e15d415437514bbaa4c9341d4526680e82` |
  | payment 16 (7,169 B; 3 alerts) | `db9eea9713d51f6eb11f3a029fd496aa37949124a9dced0308a2e5d96d193157` | CG1 | `1637469fe9cd721ee9b61f382cdd7b89a3e907319afcd48551b67edc80ba7a66` | `94dc7ed163d2f5a206e4af81d7d1ba21ac2a7edd24bd450059cf0e1059c07709` |
  | payment 21 (9,333 B; 4 resolved) | `cd2f543c48a81816a7d4fb4cbafdff69df45c94cce0b5ff54056a2a20e1839ea` | `9d37267f6830d441f2c6ce82698704b397a29c16eb135973907fa2fa38045ce4` | `f28976b66615201a67ca06a8c1845be6a80d7c3702befc2f7ee045aa6c397d99` | `dffbf0e8ea48512fbe05e39cbfccd63f8a5c16b9a6844607342a3f524014fd24` |
  | email 57 (3,150 B; A/B/C) | `547b68200de70cf41fc33bec3de8ac64ec27547b9778d47f10c6966a0e106424` | `bd3c8b5e393bb0a691b49c6ac0ee7e2a2d60e035d1b73f0d7671338a97b2b2b6` | `350dcade09681a629f7e4f32acd243b3f69592e836359a2d2bf34ab762e59560` | `4f5c8754f674ed912ef635f7a024c5236c8eee346e9051e8577422f608b9f6ed` |
  | `notification-firing.json` (2,611 B) | `8384bd0bc8a9e5680014ee5389312298742b665701fc847d14b9de7a4abba5d4` | `aa57d128272b37ba89511a41b61e587aa198e2676d80f71925332c0d582bb7f8` | `6edd2da5b2d84802d63b6ab3cf663804e6e0e0f550c31f4e0c1df53f45067339` | `a99b74e0622bbf52ab6f66f38af0034e030e8b301bd0a399b97e7931f81f262d` |
  | `notification-resolved.json` (2,665 B) | `ca471928e4c96cb292cdacdbb1124846c1667b9e54f9138b152888de1b05c3cf` | legacy group | `d0b46f6b0352fbd887d8196473f833da2c473e63bc9fbd6640a4f74b8f04009f` | `107b7990e93f96f157da3e1ca394fd0697020a1d94647a7cf30d91b5fe8963f6` |

  The full canonical JSON of E1 and E2 is also pinned.
- **C5.** Legacy fixtures: all three are admitted from exact file bytes. The firing and repeat records are equal (the files are byte-identical). Their keys equal the plan goldens `a99b74e0…` and `107b7990…`, and the group is `aa57d128…`.
- **C6.** Exact-byte digest: pretty, compact, trailing-newline and leading-space forms of payment line 1 give the same members, group and key, and four distinct `body_digest`s.
- **C7.** Permutation: each of the 22 multi-alert captures, with a seeded shuffle of `alerts` and a reversal of every `values` object, gives an equal record apart from `body_digest`, and an equal `dedupe_key`.
- **C8.** Allowlist: on payment line 16, each ignored top-level key and each ignored alert key is deleted, and separately replaced by another JSON value (40 variants). Each gives the baseline record apart from `body_digest`.
- **C9.** Legacy subset: every body admitted in C1, C5, C6 and C7 passes `validate_notification`. One pinned duplicate-key body is legacy-valid and refused here.
- **C10.** Journal seam, skipped when `journal_store.no_ckpt_supported()` is false, as in `test_recovery_journal.py`. A fresh `tmp_path` journal (mode 0700) admits the sanitized firing, repeat and resolved fixtures and payment lines 1 and 2. The results are `admitted`, `suppressed`, `pending_reduced`, `admitted` and `pending_reduced` (probe s6). 14 real syncs (create 4, five admissions 2 each).
- **X1.** Body bound: payment line 1 whitespace-padded to 262,144 bytes is admitted; 262,145 bytes give `ingress_too_large` with `body_digest` `None`.
- **X2.** Ignored large strings: a 200,000-byte `message` and a 17,000-byte description are admitted. The committed default `parse_json` refuses both, which documents the option (a) difference.
- **X3.** The realistic template, from the normative generator `grafana_group(base, n, status, n_values)` (critic 9). It is copied from `u16-design/synth-probe/ceilings.py:make()`:
  - `base` is the payment line 1 body (CG1) or the line 21 body (CG2), deep-copied; its first alert is the template.
  - Member i uses service `SERVICES[i]`, where `SERVICES` is the 33 names `accounting, ad, cart, checkout, currency, email, flagd, fraud-detection, frontend, frontend-proxy, image-provider, kafka, load-generator, payment, product-catalog, quote, recommendation, shipping, valkey-cart, otel-collector, jaeger, grafana, prometheus, opensearch, llm, react-native-app, ts-web, python-svc, go-svc, dotnet-svc, java-svc, ruby-svc, rust-svc`.
  - That service replaces the `service` and `service_name` labels, and the Fingerprint is `sha256(service.encode()).hexdigest()[:16]`.
  - Values are `A = random.Random(n).random() / 7`, drawn in member order from one generator per body, then `B` (and `C` when `n_values == 3`) as 1 when firing and 0 when resolved.
  - `endsAt` is Go zero time when firing and `2026-09-17T22:05:20Z` when resolved. `silenceURL` has one matcher per non-`alertname`/`grafana_folder` label in sorted order, and `valueString` is `[ var='K' labels={service=S, service_name=S} value=V ]` joined by `, `.
  - `commonLabels` is the labels every member shares. `message` is `**Firing**\n\n` or `**Resolved**\n\n` followed by the per-member sections, joined by `\n`: `Value: K=V, …`, `Labels:` lines ` - k = v`, `Annotations:` lines, `Source: <generatorURL>` and `Silence: <silenceURL>`, as captured.

  The assertions, both measured and pinned:
  - two values, CG1 and CG2, firing and resolved: the 19-alert `message` is at most 16,384 B and the 20-alert one is larger (15,733-15,963 against 16,576-16,818 B pinned); 20 is admitted here and refused by the default parser;
  - the admitted ceiling equals the largest n whose record, projected without bounds, is at most 4,096 B, and equals the pinned 28. 29 gives `ingress_record_too_large` with `alerts == 29`;
  - 33 give `ingress_too_many_alerts` with 32 members and 1 omitted;
  - three values: 21 are admitted; 22 give `ingress_too_many_values` with `alerts == 22`.
- **X4.** Member bounds: 32 value-free members are admitted and 33 refused; 256 minimal members give `ingress_too_many_alerts` (`alerts == 256`, 32 listed, 224 omitted); 257 give `ingress_json_unsupported` with no counts. 64 values are admitted and 65 refused. 28 clones of payment line 1 are admitted and 29 refused.
- **X5.** Grammar edges: fingerprint 64/65; refId 32/33 and `"Query 1"`; `groupKey` 1,024/1,025; a non-ASCII `groupKey`.
- **X6.** Duplicates: a duplicate key at the root, inside an alert, and inside ignored `labels` gives `ingress_json_invalid`. A duplicate Fingerprint at non-adjacent positions gives `ingress_duplicate_fingerprint`.
- **X7.** Numbers: `NaN`, `Infinity`, `-Infinity`, `1e400`, 2^53 and a 33-character lexeme give `ingress_json_unsupported`. 2^53-1 and `1e-400` are admitted.
- **X8.** Nesting: depth 16 in an ignored field is admitted and 17 refused. 262,144 bytes of `[` are refused; the time is printed.
- **X9.** Encoding and syntax:
  - a BOM, invalid UTF-8 inside an ignored string, an empty body, whitespace only, trailing garbage, and a top-level array or scalar give `ingress_json_invalid` or `ingress_shape`;
  - a NUL escape and a lone-surrogate escape in `message` give `ingress_json_unsupported`.
- **X10.** Totality fuzz, seed-fixed: 2,000 mutations of five captures (byte flips, truncations, insertions, deletions) plus 200 random byte strings. Every call returns exactly one of source and refusal. Every admitted source passes `validate_source`, and every refusal passes `refusal_to_json` (probe s5: 2,200 outcomes, none raised; probe s8: 1,444 fuzz refusals, all valid summaries).
- **X11.** Work at the bound: 256 KiB of small objects, many keys, escapes, numbers, and a 250,000-byte `message`. Each returns an outcome. Times are printed, never asserted (at most about 107 ms measured).
- **X12.** Resends and members (critic 1, 4):
  - two re-renders of one non-ASCII-folder group (E8), with different members, values and `message`, give different `body_digest`s and an equal `refused_group`;
  - for every phase-2 refusal produced in X3-X5, `alerts` equals the body's member count, `members` follows the Resolved-first order, and `refusal_to_json` succeeds (probe s8: 58 generator refusals, all valid).

**Root** owns:
- the baseline, measured before any edit: plain `pytest -q`, expecting 4012 passed and 38 skipped;
- `docs/recovery-journal.md` (next section), the backlog entry and the issue-37 note;
- the focused command, with its wall time recorded:
  `pytest -q tests/test_journal_ingress.py tests/test_forwarder_json_string_cap.py tests/test_journal_ingress_corpus.py tests/test_journal_ingress_adversarial.py tests/test_forwarder_json.py tests/test_forwarder_json_adversarial.py tests/test_forwarder_routes.py tests/test_forwarder_routes_adversarial.py tests/test_journal_source.py tests/test_journal_records.py tests/test_receiver.py tests/test_replay.py`;
- the full suite, `pytest -q`: 0 failures, and 38 skips plus none new (C10 runs on 3.13);
- `ruff check` on the new and changed files, and `git diff --check`;
- the diff check (critic 11). Among existing tracked paths, `git diff --stat` touches only `grafana_jsm_sandbox/forwarder_json.py`, `docs/recovery-journal.md`, `.scratch/many-alerts-one-incident/execution-backlog.md` and `.scratch/many-alerts-one-incident/issues/37-run-recovery-and-admission-specification.md`. `git status --porcelain` shows only those, this unit's new files ("Unit boundary" items 1, 3 and 5) and the four protected paths, which stay unchanged (hashed before and after). The tree is still clean after a second full-suite run;
- `reviews/journal-ingress/validation.json`, with SHA-256 hashes of the sources, tests, docs and both suite logs, plus the transcribed timings.

An independent reviewer binds the final hashes before the single local commit. The review must check `forwarder_json.py` against its baseline diff line by line. There is no push.

## Documentation (`docs/recovery-journal.md`, root)

- **Append a section "Ingress"** after "Bounds":
  - what `journal_ingress.sanitize_notification` does, and that it is pure and not yet called by the Receiver;
  - the read set, and that every other field is parsed within the house parser's rules and dropped;
  - the mapping rules: absence, `startsAt` and `starts_at_dropped`, numbers, sorting, the digest over exact bytes, `HTTP_PROVENANCE`;
  - the two phases (400-class before 422-class);
  - the bounds, and the ceiling (28 two-value alerts, 21 three-value, 32 value-free);
  - the code table, with the classes marked as a proposal for the seam; response bodies must carry the code only;
  - the refusal summary: nine keys, Resolved first, `refused_group`, no HTTP status, and not persisted; `oversize_refusal` for header-only refusals;
  - the `max_string_bytes` keyword and why ingress alone raises it;
  - non-claims: Grafana's real wire bytes, retry and resend behaviour, Receiver integration.
- **L271-273.** Add the four new test files to the focused command.
- **L275-279.** Replace "No Receiver integration, raw Notification ingress, dispatch, …" with "No Receiver integration, ingress refusal persistence, dispatch, …", and add "Grafana's retry and resend behaviour after a refusal" to the not-qualified list.

## Proposals requiring ratification

Numbered U16-P1 to U16-P18 to avoid clashing with the plan's P1-P27 and R1-R7.
- **U16-P1. Parser strategy (D1).** The additive `max_string_bytes` keyword on the shared `parse_json`, raised to the body bound by ingress only. *Alternative:* (a), with its 19-alert ceiling.
- **U16-P2. Body bound (D2):** 262,144 bytes. *Alternative:* robust's 1 MiB.
- **U16-P3. Read set (D3).** `version` and top-level `status` are not read, and unknown fields are ignored. *Alternatives:* strict's `version == "1"` gate and status witness.
- **U16-P4. Absence (D4).** Absent or `null` `truncatedAlerts` and `values` give `None`; a `null` value is kept; a present wrong type is refused with 400.
- **U16-P5. `startsAt` (D5).** It never refuses. Only the exact Go zero time and absence are silently `None`; every other unkept value names its Fingerprint in `starts_at_dropped`, which is returned, not persisted. *Alternative:* convert offsets to Z (robust U6).
- **U16-P6. Unrepresentable Grafana input is refused with 422 and named members (D6).** *Alternatives,* each an ingress-only loosening: digest-mapped `groupKey` and refIds, and big integers as float64 (robust U3-U5).
- **U16-P7. P1 (ii) as whole-Notification 422 refusals (D7)**, with no `starts_at` fallback.
- **U16-P8. The 16 codes and the proposed class rule** (400 / 413 / 422 / 500). A parser code with any Go-emittable cause is 422, so `json_unicode` is 422. Response bodies carry the code only, and the class is never persisted.
- **U16-P9. The refusal summary shape (D8).** Nine keys, no HTTP status, at most 32 members listed Resolved first, the cross-field rules of `refusal_to_json`, and a 4,096-byte bound.
- **U16-P10. `starts_at_dropped`** as a tuple of Fingerprints on the outcome. It replaces revision 1's `INGRESS_NOTE_CODES`.
- **U16-P11.** Duplicate keys (anywhere) and duplicate Fingerprints are refused with 400, never merged.
- **U16-P12. Provenance (D9).** Always `HTTP_PROVENANCE`; `capture` is deferred.
- **U16-P13. `body_digest` (D10)** is unkeyed over the exact bytes, and uncomputed for an oversize body. Plan P15's confirmation-oracle non-claim stands; it applies equally to `refused_group`.
- **U16-P14. Test encoding.** Capture bodies are reconstructed with the Go-style encoder (lowercase escapes), pinned by `raw_len`, so capture goldens pin the reconstruction. The X3 generator is normative.
- **U16-P15. Names:** `journal_ingress`, `sanitize_notification`, `oversize_refusal`, `IngressOutcome`, `IngressRefusal`, `refusal_to_json`, `IngressError`, `MEMBER_CODES`, `starts_at_dropped`, `refused_group`, the `ingress_*` codes (including `ingress_json_unsupported`), and the keyword `max_string_bytes`.
- **U16-P16. The durable refusal summary is re-deferred** to the integration unit (critic 12). Plan Deferred 1, P22 and L1425 assigned it to this unit. Until it lands, refusals exist only as return values and are invisible after the process exits.
- **U16-P17. `refused_group` (D12)** with the tag `rj.refused-group.v1`, and the flood key `(code, source_group or refused_group or None)` for Deferred 3.
- **U16-P18. Two-phase precedence (D11).** Every 400-class check over every member runs before any 422-class check.

## Deferred

1. **Receiver integration** (plan Deferred 2).
   - Refuse a missing or invalid `Content-Length`, or a chunked body, before reading. For a declared length above 262,144, answer from `oversize_refusal(declared_length)` before reading. Otherwise read exactly the declared bytes and pass them unmodified.
   - Replace `validate_notification`, whose 400 texts echo caller data (notification.py L27, L41; receiver.py L143).
   - Choose the response class at the seam (for example from `INGRESS_HTTP_STATUS[code]`), with the code as the body.
   - `admit` an admitted source, then 202. Never `admit` a refusal (N12 b). Map `JournalError` to 503 with `Retry-After`.
   - Count refusals and dropped `startsAt` Fingerprints per boot for health.
   - Choose the 422 policy: "422 and stay refused", or "record durably, hold dispatch, answer 202" (robust U10). Decide after the resend behaviour is qualified.
   - It must follow, or ship with, the operator unit (plan P20).
2. **Body spool** keyed by `body_digest`, written and synced before the admission commit. It is content-addressed: the byte-identical legacy firing and repeat share an entry.
3. **Durable refusal summary** (U16-P16).
   - An `ingress_refusal` record type whose data is `refusal_to_json(r)`, with its R3 registry entry, its reducer transition and its capacity charge (R1).
   - A flood policy: at most one record per `(code, source_group or refused_group or None)` per generation, and later ones counted per boot (as plan P22). Re-renders every 10 s change `body_digest` but not this key.
   - Refusals on `/health`.
4. **The `capture` provenance kind**, with the f31 replay harness. It is a `journal_source` validator change and bumps the admission `schema_version` (R1).
5. **Loosening candidates**, each ingress-only and additive:
   - converting offset `startsAt` values to Z;
   - digest-mapped non-ASCII or oversize `groupKey`s, and digest-mapped refIds;
   - integers above 2^53-1 through float64. This needs a further `parse_json` keyword or an integer-lexeme `JSONDecimal`;
   - separating NUL from lone surrogates, which needs a parser change.

   Raising the 32 / 64 / 4 KiB bounds is a journal change that needs a new `schema_version`.
6. **Grafana-side mitigations**, which need a live probe: a contact-point maximum-alerts setting, so Grafana truncates and reports `truncatedAlerts` instead of the Receiver refusing, and a short custom `message` template.
7. **Operator actions**, including reconciling a lost Resolved from the summary's members.
8. **Persisting `starts_at_dropped`** in the admission record, if ratified. It is a journal schema change.
9. **Retiring `notification.py`** once the Receiver uses this module.

## Not qualified by this unit

- **Grafana's real wire bytes.** Captures hold parsed bodies. The reconstruction matches `raw_len` in 115 of 115 rows, which is length evidence, not byte identity. The escape case is unpinned by the captures, which contain no `<` or `>`. Float formatting below 1e-6 or at or above 1e21 never occurs in the captures.
- **Grafana behaviour, none probed:**
  - whether a 4xx is retried within a flush (the brief's premise), and whether it is re-sent across flushes (the resend hypothesis);
  - whether values can be non-finite, or integral at 2^53 or above;
  - the refId charset;
  - non-ASCII `groupKey` quoting;
  - `startsAt` offsets under a non-UTC time zone;
  - maximum-alerts truncation and which alerts it keeps;
  - other Grafana versions, including the unpinned `otel-lgtm:latest`.
- **Groups above 4 alerts.** The 19-33 alert results come from a synthetic generator built from captured shapes, not from a real large group.
- **HTTP-level behaviour**: `Content-Length`, chunked bodies, concurrency, and connection handling after a 413.
- **Durability and visibility of refusals**, and any operator workflow for a lost Resolved.
- **Venue performance.** Timings come from the development Mac.
- **Every U16 proposal.**

## Residual risks the reviewers must accept

- **Refused real Notifications.** These inputs are refused, and each refusal loses the update to OPS until the integration and operator units exist:
  - groups of more than 28 two-value or 21 three-value alerts;
  - a non-ASCII or oversize `groupKey`;
  - a renamed refId;
  - a `values` integer at or above 2^53;
  - a NUL in any string;
  - a body over 256 KiB.

  Member-level refusals name up to 32 members, Resolved first. The parser-level ones (`ingress_json_unsupported`, `ingress_too_large`) name none. Under the resend hypothesis a refusal may repeat every 10 s. Until Deferred 3 lands, the summary exists only as a return value (U16-P16).
- **A change to a shared security module.** `forwarder_json` gains a parameter. A future Forwarder or journal caller could pass it; test S6 pins the call sites and rejects splats, `partial` and aliases, but review must still re-check them.
- **`startsAt` leniency.** A malformed or offset time is dropped from the record. Only `starts_at_dropped`, which is returned but not persisted, distinguishes it from "not supplied".
- **`version` not read.** A future Grafana schema that keeps these field names but changes their meaning would be read as v1.
- **The inherited parser's bans** apply to ignored fields as well, so a Notification can be refused over data the record would never hold. The bans are NUL, lone surrogates, integers above 2^53-1, over-long lexemes and more than 256 array items. The mixed codes are conservatively 422, so a non-Grafana lone surrogate is also classed as lost real data.
- **Unkeyed digests.** `body_digest`, `source_group` and `refused_group` confirm a guessed body or `groupKey` (P15).
- **Grammar duplication.** Ingress re-states three journal grammars; test I7 keeps them equal.
- **No production effect yet.** The running Receiver still uses `validate_notification` and acknowledges without a durable record.

## Critic issues resolved (revision 2)

| Critic issue | Resolution |
| --- | --- |
| 1 (high). Member-level 422s name no members; a 422 can hide a provable 400 | **Accepted.** Two phases (D11, S4-S15, U16-P18). Every 400-class check over every member precedes `groupKey` support, refId grammar and P1 (ii). Every phase-2 refusal carries `alerts`, `resolved`, `members` and `members_omitted` (`MEMBER_CODES`); `ingress_json_unsupported` is the only 422 without members, as stated. I6 is rewritten: a bad status anywhere beats a bad refId anywhere, and mixed `values` give 400 in any key order. The code table is updated. Probe s8 reproduces each of the critic's cases |
| 2 (medium). A truncated member list can omit the Resolved members | **Accepted.** Resolved first, then Fingerprint, truncated after ordering (D8). Updated in the API comment, I9 and E7; the 32 firing plus 1 Resolved row was added |
| 3 (medium). `http_status` frozen into the durable summary | **Accepted.** `http_status` is removed from `IngressRefusal` and `refusal_to_json` (nine keys, with `refused_group` added). `INGRESS_HTTP_STATUS` is a proposal the seam reads (D8; Deferred 1) |
| 4 (medium). The flood key cannot throttle looping refusals | **Accepted.** `refused_group` (D12, U16-P17), computed with `hashlib` because `tagged_digest` rejects these keys. Every refusal after S5 carries exactly one group. The flood key is `(code, source_group or refused_group or None)`. X12 pins its stability across re-renders |
| 5 (medium). I10 cannot pass for grammar-valid canaries | **Accepted.** I10 is split: (a) grammar-invalid canaries (`CANARY 7f3a`, `CANARY-7f3a/`) and canaries in ignored fields never appear; (b) grammar-valid ones appear verbatim. N9 is reworded to "caller-chosen but grammar-bounded" |
| 6 (medium). `json_unicode` breaks the class rule | **Accepted.** `json_unicode` maps to 422 through the renamed `ingress_json_unsupported`, which also takes `json_number` and `json_array_too_long`. The rule "a parser code with any Go-emittable cause is 422" is stated once. The residual risk notes the converse cost (a lone surrogate is also 422) |
| 7 (medium). `refusal_to_json` validation incomplete; no header-only refusal | **Accepted.** Cross-field and encodability checks (API), including every check the critic listed plus the resolved-listed count, group presence per code, and a 4,096-byte canonical bound. Public `oversize_refusal(declared_length)` bounds the length to 262,145..2^53-1 and is used by S1 (I9, I14; probe s8: 16 of 16 forgeries rejected) |
| 8 (low). Totality rests on unnamed exception classes; I7 omits `startsAt` | **Accepted.** An exact exception table (Module). `(SourceError, JSONPolicyError)` → divergence, except `source_too_large`. The probe showed that revision 1's `canonical_number` handler let a `JSONPolicyError` escape; the revision-2 prototype catches it. I5 injects `JSONPolicyError` into each wrapped call; I7 gains `startsAt` rows (Arabic-Indic digits, 30 against 31 characters) |
| 9 (low). X3's boundaries depend on unpinned generator details | **Accepted.** The generator is specified in X3 and is normative (U16-P14). X3 asserts the ceiling both as a measured property (the largest n with a projected record ≤ 4,096 B) and as the pinned 28 and 21. `wire()` pins lowercase escapes |
| 10 (low). The worst-case summary size is misstated | **Accepted.** Re-measured under the new shape: 2,866 B at 256 Resolved members with 64-character Fingerprints, an unsupported `groupKey` and `body_bytes` 262,144 (Bounds, I9). The 3,072 B assertion holds, and the module enforces 4,096 |
| 11 (low). Commit contents and test side effects unspecified | **Accepted.** "In" item 5 lists the evidence files, the backlog entry and the issue-37 note, and the diff check is widened to match. Tests never write repository files; timings are printed or recorded with `record_property` and transcribed by root |
| 12 (low). An unprobed claim stated as fact; the re-deferral is not a proposal | **Accepted.** The no-retry-within-a-flush statement is now the brief's premise, grouped with the resend hypothesis (D1, "Refusal codes", "Not qualified"). U16-P16 records the re-deferral of the durable summary against plan Deferred 1, P22 and L1425 |
| 13 (low). S6 can be evaded; N12 has no test | **Accepted.** S6 rejects `**` splats, any non-callee reference to `parse_json` (so `partial` and assignment are caught) and aliased imports. N12 is split: (a) inertness, tested by I13 over refused inputs; (b) "never `admit` a refusal", an integration obligation (Deferred 1). The invariant preamble says so |
| 14 (low). `starts_at_dropped` cannot be attributed or persisted | **Accepted, first option.** `IngressOutcome.starts_at_dropped` is a sorted tuple of at most 32 Fingerprints, replacing `notes` and `INGRESS_NOTE_CODES` (D5, U16-P10). Persisting it is a journal schema change (Deferred 8) |

No issue is rejected. Two resolutions go further than the critic proposed:
- **Issue 3.** `http_status` is removed from the dataclass as well as the summary, so no in-memory value can carry a stale class.
- **Issue 7.** The summary is also bounded at 4,096 canonical bytes, and `sanitize_notification` builds its own oversize refusal through `oversize_refusal`, so the two paths cannot diverge.
