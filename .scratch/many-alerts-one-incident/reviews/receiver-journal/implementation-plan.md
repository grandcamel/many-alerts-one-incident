# Journaled Receiver front door: durable admission before the 202, visible refusals, verify-only inspect and resume at open (unit 17)

2026-09-24, revision 2 (critic pass). **Baseline:** `b931610` (unit 16). This is the seventeenth local application unit under the [approval record](../native-runtime-source-implementation-approval.json), and the third unit of the ticket-37 Receiver-owned recovery journal. Its authority is proposal step 2 (`native-runtime-source-implementation-proposal.md` L32-36), unit-15 plan Deferred 2 and 6 and P20, and unit-16 plan Deferred 1-3.

**Scope.** Source and synthetic tests only. Tests use private 0700 `tmp_path` subdirectories, real SQLite, real `F_FULLFSYNC`/`fsync`, real sockets on ephemeral ports, injected clocks and ID factories, and the committed fixtures and ticket-14 captures read-only. Out of bounds: push, provider/native/tenant calls, real credentials, C2 retries, paid experiments, deployment, Grafana provisioning, and any edit to `receiver.py`, `__main__.py`, `replay.py`, `run_spawner.py`, `notification.py`, `reset.py`, `journal_store.py`, `journal_source.py`, `journal_ingress.py`, any `forwarder_*` module, `pyproject.toml`, the container files, or any existing test file. Run the full suite before committing. Every existing test file stays byte-identical.

**Protected state.** Four dirty paths exist at baseline (re-checked 2026-09-24 with `git status --porcelain`):
- `.scratch/many-alerts-one-incident/issues/19-mcp-grafana-behind-the-sentinel.md` (modified);
- `.scratch/many-alerts-one-incident/reviews/planning-frontier-2026-09-18.md` (modified);
- `.scratch/many-alerts-one-incident/reviews/ticket-19/c2-ingestion-execution-draft.md` (untracked);
- `.scratch/many-alerts-one-incident/reviews/ticket-19/c2-ingestion-session-outcome.md` (untracked).

None of them is edited, staged or committed. Ticket 19 C2 is out of scope. `reviews/receiver-journal/panel/` (designs, judgments, probes) is working material and is not staged, as `u16-design/` was not. Staging uses explicit paths only.

**How this plan was made.** Three independent designs were judged by two judges: `design-admission-only`, `design-minimal-dispatch` and `design-operator-first` (all in `panel/`). Judge 1 scored spec fidelity and fail-closed behavior; judge 2 scored boundedness, legacy identity, testability and later-unit fit. `design-admission-only` won both, 49 and 48 of 60, and is the base. Grafts come from `design-operator-first` (resume at open, no spool deletion, a separate extension digest, a `rule` literal on the refusal record, the import-graph test, the stale-token no-write test) and `design-minimal-dispatch` (the per-type actor table test, the ACK-lost test, the explicit-create invariant, and the forward contract for the lifecycle unit). Two judge fixes are new: a WAL-safe verify-only inspect and binding the listener before opening the journal. "Design judgment" maps every judge error to its resolution.

**Revision 2** answers the completeness critic (`panel/critic.md`: 16 issues, none high, 7 medium). The main changes are listener hardening against stdlib error paths and trickling clients, an honest statement of the refusal byte coupling, a split refusal validator, a capacity precheck and an entry cap on the spool, a pair-keyed reader registry, a resolved-only reserve in the refusal budget, and inspect/resume edge rules. "Critic issues resolved (revision 2)" maps each issue to its change, or explains why part of it is rejected.

Facts marked "probe sN" were checked by the synthesizer with scripts in `panel/probe-synth/` (macOS 25.6, Python 3.13.7, real syncs; outputs in `*.out`):
- **s1** (`s1_inspect_neutrality.py`). On a lock-absent image, a verify-only open (store open, `_replay_finding`, close) adds only `lock`, changes nothing, and the next real open's `restart_recovery` body is byte-equal to a twin opened without the inspect. On a lag-1 image it adds and changes nothing. In both, the inspected head's `record_digest` equals the next restart's `recovered.record_digest`, which is what the resume token binds.
- **s2** (`s2_import_graph.py`). A fresh interpreter importing the front door's dependencies (`http.server`, `argparse`, `json`, `logging`, `threading`, `secrets`, `recovery_journal`, `journal_ingress`) loads no `subprocess` and no `forwarder`, `run_spawner`, `receiver`, `notification`, `run_command` or `__main__` module. Importing `receiver`, `__main__` and `replay` loads no journal module and no `sqlite3`.

Judge probes cited as "J1 p1", "J1 p2" and "J2 q1-q5" are in `panel/probe-judge-1/` and `panel/probe-judge-2/`; design probes as "AO p1-p4", "OF p1-p3" and "MD p1-p5". Critic probes "c1a-c1c" are in `panel/probe-critic/c1_http_edges.py`: a no-read 503 reached a urllib client 500 times out of 500 on macOS; the stdlib echoes caller bytes into `send_error` responses; the handler timeout applies per `recv`, so a trickle survives it.

Facts marked "probe r1" were checked by the reviser with `panel/probe-reviser/r1_http_hardening.py` (output `r1_http_hardening.out`; macOS 25.6, Python 3.13, `127.0.0.1:0`):
- **r1a.** A `send_error` override mapping the status to a closed code sends no caller byte for a canary in the method, the request target, the HTTP version, a header line over 65,536 bytes or a malformed header. When the version cannot be parsed, the stdlib still has `request_version == "HTTP/0.9"`, so the reply is the bare code with no status line. With `log_message` overridden, stderr stays empty.
- **r1b.** A raw reader that re-arms `settimeout(deadline - now)` before each `recv_into`, wrapped in `io.BufferedReader` and installed in `setup()`, cuts a body trickled at one byte every 0.1 s at 1.0 s under a 1 s deadline, and the 400 still reaches the client. It also cuts a header trickle at 1.0 s; the stdlib's own `TimeoutError` path closes without a response.
- **r1c.** A non-blocking semaphore in `process_request` with a cap of 2 closes the third connection at once (EOF, 0.0 s) and starts no handler thread. Slots are released in `process_request_thread`'s `finally`.
- **r1d.** A `handle_error` override that records only the exception type name leaves stderr empty when a handler raises.

**Proposal marking.** Every limit, code string, class, field name, digest tag, file name and exit code below is a proposed routine choice that requires review (spec L341-347). "Proposals requiring ratification" lists them.

**Citation keys.** `spec Lnn` is `reviews/ticket-37/recovery-specification.md`. `plan` is `reviews/recovery-journal/implementation-plan.md` (unit 15; R1-R7 at L735-746, I-numbers at L983-1015, P7 L1336, P20 L1359, P22 L1361, Deferred L1376-1396, residual risk L1425). `u16` is `reviews/journal-ingress/implementation-plan.md` (D12 L188-191, class rule L429-435, resend hypothesis L465-467, "Response bodies" L469, U16-P16/P17 L716-717, Deferred L722-746). `ADR12` is `docs/adr/0012-run-outcomes-and-recovery-are-explicit.md`. `J1-AO-3` names judge 1's third error in admission-only; `J2-OF-4` judge 2's fourth in operator-first; `MD` is minimal-dispatch.

These facts were re-read against the working tree on 2026-09-24:
- **Receiver today.** `accept` validates with the legacy `validate_notification`, writes the body into a fresh Run directory and queues it (receiver.py L84-89). The handler reads `int(Content-Length or 0)` bytes and answers 202, 400 with `str(error)`, which echoes caller data, or 500 (L135-149). `__main__.serve` constructs a Forwarder holding the Jira credential before the Receiver (L114-131).
- **Legacy seam.** `tests/test_replay.py` expects `[202, 202, 202]` and three spawns from the conftest `receiver` fixture. The firing and repeat fixtures are byte-identical and share `body_digest` `8384bd0b…` (J2 q1).
- **The shell.** `_open_verified` replays, then calls `finish_open`, then `_run_restart_recovery` (recovery_journal.py L195-233). Every open appends `restart_recovery` (plan I11). `_replay_finding(store, candidate)` is the whole verification (L236-277). `snapshot()` has 16 pinned keys (D11). `JOURNAL_ERROR_CODES` is pinned by no test.
- **The store.** `_verify_open` computes `wal_found` and **then** connects (journal_store.py L827-828), so an open of a WAL-absent image creates an empty WAL and changes the next open's `wal_found` from `null` to `{size: 0}` (J1 p1, p2). `_take_lock` creates an absent `lock` (L302-306). A decode failure on a digest- and chain-verified row is the process hold `journal_schema_unsupported`.
- **The reducer.** `apply_delta` adds a dispatch hold only when absent (L649-652), so `restart_recovery`'s `since` is the first restart after the last clear. Only genesis and restart deltas set `new_boot_id`. `state_digest` covers `head`, `logical_bytes` and `dispatch_holds` (L720-741). No test constructs a `Delta`.
- **The records.** The event-type check precedes the actor check (journal_records.py L456-460). The envelope accepts only `schema_version == 1`, checked at L443 before every other field (`test_a3_schema_version_unknown_event_type_and_unknown_rule_are_unsupported` pins `record_unsupported` for 2). `_TYPE_VALIDATORS` is keyed by type and pinned by no test. The writer side is separate: `seal` (L492) and `content_digest` (L577) write `SCHEMA_VERSION`, and `Record` has no schema-version field. `thaw` leaves lists as lists; v1 validators require tuples; `parse_json` decodes arrays as tuples.
- **Budgets.** `plan_admission` and `_verify_admission_pair` compare `logical_bytes + charge` with `ordinary_bytes` (journal_reducer.py L363-365, L526-528). Restart and capacity-hold records compare it with `total_bytes`, where `charge = len(record.body) + RECORD_OVERHEAD_BYTES` (384). Every record advances `logical_bytes`.
- **The store's open.** `_verify_open` returns **before connecting** on an anchor finding, on a persisted anchor hold, or when the DB is absent or shorter than `PAGE_SIZE` (journal_store.py L817-826). Only past those checks does it compute `wal_found` and connect.
- **The stdlib listener (3.13).** `BaseHTTPRequestHandler` calls `send_error` only with 400, 414, 431, 501 and 505 (parse_request and handle_one_request). The default `send_error` writes the caller-derived message into the reason phrase and an HTML body, and `log_error`s it (probe c1b). `socketserver.BaseServer.handle_error` prints a full traceback to stderr.
- **Import pins.** A12 pins journal_records' `journal_source` names to exactly `("MAX_FINGERPRINT_BYTES", "source_from_json")` and six `from` imports. B11 pins the reducer to six `from` imports. D13 pins recovery_journal's top-level set, `(0, "collections.abc", ("Callable",))` exactly, and relative imports to the four journal modules; `os`, `http` and `sqlite3` are banned there. F5 covers exactly the five unit-15 modules by name. F3 asserts `seen_types == set(jr.EVENT_TYPES)`. S6 (`test_forwarder_json_string_cap.py`) scans every package module for `parse_json` calls.
- **Full suite at baseline:** 4443 passed, 38 skipped.

## Why this unit

Spec L193-196 makes the admission commit the first ordering point, and ADR12 L27 forbids acknowledging an admission that is not durable. Units 15 and 16 built the journal and the sanitizer, but nothing connects HTTP to them: the Receiver still acknowledges with no durable record. Three obligations meet at this seam:
- **Receiver integration** (plan Deferred 2): open at startup, answer 503 while held, admit before the 202, map `JournalError` to 503 with `Retry-After`, keep the journal outside `runs_directory`, and spool the raw body by `body_digest` before the admission commit.
- **Operator resume** (plan P20, Deferred 6): "must follow, or ship with" integration, because every restart holds dispatch and nothing clears it. Inspect must be verify-only and append nothing (critic 14).
- **Durable refusal summaries.** Plan P22 deferred them to unit 16; u16 re-deferred them to "the integration unit" (U16-P16), and plan L1425 requires refusals to be visible. A front door that answers 422 and forgets hides every lost Resolved after a restart.

This unit is also the first that can run spec L322's "Receiver admission" acceptance row over real HTTP: durable admission before the ACK, latest-group dedupe, capacity and backpressure, and restart replay.

## The user's opt-in decision and the legacy-identity contract

**User decision.** The journal is opt-in. With it off, which is the default, the Receiver, the demo, `replay` and every existing test behave exactly as at `b931610`. `tests/test_replay.py` keeps expecting three Runs, because the legacy path does not deduplicate the repeat.

**How this plan implements it: the opt-in is a separate command.** The operator opts in by starting `python3 -m grafana_jsm_sandbox.journaled_receiver --state-dir S`. The default container command (`python3 -m grafana_jsm_sandbox`), the conftest fixtures and `receiver.py` are untouched. Reasons:
- In admission-only mode the journaled path shares no behavior with the legacy Receiver: no queue, worker, spawner, Forwarder, credential or Run directory, and a different response and health contract.
- A `Receiver(..., journal=None)` keyword would put two contracts behind one handler class (J2-OF-3), and wiring it through `__main__` would start a Forwarder holding the real Jira token for a process that never runs anything.
- An environment switch in `__main__` would silently turn the demo into a front door that creates no Incidents, and would add a variable the container contract (`test_container.py` `SETTINGS_VARIABLES`) must then list (J1-MD-6).

This reading of "opt-in on the Receiver" is ratification item **U17-P2** (J1-AO-8). The rejected alternative is fully specified so it can be taken instead: about 10 lines in `receiver.py` adding a keyword-only `journal=None`, which swaps the handler class, starts no worker and makes `accept` raise; no existing test changes either way.

**Legacy-identity contract.** Each clause has a check in "Ownership and validation".
1. These files are byte-identical to `b931610`: `receiver.py`, `__main__.py`, `replay.py`, `run_spawner.py`, `run_command.py`, `notification.py`, `reset.py`, `journal_store.py`, `journal_source.py`, `journal_ingress.py`, every `forwarder_*` module, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `tests/conftest.py` and every existing test file.
2. The legacy import graph loads no journal module and no `sqlite3` (probe s2; test L1), and no legacy module imports new code (L2).
3. The new modules read no environment variable and never reference the spawner, the Forwarder or a credential (L3), so the opt-in cannot leak into the demo process.
4. The three journal modules this unit edits are not loaded by the legacy path at all (clause 2). Their existing v1 behavior is kept by additive changes, the unchanged E16 golden and the tests in "Existing-module changes".

The unit-15 plan's Deferred 2 anticipated a deliberate edit to `test_the_sequence_arrives_in_order_and_starts_one_run_each` and a conftest fixture creating a journal per test. The user's opt-in decision supersedes both: neither is edited, and the journaled path gets its own fixtures in new files.

## Unit boundary

### The Run-dispatch crux, ruled: option (i), admission-only

**In journaled mode the Receiver durably spools, admits, dedupes and refuses, and starts no Run.** The front door has no spawner parameter and imports no `run_spawner`, `receiver`, `subprocess` or Forwarder module (tests L3 and H1), so no process can exist without a durable `run_intent`. A journaled 202 means "durably admitted and body retained", never "a Run will start"; the receipt says `"run": "not_dispatched"`. Runs return in the run-lifecycle unit. Both judges ruled (i).

Why not (ii), a minimal durable `run_intent` plus launch now:
- **Spec step 2 has no honest minimal form today.** A Run is eligible only under the gate conjunction: a durably confirmed ticket-38 reservation, mandatory Forwarder readiness, venue readiness, operator resume and no hold (spec L197-201, L297-300; ADR12 L35). None of these inputs exists in source. A "minimal" intent must invent them or freeze their absence into v1 validators (R1), as `design-minimal-dispatch` did with `reservation_id: null` and `gate_profile: "journal-only-v1"` (J1-MD-1, J2-MD-3). The spec's faithful behavior for an ineligible Run is `run_hold` only, which is (i).
- **Step 2 also orders "commit run_intent, then register the lease, then commit the launch claim", and step 3 records spawn acceptance "immediately after the real spawner observation"** (L197-203). `spawn_run` returns only at exit, so without a spawner observer every launched Run sits in the L254 window ("run intent before spawn observation": launch unknown, hold) for its whole life, and every crash leaves a hold that needs cancel, abandon and reconcile, which are plan Deferred 3 and 6 (J1-MD-2, J2-MD-2).
- **No Run means no same-uid child next to the journal and spool** (ADR12 L25; plan Deferred 9). The lifecycle unit must settle isolation before Runs and the journaled front door coexist (J1-MD-5, J2-MD-8).

Why not (iii), journaling the admission and handing it to the legacy queue: that spawns from a journaled admission without a durable intent, which is forbidden, and the journal would say "pending" while a Run already acted on OPS. Treating the admission record itself as the intent collapses ADR12's separation of admission from execution.

**What this costs, stated plainly.** Journaled mode creates no Incidents. It is an admission rehearsal whose acceptance target is spec L322's "Receiver admission" row, not a demo mode. The legacy command stays the demo path.

### What ships with it, and what does not

- **Durable refusal summaries: in.** The deferral chain P22, L1425, U16-P16 ends here (J1-MD-4, J2-MD-5). Record `ingress_refusal`: flood-limited, with 64 of its 256 records reserved for summaries that carry a Resolved member, ordinary class.
- **Verify-only inspect: in.** Offline, it appends nothing and creates no WAL (J1 graft 3).
- **Resume: in, at open only.** `journaled_receiver --resume-token T --operator NAME` verifies the journal, checks `T` against the inspected head **before any write**, then commits `restart_recovery` followed immediately by one `operator_action`. It clears only `restart_recovery`. There is no online operator channel, token file or loopback listener (J1 graft 1, J2 graft 1). The spec's precondition "held work completed or explicitly disposed of" (ADR12 L35; spec L260-263) holds vacuously because no work exists.
- **Out:** capacity clear (admission counts never fall within a generation, so a clear would be false until reset or compaction), cancel, retry, abandon, reconcile, `reset_commit`, the online operator channel, spool deletion, and every run-family record.

### What an operator sees

1. **Setup.** `python3 -m grafana_jsm_sandbox.journal_operator create --state-dir S` makes `S`, `S/journal` (genesis) and `S/spool`, all 0700, syncs `S`'s parent and `S`, and prints `{"journal_uuid": …}`.
2. **Serve.** `python3 -m grafana_jsm_sandbox.journaled_receiver --state-dir S` binds `127.0.0.1:8080`, opens the journal, which appends `restart_recovery` as every open does, and logs `journaled admission-only mode: Notifications are recorded durably; no Run is started` and `dispatch held: restart_recovery (inspect, then restart with --resume-token)`. At start it prints the resolved state directory and the resolved runs directory that the placement check used. When the legacy command also runs on this host, `--runs-directory` must name the legacy `RUNS_DIRECTORY`, because the front door never reads the environment; otherwise the placement check protects only the default `runs`.
3. **`replay` posts.** Grafana can post only when the front door listens where Grafana can reach it, for example `--host 0.0.0.0` for the compose Grafana container on this host. That is deliberately not the default (U17-P15). Each accepted POST gets a 202 JSON receipt. For the canned sequence the results are `admitted`, `suppressed` and `pending_reduced`, each with `decision: "held"`; the spool holds 2 files because firing and repeat are byte-identical. `GET /health` shows counts, holds and counters, never Fingerprints.
4. **Resume.** Stop the front door (Ctrl-C). `journal_operator inspect --state-dir S` prints the verified report: head, holds, pending entries, recent refusals, the spool survey, and `resume.token`. Restart with `--resume-token <token> --operator NAME`. Later admissions record `decision: "admitted"`. Nothing is dispatched; the log and receipt say so. Any restart re-holds. If inspect reports `unverified` (`wal_absent`), start the front door once, stop it and inspect again. If that start reports `held` on `/health`, the hold code shown there is the verdict, and inspecting again will not change it.
5. **Refusals** get their ingress class and the code as the body. One durable summary per flood key appears in `inspect`, Resolved members first.
6. **A held journal** answers every POST with 503 and `Retry-After` without reading the body, and `/health` is 503 with the hold code.
7. **Capacity codes are permanent for this `S`.** Admission counts, pending entries and bytes never fall within a generation, and nothing here clears a capacity hold. After `capacity_admissions`, every new body is refused with 503 before it is spooled. `capacity_pending`, `capacity_bytes` and `spool_full` refuse most new bodies. The only remedy is to stop, keep `S` as evidence and `create` a new state directory.
8. **A spool conflict.** If inspect exits 5 with an entry under `mismatched_orphans`, stop the front door, move that file out of `S/spool` by hand (keep it as evidence; no tool deletes), and start again. The next arrival of that body rewrites the entry. A mismatched **referenced** entry is different: its body was acknowledged and is now lost. Leave it in place, keep `S` as evidence and create a new state directory, as in step 7. The same bytes arriving again would latch the spool.
9. **To get the demo back**, run the unchanged legacy command. It neither reads nor writes `S`, and what it handles is not journaled (residual risk).

### In (one reviewed local commit)

1. **Journal extensions** in `journal_records.py`, `journal_reducer.py` and `recovery_journal.py`: the pair-keyed reader registry; two record types, their commit shapes, projection fields, plan and verify functions; `record_refusal`; `admission_precheck`; resume at open; verify-only `inspect_recovery_journal`.
2. **`grafana_jsm_sandbox/journal_spool.py`** (new): the content-addressed body spool, with no deletion path.
3. **`grafana_jsm_sandbox/journaled_receiver.py`** (new): the front door and its `main`.
4. **`grafana_jsm_sandbox/journal_operator.py`** (new): `create` and verify-only `inspect` with the spool survey.
5. **Seven new test files and one new golden** (see "Ownership and validation").
6. **Root-owned docs and evidence**: a "Front door" section in `docs/recovery-journal.md`; this plan and `reviews/receiver-journal/validation.json`, `focused-tests.txt`, `full-suite.txt`, `outcome.md` and `review.md`; the unit-17 entry in `.scratch/many-alerts-one-incident/execution-backlog.md`; the progress note in `issues/37-run-recovery-and-admission-specification.md`.

### Size and split point

| File | Change | Estimated source lines |
| --- | --- | --- |
| `journal_records.py` | pair-keyed reader registry, actor table, two validators, the summary normalizer and its strict checker (a port) | +145 |
| `journal_reducer.py` | fields, two shapes, plan and verify functions, the reserve, boot fields, digest | +180 |
| `recovery_journal.py` | `record_refusal`, `admission_precheck`, resume at open, verify-only inspect | +220 |
| `journal_spool.py` | new, with the entry cap, `sync_directory` and the orphan check | 215 |
| `journaled_receiver.py` | new, with listener hardening (error map, deadline reader, connection cap) | 400 |
| `journal_operator.py` | new, with the create syncs | 160 |
| **Total** | | **about 1,320** |

Revision 2 adds about 160 source lines to revision 1's 1,160. Tests come to about 2,900 lines in seven files. **Split trigger:** if the added source lines (`git diff --numstat` over `grafana_jsm_sandbox/` plus the new modules) pass 1,400, commit two reviewed units, as 15a and 15b were:
- **17a:** item 1 with tests A and K and the front-door golden. It is inert: no production path calls it.
- **17b:** items 2-4 with tests S, H, O, C and L.

P20 holds in that order, because resume exists in the shell before any HTTP front door ships. At about 1,320 estimated lines the margin to the trigger is about 80 lines, so the root measures after implementer A's changes land. If A's three modules pass 625 added lines (1,400 minus B's estimated 775), the root splits at once rather than at the end.

## Existing-module changes

Every change is additive and named below with the existing test that pins its area. **No existing test file changes.**

### `journal_records.py` (about +145; imports unchanged)

1. After `RECORD_CLASS`:
   - `FRONT_DOOR_EVENT_TYPES = ("ingress_refusal", "operator_action")` and `REGISTERED_EVENT_TYPES = EVENT_TYPES + FRONT_DOOR_EVENT_TYPES`. **`EVENT_TYPES` stays the unit-15 five-tuple**, because F3 asserts `seen_types == set(jr.EVENT_TYPES)` over a journal that holds only those.
   - `RECORD_CLASS` gains `ingress_refusal: "ordinary"` and `operator_action: "recovery"`. It stays keyed by type: a type's class never changes across schema versions.
   - **The reader registry is keyed by `(event_type, schema_version)`** (critic 7). `_TYPE_VALIDATORS` becomes `MappingProxyType({(type, 1): validator for the seven types})`, and `TYPE_ACTORS = MappingProxyType({...})` has the same keys: each v1 type and `ingress_refusal` map to `"receiver"`, and `operator_action` to `"operator"`. `SCHEMA_VERSIONS = frozenset(version for _, version in _TYPE_VALIDATORS)`, which is `{1}` now.
2. **Four predicates in `_validate_envelope`**, each at its current position:
   - L443: `schema_version != SCHEMA_VERSION` becomes `schema_version not in SCHEMA_VERSIONS` (`record_unsupported`), still after the int-type check and before every other field;
   - L456: `event_type not in EVENT_TYPES` becomes `(event_type, schema_version) not in _TYPE_VALIDATORS` (`record_unsupported`);
   - L459: `actor != "receiver"` becomes `actor != TYPE_ACTORS[(event_type, schema_version)]`, still after the event-type check and still behind `actor not in ACTORS`;
   - L467: the dispatch becomes `_TYPE_VALIDATORS[(event_type, schema_version)](...)`.

   While only version 1 is registered, `version in {1}` is `version == 1`, and the pair check is `type in REGISTERED_EVENT_TYPES` given that version. So for each v1 type all four predicates accept exactly the set they accepted before, with the same codes and at the same positions. `test_actor_spawner_is_rejected_even_though_it_is_a_valid_actor` still gets `record_field`, and the schema-version-2 case still gets `record_unsupported` before any other field check. **The writer side is unchanged**: `seal` and `content_digest` still write `SCHEMA_VERSION` (1), and `Record` gains no field. A later `(type, 2)` pair needs one registry entry on the reader side. On the writer side it needs the per-record version described in Deferred 1.
3. Constants, restated because A12 pins the imports (parity-tested by A5): `REFUSAL_RULE = "first-per-membership-v1"`, `MAX_REFUSAL_RECORDS = 256`, `REFUSAL_RESOLVED_RESERVE = 64`, `INGRESS_REFUSAL_CODES_V1` (the 16 codes, sorted), and private copies of the five member codes, the four no-group codes, the statuses, 32 listed members, 256 alerts, the 4,096-byte summary bound and the 262,144-byte body bound. `OPERATOR_ACTIONS = ("resume",)`, `RESUME_RULE = "resume-at-open-v1"`, `RESUMABLE_HOLDS = ("restart_recovery",)`.
4. **The summary check is two functions** (critic 4). Both are verbatim ports of `journal_ingress`'s `_groups_ok`, `_members_ok` and `refusal_to_json` checks, including the code-to-group coupling, Resolved-first order, member uniqueness and the listed-Resolved count (J2-OF-4):
   - `_check_refusal_summary(value) -> None` is **strict**. It requires a `dict` with exactly the nine keys and `members` as a **tuple** of 2-**tuples**, which is the v1 convention that `parse_json` yields and `_validate_admission` enforces. It also requires every cross-field rule and at most 4,096 canonical bytes. Any violation raises `RecordError("record_field")`. `_validate_ingress_refusal` calls only this function, at seal and at decode alike.
   - `refusal_summary_data(summary) -> dict` is the **normalizer**, called only by `RecoveryJournal.record_refusal` before sealing. It accepts `members` as a list or tuple of lists or tuples (the `refusal_to_json` output has lists), rebuilds a new dict with tuples, calls `_check_refusal_summary` on the result, and returns it. `record_refusal` seals that **normalized** dict, so the in-memory `Record.data` equals the replayed one (J2-OF-7).
5. `_validate_ingress_refusal` and `_validate_operator_action` (tables and check order under "Journal extensions"), registered under `(type, 1)`; `__all__` grows.

### `journal_reducer.py` (about +180; still six `from` imports, names added to the existing `.journal_records` import)

1. `Projection` gains fields that no admission transition reads or writes (R4):
   - front-door fields: `refusal_keys: set[str]`, `refusal_count = 0`, `refusal_unreserved_count = 0` (records whose summary has no Resolved member), `resume_count = 0`, `last_resume_commit_seq: int | None = None`;
   - boot fields: `boot_start_commit_seq: int | None = None` (the commit that started the current boot) and `boot_recovered: Head | None = None` (the head that boot's restart recovered; `None` after genesis).
2. `Delta` gains four **defaulted** trailing fields: `refusal_key_add: str | None = None`, `refusal_unreserved: bool = False`, `dispatch_hold_clear: str | None = None`, `resume_commit_seq: int | None = None`. Every existing construction is keyword-only and unchanged.
3. `apply_delta`:
   - at the top, before `p.head` moves: `if delta.new_boot_id is not None: p.boot_recovered = p.head; p.boot_start_commit_seq = delta.head.commit_seq`. Only genesis and restart deltas set `new_boot_id`, so this reads existing Delta data and changes no existing field. `_verify_restart` and the restart record are untouched (contrast J2-OF-6);
   - at the end, three guarded plain statements: add the refusal key, increment `refusal_count`, and increment `refusal_unreserved_count` when the delta says the record was unreserved; `del p.dispatch_holds[code]` (already proven present by `verify_commit`); increment `resume_count` and set `last_resume_commit_seq`. A refusal delta carries `logical_bytes = p.logical_bytes + charge`, as every existing delta does. That is the byte coupling stated under `ingress_refusal`.
4. `_commit_shape` gains `("ingress_refusal",)` and `("operator_action",)` (R3). `verify_commit` routes both after the existing non-restart boot and clock checks, before the capacity and admission branches.
5. New names: `REFUSAL_KEY_TAG = "rj.refusal-key.v1"`, `FRONT_DOOR_STATE_TAG = "rj.front-door-state.v1"`, `RefusalNotRecorded(reason)`, `refusal_key`, `plan_ingress_refusal`, `plan_operator_resume`, `_verify_ingress_refusal`, `_verify_operator_action`, `front_door_digest`.
6. **`state_digest` is byte-for-byte unchanged** (`rj.state.v1`; J1-AO-5, J2-AO-1). E16's `_E16_STATE_DIGEST`, head and pending digests hold for the committed golden. Front-door state is pinned by `front_door_digest(p) = tagged_digest("rj.front-door-state.v1", {refusal_count, refusal_unreserved_count, refusal_keys_digest: _list_digest("rj.refusal-key-set.v1", keys), resume_count, last_resume_commit_seq})`.
7. No try/except is added (F5 notes the reducer has none).

### `recovery_journal.py` (about +220; top-level imports unchanged)

1. `JOURNAL_ERROR_CODES` gains `refusal_invalid`, `resume_invalid` and `resume_stale`. None latches.
2. New frozen dataclasses `ResumeRequest`, `ResumeReceipt` and `Inspection`, and `REFUSAL_OUTCOMES = ("recorded", "coalesced", "limit", "no_room")`.
3. `open_recovery_journal(..., resume: ResumeRequest | None = None)`, keyword-only with a `None` default, so every existing call is unchanged:
   1. A malformed request (token not 64 lowercase hex; `operator` or `reason` failing `validate_id`) raises `resume_invalid` **before** the store is opened.
   2. In `_open_verified`, after replay found nothing and the boot ID was minted, and **before** `finish_open`: a token different from `candidate.head.record_digest` raises `resume_stale`. The existing `finally` closes the store. Nothing is written (W13).
   3. A store or replay finding follows today's path unchanged: a recovery finding is persisted and the handle returned held, with `resumed_this_boot` `None`. Resume never lifts or skips a finding.
   4. After `_run_restart_recovery` committed, `_resume_at_open` stamps, mints, plans `plan_operator_resume` and commits through the existing `_commit`. Clock, ID, capacity and write faults latch exactly as for restart.
4. `_replay_finding(store, candidate, *, observe=None)`: a keyword-only callback invoked with each verified commit group. Only inspection passes it.
5. `RecoveryJournal` gains `record_refusal(summary: dict) -> str`, the property `resumed_this_boot -> ResumeReceipt | None` and `front_door_status() -> dict`. Per-boot refusal outcomes live in a new dict, **not** in `_refusals_this_boot`, which D11 requires to hold capacity codes only. `record_refusal` calls `refusal_summary_data` first; a malformed summary, or a code outside `INGRESS_REFUSAL_CODES_V1`, raises `refusal_invalid` and latches nothing.
6. `RecoveryJournal.admission_precheck() -> str | None` (critic 6) returns `"capacity_admissions"` iff the state is `ready` and `"capacity_admissions"` is in the projection's `dispatch_holds`; otherwise `None`. It takes no lock and writes nothing: it reads one state string and makes one dict membership test, each atomic under the GIL. It is advisory, and `admit` stays authoritative. The answer is exact in one direction: that hold is written only after a refusal with `admission_count + 1 > max_admissions` (journal_reducer.py L309), the count never falls within a generation, and nothing in this unit clears the hold, so every later `admit` would refuse with the same code. It deliberately does not fire when the bound is merely reached, so the first refusal still goes through `admit` and writes the durable `capacity_hold`. `capacity_pending` and `capacity_bytes` are not prechecked, because a repeat or a smaller body can still be admitted after either.
7. `inspect_recovery_journal(directory) -> Inspection` (see "Operator entry points").
8. **`snapshot()` is unchanged** (D11 pins its 16 keys). Imports add names to the existing relative `from` imports only (`DB_FILENAME`, `PAGE_SIZE` and `WAL_FILENAME` from `.journal_store`; the new reducer names). The `collections.abc` import stays exactly `Callable`, because D13 asserts that tuple; new annotations use `dict`. `__all__` grows by four.

### Existing tests that pin changed code, and why each stays green

| Existing test | What it pins | Why it holds |
| --- | --- | --- |
| schema-version case (`test_journal_records.py` L449) | `schema_version: 2` on a genesis gives `record_unsupported` | `2 not in SCHEMA_VERSIONS`, checked at the same position (L443) |
| unknown-type case (`test_journal_records.py` L455) | `not_a_real_type` gives `record_unsupported` | `("not_a_real_type", 1)` is not a registered pair |
| `test_actor_spawner_is_rejected…` | a v1 type requires `receiver` | `TYPE_ACTORS` maps all five `(type, 1)` pairs to `receiver` |
| F3 (adversarial L638-658) | `seen_types == set(EVENT_TYPES)` | `EVENT_TYPES` unchanged |
| F1 mutation matrix | v1 validators reject every leaf mutation | v1 validators and verify functions untouched |
| A12, B11, D13, F5 | exact imports, counts, except discipline, no `os`/`http`/`sqlite3` in the shell | no new module imported; names added inside existing `from` imports; `collections.abc` tuple unchanged; new except bodies only assign or pass |
| D11 | 16 snapshot keys; `refusals_this_boot` capacity codes only | `snapshot()` and `_refusals_this_boot` unchanged |
| D9 | null projection fields while held | unchanged |
| E16 guard and rebuild | the 13-record golden's three digests; rebuild reproduces | `state_digest` formula unchanged; boot fields excluded from it; open without `resume` unchanged |
| S6 (`test_forwarder_json_string_cap.py`) | `parse_json` call sites package-wide | the new modules never call `parse_json` |
| `test_forwarder_upstream_adversarial.py` scans | no `.py` file under the repository names the connector; it rglobs `.scratch/` probes too | the new modules and the `panel/` probes (including `probe-reviser/`) do not |
| `test_journal_store.py`, `test_journal_source.py`, `test_journal_ingress_corpus.py`, `test_journal_ingress_adversarial.py` | the store decodes through the edited envelope; the unit-16 helpers A4 imports | decoding is unchanged for every v1 record; A4 imports the helpers read-only |
| `test_receiver.py`, `test_replay.py`, `test_container.py` | legacy 202/400/500, three spawns, env contract | those modules and fixtures are byte-identical; the new entry point reads no environment |

## New modules

House rules as in units 15 and 16: exact-type checks, closed code sets in `frozenset`s and `MappingProxyType`s, `__all__`, and every `except` body only assigns or passes, with a fresh error raised after the `try` (test L4). None reads an environment variable.

### `grafana_jsm_sandbox/journal_spool.py` (I/O, about 215 lines)

Holds each admitted Notification's exact bytes, keyed by `body_digest`, for the lifecycle unit's Run input. It is not the journal: the journal never holds a raw body (spec L156-159).

**Imports (AST-checked: nothing outside this allowlist):** `__future__`, `dataclasses`, `fcntl`, `os`, `re`, `secrets`, `stat`, `sys`, `threading`, `pathlib`; `from .journal_ingress import MAX_INGRESS_BODY_BYTES, body_digest`. Not `journal_store` (its sync primitive is private), `sqlite3`, `logging`, `http`, `subprocess` or `socket`.

```python
MAX_SPOOL_BYTES = 256 * 2**20                     # injectable per instance; the spool is never replayed
MAX_SPOOL_ENTRIES = 20_000                        # injectable; 2 x the default max_admissions (critic 6)
SPOOL_ERROR_CODES = frozenset({"spool_argument", "spool_missing", "spool_path_invalid",
    "spool_permissions", "spool_sync_unsupported", "spool_full", "spool_conflict",
    "spool_write_failed", "spool_broken"})

class SpoolError(Exception):                      # .code; args == (code,); never a path or bytes
    code: str

def create_spool(directory: Path) -> None         # mkdir 0700; refuses an existing path; journal_operator only
def full_sync(fd: int) -> None                    # F_FULLFSYNC on darwin, os.fsync on linux, else spool_sync_unsupported
def sync_directory(path: Path) -> None            # O_RDONLY | O_DIRECTORY | O_NOFOLLOW, full_sync, close;
                                                  # any OSError -> spool_write_failed (critic 13)
def survey_spool(directory: Path, referenced: frozenset[str]) -> dict[str, object]   # read-only; inspect only

class JournalSpool:
    @classmethod
    def open(cls, directory: Path, *, max_bytes: int = MAX_SPOOL_BYTES,
             max_entries: int = MAX_SPOOL_ENTRIES) -> JournalSpool
        # never creates; lstat custody: a directory, not a symlink, euid-owned, mode 0700 (else
        # spool_missing / spool_path_invalid / spool_permissions); sums the sizes of 64-hex entries
        # and counts every directory entry (64-hex names, temporaries and unexpected names alike)
    def store(self, body: bytes, digest: str) -> str             # "written" | "present"
    @property
    def broken(self) -> str | None                               # the latched code, or None
    def status(self) -> dict[str, object]
        # {"state": "ok"|"broken", "code", "bytes", "max_bytes", "entries", "max_entries",
        #  "written_this_boot", "full_refusals_this_boot"}
```

**`store`**, under one spool lock (only one process writes the spool, because the front door holds the journal's flock first):
1. Exact `bytes` and `digest == body_digest(body)`, else `spool_argument`.
2. Latched: raise the latched code as `spool_broken`.
3. Verified earlier this boot: return `"present"` with no I/O. The verified set holds only digests of entries that exist, so it never exceeds `max_entries` members (a few megabytes at 20,000).
4. The entry exists: open with `O_RDONLY | O_NOFOLLOW`; require a regular file, 0600, euid-owned, one link, at most 262,144 bytes and `body_digest(content) == digest`; fully sync the directory once (a W3 entry may not yet have a durable directory entry); return `"present"`. Any mismatch latches `spool_conflict` and the entry is left byte-identical as evidence.
5. Absent: if `bytes + len(body) > max_bytes` or `entries + 1 > max_entries`, raise `spool_full` (counted, not latched). Otherwise write `.tmp-<digest>-<16 hex>` (`O_CREAT | O_EXCL | O_NOFOLLOW`, 0600), `full_sync`, close, `rename` to `<digest>`, `full_sync` the directory, and return `"written"`.
6. Any `OSError` or sync failure latches `spool_write_failed`. A sync is never retried, as the store's rule (docs "After any write or sync failure").

**There is no deletion path**: no `unlink`, `remove`, `rmdir`, `rmtree` or `truncate` (AST, S9). A temporary left by a failure stays and is counted.

**`survey_spool`** returns `{entries, bytes, referenced, orphans: [≤ 32], orphans_total, missing: [≤ 32], missing_total, mismatched: [≤ 32], mismatched_total, mismatched_orphans: [≤ 32], mismatched_orphans_total, temporaries, unexpected}`. **Every** 64-hex entry is content-verified with the same custody checks as `store` step 4: referenced and orphaned alike. The work is bounded by `MAX_SPOOL_ENTRIES` files of at most 262,144 bytes (critic 14). An orphan is a 64-hex entry no admission references. A mismatched orphan is one whose content would latch `spool_conflict` on the next arrival of its digest. `unexpected` counts other names. It writes nothing.

### `grafana_jsm_sandbox/journaled_receiver.py` (about 400 lines)

**Imports (AST-checked: nothing outside this allowlist):** `__future__`, `argparse`, `dataclasses`, `io` (the deadline reader), `json`, `logging`, `os` (only `geteuid` for the custody of `S`), `re`, `stat`, `sys`, `threading`, `time`, `types` (`MappingProxyType`), `collections`, `http` (`http.server` and `HTTPStatus` only), `pathlib`; `from .journal_ingress import INGRESS_HTTP_STATUS, MAX_INGRESS_BODY_BYTES, oversize_refusal, refusal_to_json, sanitize_notification`; `from .journal_spool import …`; `from .recovery_journal import JournalError, RecoveryJournal, ResumeRequest, new_id, open_recovery_journal`. It never imports `subprocess` or `socket`, never reads the environment, and never imports a module in the exact set `{forwarder, run_spawner, receiver, notification, run_command, __main__}` or any other `forwarder_*` module directly (L3). `forwarder_json` is an **expected transitive load** through `journal_records` and `journal_ingress`, and L3 allows it by name.

```python
MODE = "journaled-admission-only"
MAX_IN_FLIGHT = 8; MAX_CONNECTIONS = 32; REQUEST_DEADLINE_SECONDS = 10.0
RETRY_AFTER_SECONDS = 10; BUSY_RETRY_AFTER_SECONDS = 1       # 10 = this demo's group_interval
DEFAULT_HOST = "127.0.0.1"; DEFAULT_PORT = 8080; DEFAULT_RUNS_DIRECTORY = Path("runs")
FRONT_DOOR_CODES = frozenset({"state_missing", "state_path_invalid", "state_permissions",
    "state_placement_invalid", "listener_bind_failed", "front_door_argument",
    "resume_not_applied"})
HTTP_CODES = frozenset({"not_found", "busy", "journal_opening", "http_length_required",
    "http_content_length_invalid", "http_body_incomplete", "http_request_invalid",
    "http_header_invalid", "http_method_unsupported", "receiver_error"})
STDLIB_ERROR_CODES = MappingProxyType({400: "http_request_invalid", 414: "http_request_invalid",
    431: "http_header_invalid", 501: "http_method_unsupported", 505: "http_request_invalid"})

class FrontDoorError(Exception):                  # .code in FRONT_DOOR_CODES
    code: str

class JournaledReceiver:
    """The journaled front door: durable admission before the 202, and no Run."""
    def __init__(self, state_directory: Path, *, runs_directory: Path = DEFAULT_RUNS_DIRECTORY,
                 host: str = DEFAULT_HOST, port: int = 0, resume: ResumeRequest | None = None,
                 max_in_flight: int = MAX_IN_FLIGHT, max_connections: int = MAX_CONNECTIONS,
                 request_deadline: float = REQUEST_DEADLINE_SECONDS,
                 spool_max_bytes: int = MAX_SPOOL_BYTES, spool_max_entries: int = MAX_SPOOL_ENTRIES,
                 wall_clock=time.time_ns, mono_clock=time.monotonic_ns, id_factory=new_id) -> None
        # 1. custody of S (directory, not a symlink, euid, 0700) and placement: resolved S and
        #    resolved runs_directory must not contain each other -> FrontDoorError; nothing touched
        # 2. binds the listener (OSError -> listener_bind_failed) BEFORE any journal or spool access
    @property
    def url(self) -> str
    def start(self) -> None
        # serves 503 journal_opening; JournalSpool.open(S/spool); open_recovery_journal(S/journal,
        # resume=...); then admitting. A JournalError or SpoolError stops the listener and propagates.
        # If a resume was requested and the returned handle is held (so resumed_this_boot is None),
        # start() stops the listener, closes the journal and raises FrontDoorError("resume_not_applied")
        # (critic 8c). The held open has already done exactly what an open without resume does.
    def stop(self) -> None                         # shut the listener, then journal.close()
    @property
    def journal(self) -> RecoveryJournal | None
    def health(self) -> tuple[int, dict[str, object]]   # also callable in-process by tests

def main(argv: list[str] | None = None) -> int
    # --state-dir S (required) --host --port --runs-directory
    # --resume-token HEX --operator NAME [--reason TOKEN]   (--operator is required with the token)
    # prints once, on stdout, the resolved S and the resolved runs directory used by the placement
    # check (critic 16), then "listening on http://<host>:<port>"
    # exit 0 clean stop (SIGINT); 1 refused to start (code on stderr, one-line hint; also resume_stale,
    # resume_invalid and resume_not_applied); 2 usage
```

It never creates `S`, `S/journal` or `S/spool` (explicit create only; plan I21). It logs codes, IDs and counts only. The two paths it prints come from the operator's own arguments, never from a caller.

**Listener hardening** (critics 1 and 2; probe r1). All of it is part of U17-P11:
- **No stdlib error path reflects caller bytes.** The handler overrides `send_error(code, message=None, explain=None)`. It ignores `message` and `explain` and maps `code` through `STDLIB_ERROR_CODES`, which covers exactly the statuses the 3.13 stdlib sends: 400, 414, 431, 501 and 505. The status stays the stdlib's. The reason phrase is the fixed `HTTPStatus` phrase, and the body is the mapped code as `text/plain; charset=utf-8` with `Connection: close`. An unmapped status becomes 500 `receiver_error`. Each mapped code is counted under `http.protocol_errors`. When the version cannot be parsed, the stdlib is still in HTTP/0.9 mode and writes no status line, so the reply is the bare code (probe r1a). `log_message` is overridden to drop everything, which silences `log_request` and both stdlib `log_error` calls. The server overrides `handle_error` to log only `type(exception).__name__`, never the traceback or the client address (probe r1d).
- **One monotonic deadline per request.** `handle_one_request` sets `deadline = monotonic() + request_deadline` before calling the stdlib's. That one deadline covers the keep-alive idle wait, the request line, the headers and the body. `setup()` replaces `rfile` with `io.BufferedReader(_DeadlineReader(self), 65536)`. `_DeadlineReader.readinto` raises `TimeoutError` once the deadline has passed and counts `http.deadline_exceeded`. Otherwise it calls `settimeout(remaining)` and then `recv_into`, so a trickle cannot re-arm the timeout (probe r1b; critic probe c1c). In the header phase, the stdlib's own `TimeoutError` path closes without a response. In the body phase, step 6 answers 400 `http_body_incomplete` on a best-effort basis. Before any response is written, the handler resets the socket timeout to `request_deadline`, because responses are at most about 1 KiB.
- **A connection cap.** The server overrides `process_request`. A non-blocking acquire of a `max_connections` (32) semaphore that fails counts `http.connections_refused` and calls `shutdown_request` at once, with no response and no thread (probe r1c). A slot is released in `process_request_thread`'s `finally`, or at once if the thread fails to start. Gauges `http.connections_open` (at most 32) and `http.in_flight` (at most 8) are reported in health.

### `grafana_jsm_sandbox/journal_operator.py` (about 160 lines)

**Imports (AST-checked: nothing outside this allowlist):** `__future__`, `argparse`, `json`, `sys`, `pathlib`; `from .journal_spool import SpoolError, create_spool, survey_spool, sync_directory`; `from .recovery_journal import JournalError, create_recovery_journal, inspect_recovery_journal`; `from .journal_reducer import DEFAULT_BOUNDS, JournalBounds`. The same bans as the front door.

```python
def create_state(state_directory: Path, *, bounds: JournalBounds = DEFAULT_BOUNDS, **clocks_and_ids) -> dict
    # refuses an existing path (state_exists); in this order (critic 13):
    #   mkdir S 0700; sync_directory(S.parent)
    #   create_spool(S/spool); mkdir S/journal 0700; sync_directory(S)
    #   create_recovery_journal(S/journal)          # its own 4 syncs, as unit 15
    # A crash midway leaves S without genesis: remove S by hand (nothing was ever acknowledged),
    # as journal_create_failed already documents. A sync failure is spool_write_failed, exit 1.
def inspect_state(state_directory: Path) -> tuple[int, dict]    # (exit code, report + "spool" survey)
def main(argv: list[str] | None = None) -> int
#   create  --state-dir S        exit 0; 1 refused (state_exists or a JournalError/SpoolError code); 2 usage
#   inspect --state-dir S        exit 0 ready and spool consistent; 1 held; 2 usage; 3 journal_locked;
#                                4 any other open error, including a spool custody failure of S/spool
#                                (spool_missing, spool_path_invalid, spool_permissions; the spool code is
#                                named in the report and on stderr; critic 8d); 5 ready but the spool is
#                                inconsistent: a referenced body missing or mismatched, or a mismatched
#                                orphan; 6 unverified (wal_absent)
```

`journal_operator` gets `sync_directory` from `journal_spool`, so its own allowlist still has no `os`.

Output is one JSON object on stdout.

## Journal extensions

### `ingress_refusal` (ordinary class, actor `receiver`, `ids` = `{}`)

| `data` key | Validator | Replay (`_verify_ingress_refusal`) |
| --- | --- | --- |
| `rule` | the literal `first-per-membership-v1`; another value is `record_unsupported` (R2) | - |
| `summary` | `_check_refusal_summary` (strict): exactly the nine `refusal_to_json` keys and every cross-field rule; `members` a tuple of `(fingerprint, status)` tuples; at most 4,096 canonical bytes | - |
| `refusal_key` | hex64 | equals `refusal_key(summary)` and is not in `p.refusal_keys` |
| `refusal_seq` | int 1..256 | equals `p.refusal_count + 1` and is at most `MAX_REFUSAL_RECORDS` |
| (reserve) | - | if `summary["resolved"]` is not a positive int: `p.refusal_unreserved_count + 1 <= MAX_REFUSAL_RECORDS - REFUSAL_RESOLVED_RESERVE` (192) |
| (budget) | - | `p.logical_bytes + len(record.body) + RECORD_OVERHEAD_BYTES <= p.bounds.ordinary_bytes`, the same form as `_verify_admission_pair` (critic 11) |

**Check order** (critic 4). Validator: `ids == {}`, then `data` is a `dict` containing `"rule"` (else `record_field`), then the `rule` literal (`record_unsupported`, so a future rule with another shape is unsupported rather than malformed), then the exact key set, then `_check_refusal_summary`, then `refusal_key`, then `refusal_seq` (its type and bounds as `_require_bound_int` checks them). Replay, after the existing non-restart boot and clock checks: sequence, limit, reserve, key recomputation, key novelty, then budget. Every replay failure is `replay_mismatch`. `plan_ingress_refusal` returns `RefusalNotRecorded` in this order: `coalesced` for a known key, checked first so that a known key is coalesced even at the limit; then `limit` for the count or the reserve; then `no_room` for the budget, computed on the sealed record exactly as replay computes it. A record it does plan passes every replay check.

- **Key.** `refusal_key = tagged_digest("rj.refusal-key.v1", {alerts, code, members, members_omitted, refused_group, resolved, source_group})`: the summary **without** `body_bytes` and `body_digest`. Grafana's re-renders change `message` and so `body_digest`, and coalesce. A member turning Resolved inside a refused group changes `resolved` and `members`, so it gets its own record. That lost Resolved is what the summary exists to surface; the unit-16 key `(code, source_group or refused_group or None)` would hide it. Parser-level and oversize refusals carry no group or members, so they share one key per code, as D12 intended.
- **Flood policy (rule `first-per-membership-v1`).** A key already recorded this generation is `coalesced`. After 256 records it is `limit`. A summary whose `resolved` is not a positive integer (no Resolved member, or a parser-level or group-key refusal with `resolved: null`) is also `limit` once 192 such records exist, so **64 records stay reserved for summaries that carry a Resolved member** (critic 12). If `p.logical_bytes + len(record.body) + RECORD_OVERHEAD_BYTES` for the sealed record exceeds `ordinary_bytes`, it is `no_room`. None of these writes, and each is counted per boot. No capacity hold is written: capacity codes stay admission-only. Worst case 256 × about 5 KiB, about 1.3 MiB of the 112 MiB ordinary region.
- **What the reserve does and does not protect.** It keeps a benign firing-only flood from using up the durable channel before a lost Resolved arrives. Examples are a large flapping group refused as `ingress_too_many_alerts` (a new membership about every `group_interval`), or `ingress_group_key_unsupported` keys. It does **not** stop a sender who can reach the port and mints Resolved-bearing summaries with distinct groups: 64 such posts use up the reserve. Against that sender the only real mitigation is webhook authentication, which is deferred (Deferred 8), and U17-P3 records this limit explicitly.
- **Inert, except for the byte budget** (critic 3). No admission transition reads the front-door fields, and a refusal changes no baseline, pending entry, admission count or dispatch hold. A refusal **does** advance `logical_bytes`, the budget `plan_admission` and `_verify_admission_pair` check against `ordinary_bytes`. Near that bound, adding or removing refusal records can turn an admission into a `capacity_bytes` refusal with its `capacity_hold`, or the reverse. The hold then changes `dispatch_holds` and `decision` in later admission records. Across a generation, refusals move the boundary by at most the sum of their charges: at most 256 × (`len(record.body)` + 384). That is an estimated 1.3 MiB, under 1.4 MiB, at the 4,096-byte summary bound. A7b pins the exact charge per record and prints the size of a record at that bound. The coupling is intended: the spec's 128 MiB journal bound (spec L273-275) covers every record. `restart_recovery` and `operator_action` already couple the same way, through the total region. A separate refusal byte slice outside `logical_bytes` was considered and rejected, because the journal could then exceed the spec bound by that slice.
- **Why a fixed 256, not `max(1, max_admissions // 32)`** (J2-AO-4): an invented ratio couples two unrelated bounds. The limit and the reserve are part of the rule and are versioned by the `rule` literal.

### `operator_action` (recovery class, actor `operator`, `ids` = `{}`)

The spec's own record name and fields "with actor and reason" (spec L186-187), not a new family (J1-OF-1, J2-OF-1).

| `data` key | Validator | Replay (`_verify_operator_action`) |
| --- | --- | --- |
| `action` | `"resume"` (`OPERATOR_ACTIONS`) | - |
| `rule` | `"resume-at-open-v1"`; another value is `record_unsupported` | - |
| `hold` | `"restart_recovery"` (`RESUMABLE_HOLDS`) | in `p.dispatch_holds` |
| `since_commit_seq` | int 2..2^53-1 | equals `p.dispatch_holds["restart_recovery"]` |
| `inspected` | a `dict` with exactly `{commit_seq, event_seq, record_digest}`: `commit_seq` int 1..2^53-1, `event_seq` int 1..2^53-1, `record_digest` hex64. There is no cross-field check at seal, because replay re-derives all three | equals `p.boot_recovered`: the head this boot's restart recovered, which is what the operator inspected and the token matched |
| `pending_digest` | hex64 | equals `pending_digest(p)`: exactly the pending set resumed over |
| `operator` | ID grammar `[A-Za-z0-9._-]{1,128}` | - (a self-asserted label, not authentication) |
| `reason` | ID grammar; the CLI default is `restart-inspected` | - (an operator-chosen, grammar-bounded token, for example an OPS key; never free text, plan I17) |

- **Check order.** Validator: `ids == {}`, then `data` is a `dict` containing `"rule"` (else `record_field`), then the `rule` literal (`record_unsupported`), then the exact key set, then `action`, `hold`, `since_commit_seq`, `inspected`, `pending_digest`, `operator` and `reason` in table order, each `record_field` (or `record_type` for a non-int where `_require_bound_int` says so). Replay, after the existing non-restart boot and clock checks: hold present, `since`, immediacy, `inspected`, `pending_digest`, then the total-region budget. Each failure is `replay_mismatch`.
- **Immediacy.** Replay also requires `p.head.commit_seq == p.boot_start_commit_seq`: the resume is the first commit after the restart that started its boot, and the non-restart path already requires the same `boot_id`. So nothing can be admitted between the inspected state and the resume, and `inspected`, `since` and `pending_digest` are all re-derived at replay (I20; J1 graft 1).
- **Budget.** Charged to the **total** region, like `restart_recovery`, so an operator can resume after the ordinary region is exhausted. Over total gives the process hold `journal_capacity_recovery`.
- **Effect.** `dispatch_hold_clear = "restart_recovery"`; capacity holds stay. It never lifts a durable recovery hold (spec L245; that needs reconstruction, plan Deferred 8).
- **No `state_digest` in any record** (J1-OF-7). The whole-projection formula stays free to change under its own tag.
- **Inspect is never journaled.** The spec lists `inspect` among `operator_action` values, but plan Deferred 6 and critic 14 require inspect to append nothing. What was inspected is recorded durably by the resume's `inspected` field.

### Extension rules

- **R1.** The new `(ingress_refusal, 1)` and `(operator_action, 1)` validators are frozen from this commit. Every existing `(type, 1)` validator accepts exactly the records it accepted before: the registry superset and the per-type actor table yield the old predicates for the old types (tests A2, A11). `schema_version` stays 1 everywhere; the DDL, `user_version` 1 and the anchor format are unchanged. **U17-P5** ratifies reading the four registry-driven `_validate_envelope` predicates as "not a change to the envelope" for any existing type (J1-OF-9). **The version step is designed on the reader side now** (critic 7). A record is accepted iff its `(event_type, schema_version)` pair is registered, so an online resume, cancel, retry or abandon (`operator_action`, 2), or a new ingress code (`ingress_refusal`, 2), is one registry entry with its own frozen validator and actor. No predicate is edited again. The writer side is not designed here, because no v2 pair exists to exercise it. `seal` and `content_digest` write the constant `SCHEMA_VERSION`, and `Record` has no version field, so the first v2 pair must add one (Deferred 1). Until then, a refusal whose code is outside `INGRESS_REFUSAL_CODES_V1` is `refusal_invalid` → outcome `unrecorded`, the class is still sent, and A5's parity test fails in the suite. That test is the tripwire that forces the `(ingress_refusal, 2)` step (J2-MD-3).
- **R2.** An older binary meets either new type as `record_unsupported`, because the event-type check runs before the actor check (J1-AO-7, J2-AO-3). That is the process hold `journal_schema_unsupported`, never persisted (AO p3; test K11). A newer `rule` literal does the same, and so does a `schema_version: 2` record of any registered type (test K11b).
- **R3.** Two single-record commit shapes are added.
- **R4.** The front-door fields are written only by the new types. Both new types also advance `logical_bytes`, like every record; the refusal's effect on the `capacity_bytes` boundary is stated under `ingress_refusal` and ratified with U17-P3. Two readings need ratification (**U17-P6**):
  - `operator_action` removes an entry from `dispatch_holds`, which restart and capacity share and admission reads to decide `held`. That is the intended lifecycle ("explicit lifecycle transitions", spec L188-189); the admission decision function is unchanged.
  - The boot fields are set in `apply_delta` from the existing genesis and restart deltas. No v1 verify function, record or `Delta` constructor changes; no admission transition reads them; `state_digest` excludes them.
- **R5.** Every replay input is in a record or genesis: the key and the reserve class from the summary, the limit and the reserve from the rule, the budget from genesis, and `since`, `inspected` and `pending_digest` from the projection. The token check is live-only and writes nothing.
- **R6.** The dedupe rule is unchanged. The two `rule` literals version the flood policy and the resume preconditions in the same style.
- **R7.** `members` has at most 32 items. No record carries a list of admission IDs.

### Replay compatibility and goldens

- `tests/data/recovery_journal_v1_golden.jsonl` (13 records) replays to the unchanged `_E16_*` digests through the unchanged E16 tests.
- **New golden** `tests/data/recovery_journal_v1_front_door_golden.jsonl`, built by K10's deterministic builder (`SeqIds`, `SeqClock`, `max_admissions = 64`). **14 records in 11 commits** (J1-AO-2):

  | Commit | Records | What it pins |
  | --- | --- | --- |
  | c1 | genesis | - |
  | c2 | pair: firing fixture, `admitted` | - |
  | c3 | `ingress_refusal`: `ingress_json_invalid` (`b"not json"`) | a no-group key |
  | c4 | `ingress_refusal`: `ingress_too_many_alerts`, 33 alerts, 1 Resolved | members, Resolved first |
  | c5 | `ingress_refusal`: the same group, 2 Resolved | a membership change is a new key |
  | c6 | `restart_recovery` (boot 2, no resume) | `since` = 6 |
  | c7 | pair: repeat fixture, `suppressed`, `held` | - |
  | c8 | `restart_recovery` (boot 3, `--resume`) | `since` stays 6 |
  | c9 | `operator_action`: `since_commit_seq` 6, `inspected` = c7's head | `since` differs from `inspected` |
  | c10 | pair: resolved fixture, `pending_reduced`, `decision: "admitted"` | the hold is cleared |
  | c11 | `ingress_refusal`: `ingress_too_large` (`oversize_refusal(300000)`) | the oversize key |

  Attempts that write nothing are exercised during the build and asserted: a re-render of c4 with a new `message` (coalesced) and a second invalid JSON body (coalesced). The guard pins `state_digest`, the head digest, `pending_digest` and `front_door_digest`. The rebuild compares record by record, like E16, with records before c6 compared whole. From c6 on, the comparator masks **exactly** these leaves (critic 8e): `data.wal_found.digest` in c6 and c8 (the WAL's random salt), `prev_record_digest` and `record_digest` on every record (the chain consequence), `data.recovered.record_digest` in c8, and `data.inspected.record_digest` in c9. It asserts every other leaf, including `wal_found.size`, `since_commit_seq`, `pending_digest`, every `refusal_key` and every summary. **Later units must keep replaying both goldens.**

## Journaled HTTP contract

**Listener.** One `ThreadingHTTPServer` (daemon threads), `protocol_version = "HTTP/1.1"`, with the hardening under "New modules": at most 32 connections; one monotonic `request_deadline` (10 s) per request covering keep-alive idle, request line, headers and body; `send_error`, `log_message` and `handle_error` overridden. It serves only `POST /notification` and `GET /health`; there is no operator route (J1-OF-2, J2-OF-2). Every error body, including the stdlib's own protocol errors, is `text/plain; charset=utf-8` holding one ASCII code, and every reason phrase is the fixed `HTTPStatus` phrase. No caller byte appears in either (u16 L469; probe r1a).

**Before the journal is open** (bind happens first; J1 graft 7): every POST gets **503** `journal_opening` with `Retry-After: 10`, body unread, connection closed; `/health` is 503 with state `opening`. A port conflict therefore fails before any journal write, and Grafana sees a retryable 503 during a long open (about 20 s at 10,000 admissions, plan L1424) instead of a refused connection.

**`POST /notification`, step by step** (the first matching step answers):

| Step | Condition | Status and body | Headers, connection | Durable effect |
| --- | --- | --- | --- | --- |
| a | at accept: 32 connections already open | none | closed at once; no thread | none; `connections_refused` counted |
| p | the stdlib cannot parse the request line or headers (before `do_POST`) | 400, 414, 431, 501 or 505 with the mapped code | close | none; `protocol_errors` counted |
| 0 | path is not `/notification` | 404 `not_found` | keep-alive | none |
| 1 | non-blocking acquire of the in-flight semaphore (8) fails | 503 `busy` | `Retry-After: 1`; close; body unread | none; counted |
| 2 | journal not `ready` | 503 `journal_held` or `journal_closed` | `Retry-After: 10`; close; body unread | none |
| 2b | spool latched | 503 `spool_broken` | the same | none |
| 3 | any `Transfer-Encoding`, or no `Content-Length` (raw headers via `get_all`; AO p2 shows the stdlib accepts both) | 411 `http_length_required` | close | none; counted |
| 4 | more than one `Content-Length`, a value not `[0-9]{1,16}`, or above 2^53-1 | 400 `http_content_length_invalid` | close | none; counted |
| 5 | declared length above 262,144 | 413 `ingress_too_large` | close, **without reading** (u16 Deferred 1; the drain is cut, J1-AO-4) | `record_refusal(refusal_to_json(oversize_refusal(n)))` |
| 6 | read exactly n bytes through the deadline reader; the request deadline passes or EOF comes first | 400 `http_body_incomplete`, best effort | close | none; `http_body_incomplete` counted, and `deadline_exceeded` too when the deadline passed |
| 7 | `sanitize_notification(body)` refuses | `INGRESS_HTTP_STATUS[code]` (400, 422 or 500) with the code | keep-alive | `record_refusal(summary)`; never `admit` (u16 N12 b) |
| 7b | `journal.admission_precheck()` returns `capacity_admissions` (critic 6) | 503 `capacity_admissions` | `Retry-After: 10`; keep-alive | none: **nothing is spooled**; counted under `backpressure` |
| 8 | `spool.store(body, source.body_digest)` raises | 503 `spool_full`, `spool_conflict` or `spool_write_failed` | `Retry-After: 10`; keep-alive | none in the journal; the last two latch the spool |
| 9 | `journal.admit(source)` raises `JournalError` | 503 with the code (`journal_held`, `journal_closed`, the three capacity codes, `journal_write_failed`, `journal_clock_invalid`, `journal_divergence`, `journal_capacity_recovery`); 500 `source_invalid` (unreachable, u16 N3) | 503s carry `Retry-After: 10`; keep-alive | the first capacity refusal per code writes its `capacity_hold`; write, clock and divergence faults latch a process hold |
| 9b | any other exception from steps 0-9 | 500 `receiver_error` | close | logged with the exception type name only; an exception that escapes the handler anyway reaches the server's `handle_error`, which logs the type name only |
| 10 | receipt | **202** `application/json` `{"admission_id", "arrival_seq", "commit_seq", "decision", "dispatch_holds", "result", "run": "not_dispatched"}` | keep-alive | spool entry (if new) durable **before** the admission pair and its anchor |

Notes:
- **Refusal recording never changes the class.** A 4xx is not an acknowledgement, so it needs no durable record to be sent. If `record_refusal` raises (held, or a write fault that latches), the code is logged, the outcome is counted `unrecorded`, and the refusal's class is still sent. `starts_at_dropped` is counted per boot and not persisted (Deferred).
- **The 422 policy is "422 and stay refused, recorded durably"** (U17-P12). A 202 would claim an admission the v1 record cannot hold; the alternative "record, hold, 202" waits on the resend hypothesis (u16 L465-467).
- **Concurrency.** Framing, reading, sanitizing and spooling run in parallel handler threads; the spool lock serializes spool writes and the journal lock serializes `admit` and `record_refusal`, so arrival order is journal-lock order. About 40 ms of spool sync plus 44-62 ms of admit per new body on this Mac (AO p1, p4).
- `Expect: 100-continue` is answered by the stdlib before step 1, so a client may start sending a body that step 1, 2 or 5 then leaves unread. For bodies above about 1 MB the client may see a reset instead of the response (AO p2); Grafana's bodies are at most 9,333 B in the captures. On macOS, a no-read 503 with a full 2,611-byte to 256 KiB body already sent reached a urllib client 500 times out of 500 (critic probe c1a). On Linux, closing with unread data can send RST first. That case is unprobed and listed under "Not qualified".
- **Bounded work, stated exactly** (critic 2). Each connection is bounded by the 10 s deadline per request; there are at most 32 connections and handler threads, and at most 8 POSTs past step 1. A client that trickles, or that sits idle, loses its connection at the deadline whatever its byte rate. What stays open is availability: a peer that holds 32 connections and reconnects every 10 s can keep Grafana's POSTs refused at accept. There is no per-peer limit and no authentication (residual risk; Deferred 8).

**`GET /health`** (`application/json`, `Cache-Control: no-store`). **200 iff the journal is `ready` and the spool is not latched**, meaning the process accepts writes; otherwise 503 (critic 10). The status does **not** claim that a new body can be admitted. After `capacity_admissions`, a full spool, or `capacity_pending` or `capacity_bytes`, new bodies are refused while health stays 200. Those conditions show in the body (`dispatch_holds`, `spool.full_refusals_this_boot`, `http.backpressure`), as in the journal's own model, where capacity codes are dispatch holds and not process holds. H19 pins this rule. Fixed, nonsecret shape; projection fields are null unless ready; it never lists a Fingerprint, a pending entry, a head digest or a token:

```
{"mode": "journaled-admission-only", "runs": "not_dispatched",
 "journal": {"state": "opening|ready|held|closed", "hold": null | {"code", "scope", "persisted"},
             "dispatch_holds": [codes] | null, "head_commit_seq": n | null,
             "admissions": n | null, "pending_fingerprints": n | null},
 "resume": {"this_boot": "resumed" | "not_requested" | "not_applied"},
 "refusals": {"recorded": n | null, "limit": 256, "reserve": 64,
              "this_boot": {"<code>": {"recorded", "coalesced", "limit", "no_room", "unrecorded"}}},
 "http": {"busy", "http_length_required", "http_content_length_invalid", "http_body_incomplete",
          "in_flight": n, "connections_open": n, "connections_refused": n, "deadline_exceeded": n,
          "protocol_errors": {"<code>": n},
          "backpressure": {"<code>": n}, "admitted": {"<result>": n}, "starts_at_dropped": n},
 "spool": {"state": "ok" | "broken", "code": null | "<code>", "bytes", "max_bytes", "entries",
           "max_entries", "written_this_boot", "full_refusals_this_boot"}}
```

`in_flight` (at most 8) and `connections_open` (at most 32) are gauges, and tests read them in process through `health()` (H11, H11b). A health request counts toward `connections_open` like any other.

Every map is keyed by a closed code set, so memory is bounded.

## Operator entry points

| Entry point | Needs | Writes |
| --- | --- | --- |
| `journal_operator create --state-dir S` | nothing running | `S`, `S/spool`, `S/journal` and genesis: syncs `S.parent` after `mkdir S`, and `S` after both subdirectories exist, then the journal's 4 syncs, as unit 15 |
| `journal_operator inspect --state-dir S` | the journal lock (the front door must be stopped; exit 3 otherwise) | **nothing**, except an absent empty `lock` (see below) |
| `journaled_receiver --state-dir S` | an existing `S` | each start: re-anchor at lag 1 and `restart_recovery`, or a persisted recovery verdict (unit-15 open); then spool files, admissions, refusals |
| `journaled_receiver … --resume-token T --operator NAME` | a token from inspect of the unchanged journal | as above, plus exactly one `operator_action` immediately after the restart. A stale token writes **nothing** to a WAL-present image and exits 1 (see V10 for WAL-absent images). A held open writes what any held open writes and exits 1 `resume_not_applied` |

**Verify-only inspect: `inspect_recovery_journal(directory) -> Inspection`.**
1. **WAL pre-check** (J1 graft 3; critic 9). `(directory / WAL_FILENAME).lstat()`, and if the WAL is absent, `(directory / DB_FILENAME).lstat()` too.
   - WAL absent, and the DB absent or shorter than `PAGE_SIZE`: **open the store anyway** (step 2). `_verify_open` returns at an anchor finding, a persisted anchor hold or `journal_truncated`, in that order, and all **before** it connects (journal_store.py L817-826), so no WAL can be created. The report shows the real `held` verdict.
   - WAL absent and the DB at least `PAGE_SIZE`: **do not open SQLite**. Return `verdict: "unverified"`, `reason: "wal_absent"`, `next_open: ["unknown"]`, because opening could create an empty WAL and change the next restart's `wal_found` (J1 p1, p2). The operator starts the front door once, stops it and inspects again. That start's open records `wal_found: null` exactly as it would without the inspect. If its store connects, the WAL now exists and the second inspect is WAL-present. If it returns at an anchor finding or a persisted anchor hold before connecting, the front door is held and `/health` shows that hold code. The runbook (step 4 of "What an operator sees") makes that code the verdict, so the loop ends after one start in every case.
2. `JournalStore.open(directory)`. It takes the flock and creates an absent `lock`, which the report lists in `created`; no record or digest reads the lock (probe s1). Store codes become `JournalError`s: `journal_locked`, `journal_missing`, `journal_permissions`, `journal_path_invalid`, `sqlite_unsupported`.
3. The pre-check and the store's connect are not atomic. A WAL deleted by another process in between is outside the model, as a same-uid forger already is (docs "Crash windows"); nothing in this unit deletes it or would repair it.
4. `_replay_finding(store, candidate, observe=collect)`: the same verification and replay a normal open runs. `collect` gathers each admission's `body_digest`, the last 32 refusal summaries with their `commit_seq`, and the last resume. What `collect` holds is only a candidate. It is **discarded** unless replay ends with no finding, because the spec forbids applying a verified prefix (spec L242; critic 8a).
5. **Never** `finish_open` (so `query_only` stays on), `write_anchor`, `persist_hold`, `plan_restart` or `append`. Everything after the store opens in step 2 runs inside `try: … finally: store.close()`, and `close` never checkpoints (plan I3). An exception raised by `observe` is a programming error: it propagates unchanged after the `finally` has closed the store (critic 8b).

`Inspection.report` has a closed shape (JSON, nonsecret by construction):

```
{"mode": "verify_only", "verdict": "ready" | "held" | "unverified", "reason": null | "wal_absent",
 "created": [] | ["lock"],
 "finding": null | {"code", "scope", "in_anchor"},
 "anchor": null | {"counter", "commit_seq", "event_seq", "lag"}, "wal_found": null | {"size", "digest"},
 "next_open": ["restart_recovery"] | ["reanchor", "restart_recovery"] | ["persist_hold"] | ["hold"] | ["unknown"],
 "journal": null | {"journal_uuid", "generation", "head": {"commit_seq", "event_seq", "record_digest"},
                    "dispatch_holds": [{"code", "since_commit_seq"}], "counts", "bytes", "bounds",
                    "pending_digest", "state_digest", "front_door_digest"},
 "pending": null | [{"fingerprint", "status", "values", "admission_id", "arrival_seq", "source_group"}],   # <= 1,024
 "refusals": null | {"recorded", "limit", "reserve", "unreserved_recorded",
                     "recent": [{"commit_seq", "summary"}]},                                               # <= 32
 "resumes": null | {"count", "last": null | {"commit_seq", "operator", "reason", "inspected_commit_seq"}},
 "resume": null | {"token": "<head record_digest>", "head_commit_seq": n}}
```

**Null rule** (critic 8a). For any verdict other than `ready`, `journal`, `pending`, `refusals`, `resumes` and `resume` are all `null`, and `Inspection.references` is empty, even when replay verified a prefix before its finding. `finding`, `anchor`, `wal_found` and `next_open` describe the image itself and are filled whenever they are known. `next_open` is `persist_hold` for a recovery finding (`finding.in_anchor` says whether the anchor already carries it), `hold` for a process finding (the next open writes nothing), and `unknown` when unverified. `Inspection.references` is the admitted `body_digest` set; `journal_operator` adds `"spool": survey_spool(S/spool, references)` when the verdict is `ready`, and `null` otherwise.

**Resume at open.** The token is the inspected head's `record_digest`, which chains the whole history (probe s1: it equals the next restart's `recovered.record_digest` at lag 0 and lag 1). It is a staleness binding, not authentication: anyone who can read `S` can compute it, and the `operator` label is self-asserted (spec L343 leaves operator authentication syntax unchosen). Health never shows the token, so skipping inspect takes deliberate effort. Because resume happens during open, before the listener admits anything, there is no online write surface and no compare-and-set race (J1-AO-6). Each resume costs a stop and a start (J2-OF-8). If the open returns a held handle, the resume was not applied, and `start()` stops the listener, closes the journal and raises `resume_not_applied`. `main` exits 1 with that code; the listener is already released (critic 8c).

## Crash windows added by this unit

The journal's own windows (docs "Crash windows") are unchanged.

| # | Window | Durable state | Next `inspect` / start | Sender sees |
| --- | --- | --- | --- | --- |
| W1 | reading headers or body | nothing | unchanged | no response; a retry is admitted anew (spec L251) |
| W2 | spool temp written, before `rename` | a `.tmp-*` | `temporaries: 1`; never deleted | no response; a retry writes a new temp |
| W3 | renamed, before the directory sync | the entry may not survive power loss | if it survived: an orphan | a retry verifies it (and syncs the directory) or rewrites it |
| W4 | spool durable, admission commit not durable | an orphan | ready; orphan listed | no response or 503; a retry is admitted, reusing the entry |
| W5 | admission committed, anchor not synced | lag 1; entry referenced | adopted, re-anchored, `restart_recovery` | a retry is `suppressed`, `held` (spec L252) |
| W6 | anchored, before the 202 | the admission | `restart_recovery` | ACK lost; a retry is `suppressed`: the ACK is idempotent |
| W7 | after the 202 | the admission | pending retained and held (spec L253) | nothing further |
| W8 | capacity refusal after the spool write | an orphan plus at most one `capacity_hold` per code. For `capacity_admissions`, only the refusal that writes the hold leaves an orphan, because step 7b stops later ones before the spool. `capacity_pending` and `capacity_bytes` can leave one orphan per distinct refused body, bounded by the spool's entry and byte caps | orphans listed, never deleted | 503 capacity code |
| W9 | refusal commit not durable | nothing | unchanged | a retry is refused and recorded |
| W10 | refusal durable, before the 4xx | one `ingress_refusal` | restart | a retry is refused and coalesced |
| W11 | after the start's `restart_recovery`, before `operator_action` | restart committed | held; the old token is stale (head moved) | the operator re-inspects |
| W12 | `operator_action` committed, anchor not synced | lag 1 | adopted, then a **new** `restart_recovery`: held again | as W11 |
| W13 | `--resume-token` stale | **unchanged** on a WAL-present image. On a WAL-absent image with the DB at least `PAGE_SIZE`, the store's connect creates an empty WAL before the token can be checked (K3b) | unchanged, except that a WAL-absent image now has an empty WAL, so the next open's `wal_found` is `{size: 0}`, not `null` | exit 1 `resume_stale`; no admission window opened |
| W14 | during inspect | unchanged; the kernel releases the flock | unchanged | - |
| W15 | spool write or sync fails while running | nothing committed; spool latched | the restart clears the latch; a temp or orphan may be listed | 503 `spool_write_failed`, then `spool_broken` |

**Ordering invariant.** The spool entry and its directory entry are durable before the admission commit, which is durable before the 202. An orphan exists only for a request that was never acknowledged. A referenced entry missing later means external deletion, which inspect reports loudly (exit 5).

Operator-first's window W14, "port bind fails after the open, leaving an extra `restart_recovery`", cannot occur here, because the listener binds first.

## Invariants

Each has a test.
- **V1. No 202 without a durable admission receipt**, written only after `admit` returns (spec L193-196; ADR12 L27; plan I1). H1, H2, C2.
- **V2. No admission without a durable spool entry**: file and directory synced before `admit` is called (plan Deferred 2; u16 Deferred 2). S1, H2, C1.
- **V3. Journaled mode starts no Run**; no spawner, Forwarder or subprocess module is imported or constructed (spec L197-203, L254). L3, H1.
- **V4. Refusals are never admitted; their bodies are the code only**, with the class from `INGRESS_HTTP_STATUS` (u16 class rule; N12 b). H5, H15.
- **V5. At most one `ingress_refusal` per flood key and at most 256 per generation, of which at most 192 carry no Resolved member, within the ordinary budget**; everything else is counted per boot (u16 D12, U16-P16/P17; spec L278-279). A7, A7b, H5.
- **V6. A held, closing or opening journal answers every POST with 503 and `Retry-After`, without reading the body** (plan Deferred 2; spec L195-196). H7, H18.
- **V7. Every `JournalError` from `admit` is 503 with `Retry-After`, except `source_invalid` (500)** (spec L211-212). H8, H9.
- **V8. Restart always re-holds**: every open appends `restart_recovery`, so no resume survives a restart (spec L32-33, L260-263; plan I11; ADR12 L27). A8, H3, C5.
- **V9. Resume is narrow and bound**: only at open, only `restart_recovery`, immediately after the restart, bound by replay to the inspected head and pending set; durable recovery holds are never lifted (spec L245, L297-302; ADR12 L35). A8, K2-K5.
- **V10. A refused resume writes nothing to a WAL-present image**: malformed before the store opens, stale before `finish_open` (J1 graft 1). On a WAL-absent image, a stale-token start creates only an empty WAL, through the store's connect, and nothing else. Inspect never issues a token for such an image (critic 9). K3, K3b, H4, O6.
- **V11. Inspect writes nothing and creates no WAL**: no database, WAL or anchor byte, no persisted verdict; an absent `lock` is the only file it may create, and it reports that; a WAL-absent image with a full-size DB is reported unverified without opening SQLite; one whose DB is absent or short is opened, because the store returns before connecting. Inspect-then-open equals open on twin images (plan Deferred 6; critic 14; plan I3). K6, K7, O4.
- **V12. Legacy identity**: the files in the contract are byte-identical, the legacy import graph loads no journal module or `sqlite3`, and the new modules read no environment (user decision). L1-L4 and the validation diff.
- **V13. v1 compatibility**: existing `(type, 1)` validators accept exactly the same records; the v1 golden replays to the same digests; `state_digest` is unchanged; older binaries meet new records only as process holds, and this binary meets a `schema_version: 2` record of any registered type the same way (R1, R2; plan I25). A2, A9, K11, K11b, existing E16.
- **V14. Custody**: no raw body, header or caller byte reaches the journal, a response (status line and reason phrase included, and the stdlib's own protocol errors included), `/health`, a log line or stderr; raw bodies exist only in the 0600 spool inside the 0700 state directory (spec L156-159; ADR12 L25; plan I17). H15, S6, K12.
- **V15. Nothing is deleted**: no deletion call in the new modules; orphans are identified, not removed. S9.
- **V16. Bounded work**: at most 262,144 body bytes read per request; at most 32 connections, with the excess closed at accept and no thread started; at most 8 POSTs in flight; one 10 s monotonic deadline per request, covering keep-alive idle, request line, headers and body, whatever the client's byte rate; a spool capped at 256 MiB and 20,000 entries; bounded counters, gauges, verified-digest set and reports (spec L275-279; u16 D2). This is bounded work, not guaranteed availability (see "Bounded work, stated exactly"). H11, H11b, H14, H14b, S5.
- **V17. Ordering**: spool before admission before 202; refusal record attempted before the 4xx; the resume commit before the listener admits. S1, C1-C5.
- **V18. One decision function**: the live and replay paths share `plan_*` and `_verify_*` for both new types (plan I20). A7, A8, A11.
- **V19. Latched spool failure is sticky until restart**; a sync is never retried. S3, S4, H10.
- **V20. The state directory and `runs_directory` never contain each other** (plan Deferred 2). H16.
- **V21. Explicit create only**: no front-door path creates `S`, the journal or the spool (plan I21; spec L262-263). O8, H16.
- **V22. Bind before open**: no journal file is touched when the listener cannot bind. H18.
- **V23. Durable layout**: `create` syncs `S.parent` after `mkdir S`, and `S` after both subdirectories exist, before genesis is written, so an acknowledged admission never outlives its directory entries (critic 13). O1.
- **V24. No spool write for a certain refusal**: once `capacity_admissions` is a dispatch hold, no new body is spooled (critic 6). H9b.

## Ownership and validation

Four owners work on disjoint files. Testers start from this plan's signatures and do not wait for the implementation. Tests never write repository files, never bind a fixed port (every server binds `127.0.0.1:0`; child processes take `--port 0` and print `listening on http://127.0.0.1:<port>`, which the parent parses), and print timings rather than assert them. Where a test must wait, it polls an in-process gauge or counter, never a sleep. An outcome that needs a time bound gets a generous one (5 s) that only catches a hang. Every random choice is seeded, and the seed is printed (critic 5).

**Implementer A** owns the three journal-module changes and `tests/test_journal_front_door_records.py` (pure; projections built by replaying planned records, no store):
- **A1.** Known answers: one sealed `ingress_refusal` and one `operator_action` with fixed IDs and stamps, canonical bytes and `record_digest` pinned; `open_record` round-trips.
- **A2.** Per-(type, actor) table over 7 types × 4 actors: accepted iff `actor == TYPE_ACTORS[(type, 1)]`; the five v1 rows are exactly `{receiver}`; an unknown type with actor `operator` is `record_unsupported`. `EVENT_TYPES` equals the unit-15 tuple; `RECORD_CLASS` covers exactly `REGISTERED_EVENT_TYPES`; `TYPE_ACTORS` and `_TYPE_VALIDATORS` have exactly the keys `{(t, 1) for t in REGISTERED_EVENT_TYPES}`; `SCHEMA_VERSIONS == {1}`. For every registered type, a `schema_version` of 0, 2 or 2^53-1 gives `record_unsupported` **before** a deliberately invalid `journal_generation` is looked at, which pins the check position.
- **A3.** Validator rejections, through `seal` and through `decode_record`: each missing or extra key; an unknown `rule` (`record_unsupported`, even with the other keys wrong); `refusal_seq` 0 and 257 (`record_field`) and `"1"` (`record_type`); the unit-16 sixteen forgeries translated to data (`record_field`); `members` as lists (`record_field`: the strict `_check_refusal_summary` accepts tuples only); a summary over 4,096 bytes; `operator_action` with action `cancel`, a 129-character `operator`, a space in `reason`, `since_commit_seq` 1, and `inspected` with an extra key, a missing key, `commit_seq` 0 or 2^53, or a 63-character digest.
- **A4.** Summary parity: every refusal `sanitize_notification` produces over the unit-16 corpus and adversarial generators (importing `capture_rows`, `wire` and `grafana_group` from the unit-16 tests), plus `oversize_refusal` at 262,145 and 2^53-1, passes `refusal_to_json` and `refusal_summary_data` alike; the forgeries fail both.
- **A5.** Constant parity with `journal_ingress` (codes, member codes, no-group codes, bounds) and `journal_source` (`ALERT_STATUSES`, `MAX_ALERTS`), and `256 == forwarder_json.MAX_JSON_ARRAY_ITEMS`.
- **A6.** The normalizer and the checker, tested separately (critic 4). `refusal_summary_data` accepts the raw `refusal_to_json` output (lists), returns tuples, is idempotent on its own output, and raises `record_field` wherever `_check_refusal_summary` does. `_check_refusal_summary` accepts the normalized dict and rejects the raw one. `record_refusal`'s in-memory `Record.data` equals `open_record(record.body).data`.
- **A7.** Refusal reducer: two re-renders give one key; one member resolving gives a new key; `coalesced`, including after the limit; the 257th distinct key is `limit`; the 193rd distinct key without a Resolved member is `limit` while a key with one is still recorded, up to 256; with a tiny `ordinary_bytes` at genesis, `no_room`, computed as `len(record.body) + RECORD_OVERHEAD_BYTES` on the sealed record. `verify_commit` rejects each of the following with `replay_mismatch`: a wrong key, a repeated key, a skipped `refusal_seq`, a record over the limit, an unreserved record past 192, and one over the ordinary budget. It rejects a foreign boot with `replay_boot`. An F1-style leaf-mutation matrix has as its only type-valid survivors `summary.body_bytes` and `summary.body_digest` within their cross-field rules.
- **A7b.** The byte coupling, directed (critic 3). A dry run with the same deterministic IDs and clocks measures `logical_bytes` before the refusal, and both charges from the sealed records. A fresh build then uses a genesis whose `ordinary_bytes` is exactly `logical_bytes + refusal_charge + admission_charge - 1`, and asserts that the measured charges repeat. With the refusal committed, the admission is a `capacity_bytes` refusal and writes its `capacity_hold`. Without the refusal, the same admission is admitted. With one byte more of `ordinary_bytes`, both are recorded. Separately, seal a refusal whose summary is at the 4,096-byte bound and print `len(record.body) + 384` × 256.
- **A8.** Resume reducer: accepted right after a restart; `replay_mismatch` for no hold (genesis boot), an admission between restart and resume, a second resume in one boot, and a wrong `since`, `inspected` or `pending_digest`; accepted with the ordinary region exhausted but the total not; the delta clears only `restart_recovery`; the next restart re-adds it with its own `since`.
- **A9.** Property over 200 seeded histories (seed printed) of admissions, restarts, `capacity_admissions` and `capacity_pending` refusals, refusals and resumes. `boot_recovered` equals the latest restart's `recovered`; `boot_start_commit_seq` equals the latest genesis or restart commit; `state_digest` and `pending_digest` equal a frozen copy of the `b931610` formulas held in the test. **The removal clauses hold only where `capacity_bytes` is unreachable** (critic 3). The generator sets `ordinary_bytes` and `total_bytes` to the v1 ceilings, and it asserts the precondition on every history: the full history's final `logical_bytes` is below `ordinary_bytes` minus the largest admission charge, so no history, with or without its refusals and resumes, can refuse with `capacity_bytes`. Under that precondition, removing every refusal record leaves every admission record's `ids` and `data` equal (only position, stamp and chain fields move), and removing resumes changes only `decision` and `dispatch_holds` (J2 graft 6, restated so it can pass; J1-OF-3). The byte boundary itself is A7b's job, not A9's.
- **A10.** `front_door_digest` known answers; it changes with a refusal or a resume and is constant over admission-only histories.
- **A11.** plan → seal → `verify_commit` → `apply_delta` round trips for both new plans equal the live projection (I20).
- **A12.** AST: the reducer still has no `try`; new `except` bodies in records and shell only assign or pass.

**Implementer B** owns the three new modules and `tests/test_journal_spool.py`:
- **S1.** `store` writes a 0600 entry named by the digest with exact bytes; with `full_sync` recording calls, the order is file sync, rename, directory sync, return `"written"`.
- **S2.** The same body again is `"present"` with no I/O; a fresh instance content-verifies a pre-existing entry once and syncs the directory.
- **S3.** A pre-existing entry with other bytes gives `spool_conflict`, latches, and stays byte-identical; later calls give `spool_broken`.
- **S4.** An injected file-sync failure gives `spool_write_failed` with no final-name entry (the temp remains), and latches.
- **S5.** Over the byte cap, and separately over the entry cap (`max_entries = 3` with a temporary and an unexpected name counted): `spool_full`, nothing written, not latched; a present body is still `"present"` at either cap; `status()` reports `entries` and `max_entries`.
- **S6.** Custody: a symlinked directory, 0755, a missing directory (`spool_missing`), a symlinked entry, an entry with two links, a 0644 entry; error `args` never contain a path or bytes.
- **S7.** `spool_argument` for a digest mismatch, `bytearray`, `str`.
- **S8.** `full_sync` platform selection equals `journal_store._full_sync` (read-only comparison); an unknown platform gives `spool_sync_unsupported`.
- **S9.** `survey_spool` counts orphans, missing, mismatched, mismatched orphans (an orphan whose bytes were rewritten, and a symlinked orphan), temporaries and unexpected names, lists at most 32 of each, and leaves the tree hash unchanged. A mismatched orphan named by the survey latches `spool_conflict` when `store` meets its digest, so the survey predicts the latch. AST: no `unlink`, `remove`, `rmdir`, `rmtree` or `truncate` anywhere in `journal_spool.py`, `journaled_receiver.py` or `journal_operator.py`.
- **S10.** `sync_directory` opens with `O_DIRECTORY | O_NOFOLLOW`, full-syncs and closes, and a regular file or a symlink gives `spool_write_failed`. With `full_sync` recording calls, it syncs the directory's own descriptor.

**Tester T1** owns `tests/test_recovery_journal_front_door.py` and the new golden:
- **K1.** `record_refusal` returns each outcome with per-boot counters; `refusal_invalid` for a malformed summary latches nothing; a clock fault latches `journal_clock_invalid`; held gives `journal_held`; `snapshot()` keeps its 16 keys and capacity-only `refusals_this_boot` with refusals present.
- **K2.** Resume at open: create, admit, close, inspect (take the token), open with `resume` → the last two records are `restart_recovery` then `operator_action`; `dispatch_holds` lacks `restart_recovery`; the next admit is `decision: "admitted"`; `resumed_this_boot` matches the record.
- **K3.** On a WAL-present image, a stale token raises `resume_stale` and every file hash is unchanged. A malformed token, `operator` or `reason` raises `resume_invalid`, and not even `lock` is touched.
- **K3b.** On a WAL-absent image whose DB is at least `PAGE_SIZE`, a stale token raises `resume_stale`. DB and anchor hashes are unchanged, and the only change is an empty WAL. The next plain open records `wal_found: {size: 0, …}` (critic 9). This pins V10's qualification.
- **K4.** Resume against a held image: the recovery verdict is persisted as today, no `operator_action` exists, `resumed_this_boot` is `None`.
- **K5.** A clock fault during the restart latches it; no resume is attempted.
- **K6.** Inspect on eleven images: ready at lag 0; lag 1; a recovery finding not yet persisted; a persisted hold; a process finding (`user_version = 2`); lock-absent; WAL-absent (checkpointed); WAL removed with the anchor ahead; **a persisted hold with no WAL**; **the DB unlinked with no WAL**; and **a torn WAL tail**, where the WAL is truncated partway through the last commit's final frame, as SIGKILL mid-append leaves it (critic 9). Each reports its verdict and `next_open`; DB, WAL and anchor hashes are unchanged; only the lock-absent image gains `lock`. The checkpointed and WAL-removed images are `unverified` and gain no file. The DB-unlinked image is opened, per the pre-check rule, and reports `held` `journal_truncated` with no WAL created. The persisted-hold image with no WAL is `unverified`. `open_recovery_journal` on its twin returns a held handle with the persisted code and creates no WAL; the runbook takes that code as the verdict, and H7b shows the same through `/health`. A second inspect after that open is still `unverified`. The test pins this, so the runbook rule stays necessary. For the torn tail, K6 asserts whatever verdict the unchanged unit-15 open gives, and K7 asserts that inspect did not change it.
- **K7.** Neutrality (J1-AO-1): each K6 image is copied to twins A and B; A is inspected; both are opened with identical injected clocks and IDs; the stored row sequences and anchor slot bodies are equal, and the next open does what `next_open` said.
- **K8.** Inspect while a handle is open gives `journal_locked`; the report is JSON with its closed shape and carries no canary (F4 technique).
- **K9.** `observe` sees each verified group exactly once; `references` equals the admitted `body_digest` set; `recent` holds at most 32 summaries, newest last. On an image whose last commit fails replay (a forged row appended with a valid digest and chain), the report has `journal`, `pending`, `refusals`, `resumes` and `resume` all `null`, and `references` is empty, although `observe` saw earlier groups. An `observe` that raises propagates its exception, and the lock can be taken again at once, which shows the store was closed.
- **K10.** Front-door golden guard and builder: pinned digests; the rebuild compares every leaf except the five masked leaves listed under "Replay compatibility and goldens"; coalesced attempts during the build write nothing.
- **K11.** Rollback (R2): with `jr._TYPE_VALIDATORS` and `jr.TYPE_ACTORS` monkeypatched to their five `(v1 type, 1)` entries (the older binary's registry), a journal whose first new row is a refusal, and separately one whose first is a resume, opens as the process hold `journal_schema_unsupported`, `persisted` false, bytes unchanged; restoring opens ready.
- **K11b.** This binary against a future version (critic 7). The last row of a journal is replaced by a hand-built, digest- and chain-valid `schema_version: 2` record. The test runs once for each single-record type: `restart_recovery`, `capacity_hold`, `ingress_refusal` and `operator_action`. The admission pair and genesis are covered by the existing record-level case at `test_journal_records.py` L449. Each run opens as the process hold `journal_schema_unsupported`, `persisted` false, bytes unchanged. Inspect reports `held` with `next_open: ["hold"]`.
- **K12.** An F3-style closed-grammar audit over a journal holding all seven types.
- **K13.** In-process crash images with `SimulatedCrash(BaseException)`: after the refusal append (W10: one record, a re-send coalesced); after the start's restart commit (W11: stale token); resume commit with the anchor write failing (W12: lag 1, then held).
- **K14.** Concurrent `admit` and `record_refusal` threads serialize; arrival sequences are contiguous.

**Tester T2** owns `tests/test_journaled_receiver.py`, `tests/test_journal_operator.py`, `tests/test_journaled_receiver_crash.py` and `tests/test_journaled_legacy_identity.py`. Fixture `front_door`: `create_state(tmp/"S", bounds=…)`, `JournaledReceiver(tmp/"S", runs_directory=tmp/"runs", port=0, …)`, `start()`. It imports `http_request`, `post_notification`, `get_health` and `FIXTURES` from `tests.conftest` read-only (`post_notification` only needs `.url`).

**Admission-only mode pins** (critic 7). The assertions that exist only because this unit starts no Run are collected in test functions named `test_admission_only_mode_*`. They are: H1's `tmp/"runs"` and `Popen` checks, H19's `mode` and `runs` values, H20's `run == "not_dispatched"`, and L3's fresh-interpreter check for `journaled_receiver`. The lifecycle unit supersedes exactly that named set by a reviewed edit its own plan declares. Every other assertion in these files must survive dispatch unchanged.
- **H1.** `replay(front_door.url, pause=0) == [202, 202, 202]`; results admitted, suppressed, pending_reduced, each `decision: "held"`; 2 spool entries equal to the fixture bytes; `tmp/"runs"` never exists; a monkeypatched `subprocess.Popen` that raises is never called; after `stop`, inspect shows pending `87e2f184874a3b71` resolved.
- **H2.** A spy on `JournalStore.append` asserts at call time that the spool entry exists with exact bytes; after the 202, stop and inspect show the admission.
- **H3.** Resume flow: serve, POST, stop, inspect, serve with `resume`: health `resume.this_boot: "resumed"`, holds `[]`; the next POST is `admitted`; a restart without resume re-holds.
- **H4.** Stale token: inspect, serve without resume, stop, serve with the old token: `start()` raises `resume_stale`, the tree hashes are unchanged, and the port is released.
- **H5.** Refusals over HTTP: `b"not json"` → 400 `ingress_json_invalid`; 33 alerts with one Resolved → 422 `ingress_too_many_alerts`; a non-ASCII `groupKey` → 422; a declared 300,000 bytes with no body sent (raw socket) → an immediate 413, the connection closed, one durable `ingress_too_large`; an injected `ingress_divergence` → 500. Every body equals its code. A re-render is coalesced; one member resolving is a new record; inspect lists the summaries Resolved first.
- **H6.** Framing on raw sockets: chunked, no `Content-Length`, and `Content-Length` with `Transfer-Encoding` → 411; a duplicate `Content-Length`, `12a`, `-1`, 17 digits, 2^53 → 400; each closes, and the journal head is unchanged.
- **H7.** Held at start (DB unlinked; persisted `journal_truncated`): a POST sending headers only gets an immediate 503 `journal_held` with `Retry-After: 10`; health 503 with `{"code": "journal_truncated", "scope": "recovery", "persisted": true}`; the spool tree is unchanged. **Full-body case** (critic 5): a urllib POST of the 2,611-byte firing fixture, like `replay`, gets the 503 with `Retry-After: 10`. This case is darwin-only and a declared skip on other platforms, because a no-read close can send RST on Linux (critic probe c1a; "Not qualified").
- **H7b.** A persisted hold with no WAL (K6's image): the front door starts held, `/health` is 503 with the persisted code, and no WAL is created. This is the runbook's "the code on `/health` is the verdict" (critic 9).
- **H8.** A failing wall clock → 503 `journal_clock_invalid`, then `journal_held`; health 503.
- **H9.** `max_admissions = 2`: the third distinct body → 503 `capacity_admissions`; one `capacity_hold`; its spool entry exists and inspect lists it as an orphan.
- **H9b.** After H9, a fourth distinct body, and the third again, each get 503 `capacity_admissions` with `Retry-After: 10`. The spool's entry count and tree hash are unchanged, and the journal head is unchanged. `http.backpressure.capacity_admissions` counts them. Inspect still lists exactly one orphan (critic 6).
- **H10.** A failing spool sync → 503 `spool_write_failed` with the journal head unchanged; then `spool_broken`; health 503 with the spool code.
- **H11.** `max_in_flight = 1` and `request_deadline = 30`: a raw socket stalled mid-body holds the slot. The test polls the in-process `front_door.health()` until `http.in_flight == 1` (a 5 s bound), and only then sends a second POST. That POST gets 503 `busy` with `Retry-After: 1`, and health stays 200. There is no race (critic 5).
- **H11b.** `max_connections = 2` and `request_deadline = 30`: two idle raw sockets are opened, and the test polls `health()` until `http.connections_open == 2`. A third socket then reads EOF with no response bytes within 5 s. `connections_refused == 1`, and `threading.active_count()` grew by at most 2 handler threads. After the two idle sockets close, the test polls until `connections_open == 0`, and a POST is admitted (critic 2).
- **H12.** 8 threads post 8 distinct bodies: 8 × 202, contiguous `arrival_seq`, 8 spool entries, and `pending_digest` equal to inspect's independent replay.
- **H13.** `GET /notification`, `POST /other`, `GET /x` → 404 `not_found`.
- **H14.** `request_deadline = 1.0` and a body that stops halfway: the connection is closed, nothing is admitted, and `http_body_incomplete` and `deadline_exceeded` are counted. The only time assertion is a 5 s bound that catches a hang; the elapsed time is printed (critic 5).
- **H14b.** `request_deadline = 1.0` and a body trickled one byte every 0.1 s, so that no single `recv` ever waits long: closed with 400 `http_body_incomplete`, nothing admitted, `deadline_exceeded` counted, all within the 5 s bound, with the elapsed time printed. A second case trickles the **headers** the same way: closed with no response, `deadline_exceeded` counted (probe r1b; critic 2).
- **H15.** Canaries in `message`, labels, annotations, a non-ASCII `groupKey` and grammar-invalid read fields never appear in any response, health JSON, `caplog` record or journal database/WAL byte; they appear only under `S/spool`. **Raw-socket protocol canaries** (critic 1): a canary in the method, in the request target, in the HTTP version, in a header name without a colon, and in a header line over 65,536 bytes. Each is absent from the raw response bytes, status line included, and from `capfd`'s stdout and stderr. Each response body is exactly its mapped code, and each is counted under `http.protocol_errors`. Two exceptions whose messages are canaries are also injected: one inside step 9b's scope (a patched `sanitize_notification`, giving 500 `receiver_error`) and one that escapes the handler (a patched `send_response`, reaching the server's `handle_error`). Neither leaves the canary or the word `Traceback` in `capfd`'s stderr.
- **H16.** `S` inside `runs` and `runs` inside `S` → `state_placement_invalid` before binding; a missing `S` → `state_missing`; nothing is created.
- **H17.** ACK lost (MD H7): the handler's response write is patched to drop the connection after `admit`; the retry gets 202 `suppressed`; the journal holds admitted then suppressed; one spool entry.
- **H18.** Bind before open: with the port already bound by a test socket, construction raises `listener_bind_failed` and every journal file hash is unchanged. With `open_recovery_journal` patched to wait on an event, a POST gets 503 `journal_opening` and health is 503 `opening`. The full-body urllib POST from H7 gets the same 503 here, as a darwin-only case (critic 5).
- **H19.** Health has its fixed key set in the `opening`, `ready` and `held` states; every code is from a closed set; no Fingerprint. **The 200 rule is pinned** (critic 10): 200 when ready with a spool that is not latched, including while `capacity_admissions` is a dispatch hold and after a `spool_full` refusal; 503 when opening, held or closed, or when the spool is latched.
- **H20.** The 202 receipt has exactly its seven keys, `run == "not_dispatched"`, `Content-Type: application/json`.
- **O1.** `create`: `S`, `S/journal` and `S/spool` at 0700; JSON `journal_uuid`; a second `create` exits 1 `state_exists` and changes nothing. With `journal_operator`'s `sync_directory` patched to record its path, and `journal_store._full_sync` patched to record each call, the recorded order is `S.parent`, then `S` (after both subdirectories exist), then the journal's four syncs (critic 13). An injected failure of the `S.parent` sync exits 1 with `spool_write_failed`, and no genesis exists.
- **O2.** `inspect` on a ready state exits 0 with the report, `resume.token` equal to the head digest, and unchanged tree hashes.
- **O3.** `inspect` while a front door runs exits 3.
- **O4.** A held image exits 1 (`next_open` `persist_hold`, with `in_anchor` false when not yet persisted); a WAL-absent image exits 6 and gains no file.
- **O5.** Spool survey: an H9 orphan is listed with exit 0; a hand-deleted referenced entry exits 5 in `missing`; a rewritten entry exits 5 in `mismatched`; a rewritten orphan exits 5 in `mismatched_orphans`; a temp is counted. After the rewritten orphan is moved out of `S/spool` by hand, as the runbook says, inspect exits 0, and a front door start admits that body again (critic 14). An `S/spool` at 0755, or missing, exits 4 with the spool code in the report and on stderr (critic 8d).
- **O6.** `journaled_receiver.main` in a subprocess with `--port 0`: it prints the resolved state and runs directories before the `listening on` line (critic 16); SIGINT exits 0; a stale token exits 1 with `resume_stale` on stderr; a token against a held image exits 1 with `resume_not_applied`, and the port is free afterwards (critic 8c); `--resume-token` without `--operator` exits 2.
- **O7.** Least privilege (OF O9): the subprocess runs with an environment holding only `PATH` and `PYTHONPATH`, starts and serves.
- **O8.** A state directory with no journal exits 1 with `journal_missing` and the `create` hint; nothing is created.
- **C1-C5** (a child process per case, SIGKILLed by a monkeypatch at the injected point; the parent then opens or inspects): C1 after `spool.store`, before `admit` (orphan, no admission; a re-POST is admitted reusing the entry); C2 after `append`, before the 202 (admission present; a re-POST is `suppressed`, `held`; one entry); C3 after the refusal commit, before the 4xx (one record; a re-POST coalesced); C4 after the start's restart, before the resume (no `operator_action`; the old token is stale); C5 after the resume commit, before serving (the next open's restart follows the `operator_action`; held).
- **C6.** A SIGKILL loop of 5 iterations: a client thread posts distinct bodies; the child is killed at a delay drawn from `random.Random(seed)`, where the seed is fixed in the test, overridable by a keyword for local reruns, and printed (critic 5); then the child is restarted; at the end inspect shows every 202'd `body_digest` referenced and present, `missing_total == 0`, and every orphan belongs to an unacknowledged request.
- **L1.** Fresh interpreter: importing `receiver`, `__main__` and `replay` loads no `journal_*`, `recovery_journal`, `journaled_receiver`, `journal_operator` or `sqlite3` (probe s2).
- **L2.** AST: `receiver.py`, `__main__.py`, `replay.py`, `run_spawner.py` and `notification.py` import none of those modules.
- **L3.** AST over the three new modules: no import outside the allowlists above; no `os.environ`, `getenv` or `environ` access; no reference to `RunSpawner`, `Forwarder`, `JiraCredential`, `spawn_run` or `parse_json`; no string constant equal to a credential variable name (read from the committed modules). A fresh interpreter importing `journaled_receiver` and `journal_operator` loads no `subprocess`, and none of **exactly** these package modules: `grafana_jsm_sandbox.{forwarder, run_spawner, receiver, notification, run_command, __main__}`. It is not a `forwarder*` prefix match, because `grafana_jsm_sandbox.forwarder_json` is an expected transitive load through `journal_records` and `journal_ingress`, and the test asserts that it **is** loaded, so a future change to that import is noticed (critic 15; probe s2).
- **L4.** AST: every `except` body in the new modules only assigns or passes, with no `raise` inside a handler.

**Root** owns:
- the baseline, measured before any edit: `pytest -q`, expecting 4443 passed and 38 skipped;
- the golden pin: root recomputes K10's four digests independently before they are committed;
- the focused command, with its wall time recorded: `pytest -q tests/test_journal_front_door_records.py tests/test_journal_spool.py tests/test_recovery_journal_front_door.py tests/test_journaled_receiver.py tests/test_journal_operator.py tests/test_journaled_receiver_crash.py tests/test_journaled_legacy_identity.py tests/test_journal_records.py tests/test_journal_reducer.py tests/test_recovery_journal.py tests/test_recovery_journal_crash.py tests/test_recovery_journal_adversarial.py tests/test_journal_ingress.py tests/test_journal_ingress_corpus.py tests/test_journal_ingress_adversarial.py tests/test_journal_store.py tests/test_journal_source.py tests/test_receiver.py tests/test_replay.py tests/test_container.py tests/test_forwarder_json_string_cap.py tests/test_forwarder_upstream_adversarial.py`. It includes the five suites the critic found missing: the store decodes through the edited envelope, A4 imports the corpus helpers, and the upstream scan rglobs the new modules and the `panel/` probes (critic 15);
- the full suite, `pytest -q`: 0 failures; skips are 38 plus only the declared platform cases, all listed in `validation.json`: S8's Linux branch, and on Linux the H7 and H18 full-body cases (darwin-only);
- `ruff check` on the new and changed files, and `git diff --check`;
- the diff check: `git diff --exit-code b931610 --` over the legacy-identity list and `tests/` is empty for tracked paths; among tracked paths `git diff --stat` touches only `journal_records.py`, `journal_reducer.py`, `recovery_journal.py`, `docs/recovery-journal.md`, the backlog and the issue-37 file; `git status --porcelain` shows only those, this unit's new files, the untracked `panel/`, and the four protected paths, hashed before and after; no test file contains a fixed port;
- `reviews/receiver-journal/validation.json` with SHA-256 hashes of sources, tests, docs and both suite logs, plus the transcribed timings.

An independent reviewer binds the final hashes before the single local commit, reading the three journal-module diffs line by line against this plan. There is no push.

## Documentation (root)

`docs/recovery-journal.md`:
- **New section "Front door (journaled, admission-only)"** after "Ingress": the opt-in command and state layout; the HTTP table and health shape; the spool (durable before admission, content-addressed, never deleted, 256 MiB); `ingress_refusal` and its flood rule; `operator_action` resume at open and why only at open; verify-only inspect, the WAL rule and exit codes; the operator runbook ("What an operator sees" above), including its three revision-2 lines: a hold code on `/health` after an `unverified` inspect is the verdict; capacity codes are permanent for a state directory, and the remedy is a new one; a mismatched orphan is moved out by hand. It also covers the listener bounds (deadline, connection cap, and why that is bounded work but not availability); the crash windows W1-W15; the non-claims.
- **Corrections:** L4-7 (the journal is wired into the journaled front door, and still not into `receiver.py`); L222-223 ("Nothing clears them yet" becomes "resume at open clears `restart_recovery`; capacity holds stay"); L225-226 (the 503 mapping now exists); L257-258 and L306-307 (the sanitizer is called by the front door, and refusals persist); the focused command at L331; L334-339 non-claims (Receiver integration is opt-in and admission-only; dispatch, Runs, the online operator channel and spool retention remain unimplemented; Grafana's 503/411/413/422 handling is not qualified).

**README: no change.** Journaled mode is not a demo mode; a README pointer belongs with the lifecycle unit, when the journaled path can open Incidents. Units 15 and 16 did not touch the README either.

## Design judgment

**Scores** (each criterion 1-10; the maximum is 60):

| Design | J1 spec_fidelity | fail_closed | boundedness | legacy_identity | testability | no_invented_inputs | **J1 total** | **J2 total** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| admission-only | 8 | 8 | 7 | 10 | 8 | 8 | **49** | **48** |
| operator-first | 6 | 7 | 7 | 9 | 7 | 6 | **42** | **43** |
| minimal-dispatch | 4 | 6 | 4 | 7 | 7 | 3 | **31** | **30** |

Judge 2's row detail for admission-only was 8, 8, 6, 10, 9, 7; for operator-first 6, 8, 6, 8, 8, 7; for minimal-dispatch 4, 6, 3, 6, 7, 4.

**Where the judges differed, and the ruling:**
1. **Resume binding.** J2 proposed `state_digest(candidate)` as the token; J1 required binding the inspected head and `pending_digest`, not `state_digest`. Ruling: the token is the inspected head's `record_digest` (formula-free, chain-binding; probe s1), and the durable record binds `inspected`, `since` and `pending_digest`; `state_digest` appears in no record.
2. **Spool collection.** J1 offered identity-bound GC or deferral; J2 required no deletion. Ruling: no deletion, a read-only survey, and the 256 MiB cap J1 asked to keep.
3. **The Receiver keyword.** J1 conditional, J2 cut. Ruling: a separate command, with the keyword specified as the U17-P2 alternative.
4. **Immediacy against later-unit fit.** J1 required "immediately after the restart"; J2 counted OF's immediacy as unable to serve an online resume. Ruling: the v1 `rule` `resume-at-open-v1` requires immediacy; an online channel needs its own `operator_action` version and rule anyway, together with cancel, retry and abandon (R1).
5. **The refusal limit.** Ruling: a fixed 256 under the `rule` literal, not a ratio of `max_admissions`.

**Every judge error, resolved:**

| Error | Resolution |
| --- | --- |
| J1-AO-1 inspect not neutral on a WAL-absent image | WAL pre-check; `unverified` without opening SQLite; K6/K7 twin-image neutrality over eleven images in revision 2 (J1 p1, p2; probe s1; critic 9) |
| J1-AO-2 golden said 16 records, listed 13 | The new golden is tabulated: 14 records, 11 commits |
| J1-AO-3 GC without identity binding | No deletion (U17-P9); Deferred 5 requires identity-bound retention |
| J1-AO-4 1 MiB drain | Cut: 413 and close without reading |
| J1-AO-5, J2-AO-1 two payload shapes under `rj.state.v1` | `state_digest` unchanged; `front_door_digest` under its own tag |
| J1-AO-6 compare-and-set without progress | Online resume cut; resume at open has no concurrent writer |
| J1-AO-7, J2-AO-3 imprecise R2 note | Corrected: always `record_unsupported` |
| J1-AO-8 opt-in reading unflagged | U17-P2, with the keyword alternative specified |
| J2-AO-2 false spool-placement reason | Corrected: the store never enumerates its directory (J2 q3); the sibling layout is chosen for one-directory custody and explicit create |
| J2-AO-4 flood key and ratio | Membership key kept under `rule` `first-per-membership-v1`; fixed limit 256; U17-P3 ratifies against U16-P17 |
| J2-AO-5 optimistic size | Second listener, token file, live inspect, GC, drain and live refusal view cut; per-file table; split trigger |
| J1-OF-1, J2-OF-1 invented `operator_resume` | `operator_action` with `operator` and `reason` |
| J1-OF-2, J2-OF-2 `GET /journal` on the ingress port | Cut; health is counts only; pending is shown only by offline inspect |
| J1-OF-3 X11 cannot pass | A9 restates isolation over admission records, baselines and `pending_digest` |
| J1-OF-4 inspect overclaim on WAL-removed | WAL pre-check |
| J1-OF-5 golden count | Not adopted; this plan's golden is counted |
| J1-OF-6 unbounded spool | 256 MiB cap, `spool_full` |
| J1-OF-7 `inspected_state_digest` freezes a formula | `inspected` head plus `pending_digest` |
| J1-OF-8, J2-OF-5 spool sync inside the journal lock | Spool before `admit`, outside the journal lock; the capacity orphan is identified by inspect |
| J1-OF-9 envelope change unratified | U17-P5 |
| J1-OF-10 "a Python 3.11 container" | Moot: the container runs 3.13 (plan P26) |
| J2-OF-3 unnecessary `receiver.py` edit | Not adopted |
| J2-OF-4 weaker refusal validator | Full port, A3-A5 parity |
| J2-OF-6 edit inside `_verify_restart` | Not adopted; boot fields derive in `apply_delta` from existing deltas (U17-P6) |
| J2-OF-7 lists against tuple validators | `refusal_summary_data` normalizes to tuples |
| J2-OF-8 each resume costs an outage | Accepted residual; OF W14 removed by bind-before-open |
| J1-MD-1, J2-MD-1 dispatch outside the gate | Crux (i) |
| J1-MD-2, J2-MD-2 `run_exit` instead of spawn and terminal observations | Not adopted; forward contract in Deferred 1 |
| J1-MD-3 merged intent and claim | Forward contract: separate commits, lease between |
| J1-MD-4, J2-MD-5 refusals re-deferred | `ingress_refusal` ships |
| J1-MD-5 live Runs beside a same-uid token | No Runs and no token |
| J1-MD-6 `RECEIVER_STATE_DIRECTORY` outside the env contract | Not adopted; the new entry point reads no environment (L3) |
| J1-MD-7 `latest-admitted-v1` under consumption | Deferred 1: the lifecycle unit needs `latest-admitted-v2` |
| J1-MD-8 "admission-only makes resume pointless" | Rejected: resume changes `decision` and satisfies P20 |
| J1-MD-9, J2-MD-9 size at the ceiling | Not adopted |
| J1-MD-10 inspect overclaim | WAL pre-check |
| J1-MD-11 no in-flight bound; reads before the held check | Semaphore (step 1); held check before any read (step 2) |
| J2-MD-3 invented fields frozen; a per-type version bump assumed | Not adopted; R1 note that any version step is an envelope change |
| J2-MD-4 retention presented as orphan collection | No deletion here |
| J2-MD-6 `decision` drift from P7 | Not adopted |
| J2-MD-7 legacy identity overstated | This plan edits neither `__main__.py` nor `journal_store.py` |
| J2-MD-8 unreapable Runs | Not adopted: no Runs |

**Grafts taken.** From operator-first: resume at open; no spool deletion and the read-only survey with exit 5; a separate front-door digest; a `rule` literal on the refusal record; least-privilege and import-graph tests (L1, O7); the stale-token no-write test (K3, H4). From minimal-dispatch: the per-(type, actor) table (A2); the ACK-lost test (H17); explicit create only (V21); the lifecycle forward contract (Deferred 1). Judge fixes: the WAL-safe inspect and bind before open.

**Cuts from the base design.** The loopback operator listener, `operator.json`, `/operator/*` routes, `inspect --live` and the y/N prompt; spool GC with its crash test and the shell-private index; the oversize drain; the conditional `front_door` key in `state_digest`; the live refusal view in health; environment defaults for host and port.

## Critic issues resolved (revision 2)

Each row names the critic's issue (`panel/critic.md`), what changed, and the tests that pin the change. "Part rejected" says which suggestion was not taken, and why.

| # | Severity | Issue | Resolution in revision 2 | Tests | Part rejected |
| --- | --- | --- | --- | --- | --- |
| 1 | medium | stdlib error paths put caller bytes in responses and stderr | `send_error` override with the closed `STDLIB_ERROR_CODES` map (400/414/505 → `http_request_invalid`, 431 → `http_header_invalid`, 501 → `http_method_unsupported`, else 500 `receiver_error`), a fixed reason phrase, a code body, `Connection: close`; `log_message` dropped; server `handle_error` logs the type name only; V14 now covers status lines and stderr (probe r1a, r1d) | H15 raw-socket canaries (method, target, version, header name, long header line), escaped-exception case | the 408 `http_timeout` mapping: the 3.13 stdlib never sends 408, and a header-phase deadline closes without a response (probe r1b). 414 maps to `http_request_invalid`, not `http_header_invalid`, because it concerns the request line. 405 is never sent |
| 2 | medium | V16 overclaimed; trickling clients hold slots | one monotonic `REQUEST_DEADLINE_SECONDS = 10` per request through a deadline reader that re-arms `settimeout(remaining)` before each `recv_into`; `MAX_CONNECTIONS = 32` enforced in `process_request` with no thread for the excess; `deadline_exceeded`, `connections_refused`, `connections_open` in health; V16 restated as bounded work, not availability; all under U17-P11 (probe r1b, r1c) | H14b (body and header trickle), H11b | - |
| 3 | medium | A9 cannot pass; "Inert" false at the byte bound | the coupling is stated: refusals advance `logical_bytes` and can move the `capacity_bytes` boundary by at most the sum of their charges (about 1.3 MiB per generation); "Inert, except for the byte budget"; A9's removal clauses restricted to histories where `capacity_bytes` is unreachable, with the precondition asserted by the generator | A9 (restated), A7b (directed boundary) | a separate refusal byte slice outside `logical_bytes`: it would let the journal exceed the spec's 128 MiB bound (spec L273-275) |
| 4 | medium | the refusal validator was specified two ways | split into the strict `_check_refusal_summary` (tuples only; the only function the validator calls) and the normalizer `refusal_summary_data` (lists or tuples, used by `record_refusal` before sealing; the normalized dict is sealed); check order for both new validators and both replay functions; every `inspected` leaf bound tabulated | A3, A6 (separately), A7 | - |
| 5 | medium | flaky and blind tests | `http.in_flight` gauge polled by H11; H14 asserts outcomes only, within 5 s, and prints elapsed time; C6 seeded and printed; full-body urllib POST in H7 and H18 (darwin-only); "no-read 503 on Linux" under "Not qualified" | H7, H11, H14, H18, C6 | - |
| 6 | medium | capacity refusals spooled first; unbounded entry count | step 7b `admission_precheck()` refuses before spooling once `capacity_admissions` is a dispatch hold (exact, lock-free, advisory); `MAX_SPOOL_ENTRIES = 20,000` gives `spool_full`; the verified set is bounded by the entry cap; runbook step 7 "capacity codes are permanent for this `S`" | H9b, S5 | prechecking when the bound is merely reached (not yet held): then the durable `capacity_hold` would never be written; the precheck fires only once the hold exists |
| 7 | medium | later-unit fit: version step and mode pins | reader registry keyed by `(event_type, schema_version)` with the four envelope predicates data-driven and byte-for-byte equivalent for v1; a v2 pair is one registry entry; the admission-only assertions are grouped as `test_admission_only_mode_*` (H1, H19, H20, L3 fresh-interpreter) for the lifecycle unit to supersede by name; Deferred 1 names both | A2 (check position), K11b | the writer side of the version step (a per-record schema version on `Record`, `seal` and `content_digest`): no v2 pair exists to exercise it, and adding a `Record` field now would be an untested v1 change; Deferred 1 names it |
| 8 | low | inspect and resume details | (a) the null rule for non-`ready` verdicts, and the `collect` candidate is discarded unless replay completes; (b) `try/finally: store.close()`, and `observe` exceptions propagate after the close; (c) `start()` raises `resume_not_applied` after stopping the listener, and `main` exits 1; (d) exit 4 names the spool code for a custody failure of `S/spool`; (e) K10 masks exactly five leaves | K9, O5, O6, K10 | - |
| 9 | low | WAL-absent loop for held images; V10 unqualified | the pre-check opens the store when the DB is absent or shorter than `PAGE_SIZE` (no connect, so no WAL); the runbook makes a hold code on `/health` the verdict; V10 and W13 qualified to WAL-present images; K6 gains three images (persisted hold without WAL, DB unlinked without WAL, torn WAL tail) | K3b, K6, H7b | - |
| 10 | low | the health 200 rule contradicted its meaning | 200 now means "the process accepts writes" (ready and spool not latched), with no claim that a new body can be admitted; capacity and `spool_full` stay in the body | H19 | the alternative, 503 for `spool_full` and `capacity_admissions`: capacity codes are dispatch holds in the journal's own model, and a monitor that pages on them can read the body |
| 11 | low | the refusal budget formula was ambiguous | `len(record.body) + RECORD_OVERHEAD_BYTES` against `ordinary_bytes`, on the sealed record, as `_verify_admission_pair` does; added as a replay row of `_verify_ingress_refusal` | A7 | - |
| 12 | low | the durable refusal channel can be exhausted by minted keys | 64 of the 256 records are reserved for summaries with a Resolved member, replay-verified through `refusal_unreserved_count`; U17-P3 states that only webhook authentication (Deferred 8) stops a sender who mints Resolved-bearing summaries | A7 | - |
| 13 | low | `create_state` did not sync `S` or its parent | `journal_spool.sync_directory`; `create_state` syncs `S.parent` after `mkdir S`, and `S` after both subdirectories exist; V23 | O1, S10 | - |
| 14 | low | one conflicting spool entry latches the spool, and inspect could not predict it | the survey content-verifies every orphan too (bounded by the entry cap) and lists `mismatched_orphans`, and inspect exits 5; runbook step 8: move the orphan out by hand | S9, O5 | answering `503 spool_conflict` for that digest only, without latching: a content mismatch under a digest name means tampering or media fault, and the whole spool stays fail-closed |
| 15 | low | the focused command omitted suites; L3's wording | five suites added; L3 names the exact module set, and asserts that `forwarder_json` **is** loaded transitively (checked) | L3 | - |
| 16 | low | defaults make the placement check and "Grafana posts" vacuous | `main` prints the resolved state and runs directories; the runbook requires `--runs-directory` to match the legacy `RUNS_DIRECTORY`; step 3 is "`replay` posts", with Grafana only under `--host 0.0.0.0`, which is deliberately not the default | O6 | - |

## Proposals requiring ratification

Numbered U17-P1 to U17-P18 to avoid clashing with P1-P27, R1-R7 and U16-P1 to U16-P18.
- **U17-P1.** Journaled mode is admission-only: no Run, and `"run": "not_dispatched"` in the receipt.
- **U17-P2.** Opt-in by a separate command (`journaled_receiver`), not a `Receiver` keyword or an environment switch. *Alternative:* the specified `journal=None` keyword.
- **U17-P3.** `ingress_refusal` v1: the nine-key summary, the membership-inclusive key (changing U16-P17's key), the `rule` `first-per-membership-v1`, 256 records per generation with 64 reserved for summaries carrying a Resolved member, ordinary class, no capacity hold. The byte coupling is accepted: refusals share the ordinary budget and can move the `capacity_bytes` boundary by up to their summed charge. **Explicit limit:** the reserve does not stop a sender who can reach the port and mints Resolved-bearing summaries; webhook authentication (Deferred 8) is the only real mitigation.
- **U17-P4.** `operator_action` v1: `resume` only, `restart_recovery` only, `rule` `resume-at-open-v1` with immediacy, bound to `inspected`, `since` and `pending_digest`; a self-asserted ID-grammar `operator` and `reason`; actor `operator`; recovery class.
- **U17-P5.** The R1 reading: the reader registry keyed by `(event_type, schema_version)`, `SCHEMA_VERSIONS`, and the per-pair actor table are not an envelope change for any existing type, because all four predicates accept and reject exactly as before, at the same positions and with the same codes.
- **U17-P6.** The R4 readings: resume removes a shared dispatch hold; the boot fields are derived in `apply_delta`.
- **U17-P7.** Resume only at open, with the inspected head digest as a staleness token; no online operator channel.
- **U17-P8.** Verify-only inspect: no WAL is ever created. A WAL-absent image with a full-size DB is `unverified`; one with a DB that is absent or short is opened, because the store returns before connecting. An absent `lock` may be created and is reported. The null rule applies to non-`ready` verdicts. Exit codes are 0-6, with 4 covering a spool custody failure and 5 covering mismatched orphans.
- **U17-P9.** The spool: `S/spool`, content-addressed by `body_digest`, synced before admission, capped at 256 MiB and 20,000 entries, conflicts latch, every entry content-verified by the survey, **no deletion**; plan Deferred 2's "collected by digest absence" is read as "identified".
- **U17-P10.** The state layout `S/journal` and `S/spool`, explicit `create`, and the placement check against `runs_directory`.
- **U17-P11.** The HTTP mapping: steps a, p and 0-10 (with 7b), the framing codes 411/400, 413 without reading, `Retry-After` 10 and 1, 8 in flight, 32 connections closed at accept beyond the cap, one 10 s monotonic deadline per request, the `STDLIB_ERROR_CODES` map with fixed reason phrases, code-only bodies, `log_message` and `handle_error` overrides, the JSON receipt.
- **U17-P12.** 422 stays "422 and stay refused", now recorded durably (u16 Deferred 1).
- **U17-P13.** The health shape, its gauges, and its 200/503 rule: 200 means "the process accepts writes".
- **U17-P14.** Bind before open, and 503 `journal_opening`.
- **U17-P15.** Defaults: `127.0.0.1:8080`, `runs` for the placement check; no environment variable. Both resolved directories are printed at start. The runbook requires `--runs-directory` to name the legacy `RUNS_DIRECTORY` when both commands are used, and `--host 0.0.0.0` (deliberately not the default) before Grafana can post.
- **U17-P16.** Names: `journaled_receiver`, `journal_operator`, `journal_spool`, the tags `rj.refusal-key.v1`, `rj.refusal-key-set.v1` and `rj.front-door-state.v1`, and every new code (including `resume_not_applied`, `http_request_invalid`, `http_header_invalid` and `http_method_unsupported`).
- **U17-P17.** The capacity precheck (step 7b): refuse without spooling once `capacity_admissions` is a dispatch hold, and only then.
- **U17-P18.** The admission-only mode pins: the `test_admission_only_mode_*` set is this unit's statement of mode, which the lifecycle unit supersedes by name.

## Deferred

1. **Run lifecycle** (plan Deferred 3), gated on the ticket-38 reservation seam or an explicit ratification of a no-reservation gate profile. Forward contract, from `design-minimal-dispatch`:
   - `run_hold` for an ineligible Run; `run_intent` durable before any spawn, then lease registration, then a separately committed launch claim (spec L197-201);
   - a `JournalError` from the intent commit is ambiguous, so never spawn;
   - a spawn observation immediately after the real spawner observation, which needs a spawner observer (spec L202-203);
   - a claim with no exit from an earlier boot is `launch_unknown`, never NEVER_STARTED (spec L254); only the claiming boot records the exit;
   - the R7 watermark `{through_arrival_seq, consumed_set_digest, consumed_count}`; `latest-admitted-v2` once entries are consumed (J1-MD-7);
   - reading Run input from the spool with `O_NOFOLLOW`, 0600, one link and a digest re-check;
   - a staleness policy for pending entries admitted while no dispatcher existed;
   - real resume preconditions over run state, and an online, Run-isolated operator channel;
   - **the writer side of the first version step** (critic 7). The reader side is registry-driven here, so `(operator_action, 2)` for cancel, retry, abandon or online resume, and `(ingress_refusal, 2)` for a new ingress code, are each one registry entry. The writer still needs a per-record schema version: a `Record` field set from the draft's registered version, written by `seal` and covered by `content_digest`. That is a v1 module change, and the lifecycle unit designs and ratifies it;
   - **the mode pins** (U17-P18). The lifecycle unit supersedes the `test_admission_only_mode_*` set by name: H1's no-runs and no-`Popen` checks, H19's `mode` and `runs`, H20's `run`, and L3's fresh-interpreter check for `journaled_receiver`. Dispatch should live in its own module, handed to `JournaledReceiver` by a separate entry point, so that L3's AST bans on `journaled_receiver.py` stay true unchanged.
2. **The `__main__` and container switch**, once journaled mode can run the demo, with the compose volume for `S`.
3. **Other operator actions** (plan Deferred 6): capacity clear with reset or compaction, cancel, retry, abandon, reconcile, `reset_commit`.
4. **Reconstruction and handoff** (plan Deferred 8), the only way to lift a durable recovery hold.
5. **Spool deletion and retention** (plan Deferred 7), bound to the journal's identity so an evidence journal's bodies are never collected (J1-AO-3).
6. **The alternative 422 policy** "record, hold, 202", once Grafana's resend behaviour is qualified.
7. **Persisting `starts_at_dropped`**, the `capture` provenance kind, ingress loosening candidates (u16 Deferred 4, 5, 8).
8. **Operator authentication** beyond same-uid, and audited identity (spec L328, L343). **Webhook authentication and per-peer limits** for the front door, the only real mitigations for a sender who mints Resolved-bearing refusal summaries or keeps 32 connections occupied (U17-P3; V16).
9. **A Linux-container run** of the spool and journal sync paths.
10. **The `Receiver` keyword seam**, only if U17-P2 is rejected.

## Not qualified by this unit

- **Grafana behaviour, none probed:** its handling of 503 with `Retry-After`, 411, 413 and 422; whether it re-sends after a refusal (the resend hypothesis); whether it always sends `Content-Length` and never chunked; its webhook timeout against about 85-100 ms per admission; what it does during the stop-start a resume needs.
- **Durability:** power loss for spool entries or the journal on any device; `F_FULLFSYNC` honesty; Linux `fsync` beyond primitive selection; volume persistence across a pod restart.
- **Isolation** of the journal and spool from Runs or other same-uid processes; the resume token and `operator` label are not authentication.
- **Performance at the bounds:** open time at 10,000 admissions plus 256 refusals; a survey that content-verifies up to 20,000 spool files. Timings come from the development Mac.
- **HTTP edge cases** beyond the tested framing: pipelining, TLS (none), and the stdlib's HTTP/0.9-form bare-code reply to an unparseable version, which a client may not parse (probe r1a).
- **No-read 503 on Linux.** On macOS the 503 reached the client with a full body unread (critic probe c1a). On Linux, closing a socket with unread data can send RST before the client reads the response. H7's and H18's full-body cases are darwin-only for this reason.
- **Availability under hostile load.** The deadline and the connection cap bound work, but a peer that holds all 32 connections can keep Grafana's POSTs refused at accept (V16).
- **The demo in journaled mode**, which creates no Incidents by design.
- **Every U17 proposal**, and every unit-15 and unit-16 proposal still awaiting ratification.

## Residual risks the reviewers must accept

- **No Incidents in journaled mode.** An operator who starts it expecting the demo gets 202s and silence while pending grows. Mitigations: a separate command; `"runs": "not_dispatched"` in health, receipts and logs; the restart hold, which forces an inspection before any future dispatch.
- **Resume costs a restart.** Every resume is stop, inspect, start. Storing a token in a script makes every later start exit 1, because the head moves. Grafana's retry across that window is unqualified.
- **Edits to frozen v1 modules.** The four registry-driven envelope predicates, the `Delta` defaults, the boot fields in `apply_delta` and the hold removal are small, but a slip would change existing-type acceptance or replay. Mitigations: every existing test unchanged and green, including the schema-version-2 case; A2's check-position test; E16; the frozen-formula property (A9); the rollback simulations (K11, K11b); mutation matrices. U17-P5 and U17-P6 still need ratification.
- **Restated vocabularies.** The refusal codes, statuses, bounds, summary rules and the sync primitive are copied because the import pins forbid importing them. Parity tests A4, A5 and S8 guard drift; review must keep the copies in step.
- **The flood key is mintable.** Flapping membership or adversarial `groupKey`s can use the 192 unreserved records early in a generation; later refusal kinds without a Resolved member are then only counted per boot. The 64-record reserve keeps a benign flood from crowding out a lost Resolved, but a sender who mints Resolved-bearing summaries can use up the reserve too. Only webhook authentication, which is deferred, stops that.
- **Refusals share the admission byte budget.** Up to about 1.3 MiB of refusal records per generation can bring `capacity_bytes` earlier for admissions (A7b). That is under 1.2% of the 112 MiB ordinary region.
- **Spool growth.** Nothing is deleted. The 256 MiB and 20,000-entry caps give 503 `spool_full` well before the adversarial 2.5 GiB; realistic use is about 30-90 MiB per generation. After `capacity_admissions`, nothing new is spooled (step 7b). Only a new state directory relieves the caps until retention lands.
- **Capacity is per generation.** With this demo's `repeat_interval: 1m`, suppressed repeats count toward the 10,000 admissions. At one repeat a minute, seven firing groups use up a generation in about a day (7 × 1,440 = 10,080). From then on every valid POST gets 503 `capacity_admissions`, which Grafana retries. The runbook says so, and the remedy is a new state directory.
- **Availability.** A peer that holds 32 connections, reconnecting every 10 s, can keep Grafana's POSTs refused at accept; the loopback default limits who can do that.
- **Coverage.** Notifications handled by the legacy command, or sent while the front door is down or opening, are not journaled. The journal is a complete admission record only if the front door is the only receiver.
- **WAL-absent images need one extra start.** Inspect reports them `unverified` rather than create a WAL. When that start is held before connecting, the `/health` hold code is the verdict (runbook step 4).
- **Latency.** About 85-100 ms per new body, serialized on the journal lock (AO p1, p4); acceptable at the captured rates.

## Root reconciliation (2026-09-24, against `b931610`)

- **Baseline.** HEAD is `b931610`, this plan's baseline, with no commit in between. `pytest -q` gives **4443 passed, 38 skipped** in 237 s, as the plan expects. The line references spot-checked against HEAD all hold: journal_records.py L443 (the `schema_version` check) and L456-460 (event type before actor); journal_store.py L817-828 (returns before connecting, then `wal_found`, then connect); recovery_journal.py L195-233 (`_open_verified`); journal_reducer.py L363-365, L526-528 and L649-652.
- **Execution split, decided up front.** Earlier units' size estimates ran about 2x low, so root runs the work as two workflows. **17a** covers Implementer A (the three journal modules and A1-A12) and Tester T1 (K1-K14 and the front-door golden). **17b** covers the spool, the front door, the operator CLI and the S, H, O, C and L cases. 17b starts only after 17a has passed review. The 625-line trigger is measured on A's diff when 17a finishes. If it is exceeded, 17a is gated, reviewed and committed on its own, with a full suite that contains no 17b file. Otherwise 17b follows before one commit.
- **Ownership adaptations (disjointness unchanged).**
  - T1 runs as a drafter in parallel with A, then as a finalizer after A. The finalizer reconciles names, builds the golden and pins its digests.
  - In 17b, Implementer B splits into B1 (`journal_spool.py` and `tests/test_journal_spool.py`) and B2 (`journaled_receiver.py` and `journal_operator.py`).
  - T2 splits into T2a (`tests/test_journaled_receiver.py`) and T2b (the operator, crash and legacy-identity files).
- **Review additions.** A fifth lens checks v1 compatibility line by line against `b931610` (the residual risk "Edits to frozen v1 modules"). A mutation sweep follows the fix loop, then a gap agent proves each new test against its mutant.
- **Documentation split.** 17a documents the journal-level features in `docs/recovery-journal.md`: `ingress_refusal`, `operator_action`, verify-only inspect and resume at open. 17b adds the "Front door (journaled, admission-only)" section and the remaining corrections.
- **17a as built.** These are recorded after the final review.
  - **Size.** The implementer's diff added 931 lines; after the review's docstring edits the final tree adds 938 (244, 222 and 472) against the 625 trigger, so 17a is committed on its own. `recovery_journal.py` grew by 472 lines, to 1,098, against an estimate of 220; most of that is inspect's report builder. The reviewer accepts the size. If a split is wanted, the seam is inspect, which could move to a `journal_inspect.py` once 17b's `journal_operator` becomes its caller.
  - **Private import.** `recovery_journal.py` imports the private `journal_store._check_directory` (fix F1-5). This keeps `journal_store.py` byte-identical, and inspect now refuses exactly the directories open refuses, with the same codes.
  - **Check order.** `record_refusal` checks closed, then held, then normalizes the summary: the same order as `admit`. This plan's text normalizes first. The implemented order is kept and pinned by a test, so a held journal answers `journal_held` whatever the argument.
  - **Validator codes (F1-18).** Every refusal-summary violation is `record_field`. An `operator` or `reason` violation is also `record_field`, not `validate_id`'s `record_id`, because they are data fields.
  - **Replay re-check (F2-1).** Replay re-checks that a resume's `hold` is `restart_recovery`.
  - **Clock code at resume (F2-7).** A monotonic-clock regression at the resume step is `journal_clock_invalid`.
  - **Exports.** `journal_records.__all__` gains 12 names, `journal_reducer.__all__` 7 and `recovery_journal.__all__` 5.
  - **Byte coupling.** The largest summary v1 can hold is 2,866 bytes, well under the 4,096-byte check. The coupling is therefore under 1 MiB per generation, not the 1.3 MiB estimated under "Journal extensions".
