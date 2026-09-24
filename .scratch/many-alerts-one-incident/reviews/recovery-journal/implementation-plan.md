# Receiver recovery journal core and durable admission transaction (unit 15)

2026-09-23, revision 2 (critic pass). **Baseline:** `6a3ecc2` (unit 14). This is the fifteenth separately authorized local application unit under the [approval record](../native-runtime-source-implementation-approval.json), and the first local implementation unit of the ticket-37 Receiver-owned durable recovery journal. Its authority is proposal step 2 (`native-runtime-source-implementation-proposal.md` L32-36): "Add Receiver-owned durable admission, recovery and accounting modules".

**Scope.** Source and synthetic tests only. Tests use private `tmp_path` subdirectories created with mode 0700, real SQLite, real `F_FULLFSYNC`/`fsync`, injected clocks and ID factories, and the committed ticket-14 captures read-only. Out of bounds: push, provider/native/tenant calls, real credentials, C2 retries, paid experiments, deployment, and any edit to an existing module, test, document or `pyproject.toml`. Run the full suite before committing. Every existing test file stays byte-identical.

**Protected state.** Four dirty paths exist at baseline (re-checked 2026-09-23 with `git status --porcelain`):
- `.scratch/many-alerts-one-incident/issues/19-mcp-grafana-behind-the-sentinel.md` (modified);
- `.scratch/many-alerts-one-incident/reviews/planning-frontier-2026-09-18.md` (modified);
- `.scratch/many-alerts-one-incident/reviews/ticket-19/c2-ingestion-execution-draft.md` (untracked);
- `.scratch/many-alerts-one-incident/reviews/ticket-19/c2-ingestion-session-outcome.md` (untracked).

None of them is edited, staged or committed. Ticket 19 C2 is out of scope. Staging uses explicit paths only.

**How this plan was made.** Three independent designs were judged by two panels: SQLite-transactional (`design-sqlite`), a hand-rolled framed log (`design-log`) and a domain-first reducer (`design-domain`). `design-sqlite` won both panels, 47 of 60 on durability and spec fidelity (judge 1) and 43 of 60 on boundedness and fit (judge 2), and is the base. Grafts come from `design-domain` (pure reducer, commit framing, test strategy) and `design-log` (single-in-flight tail rule, crash enumeration, versioned decision rule, consumption watermark). "Judge conflicts resolved" settles the four points where the panels disagreed. "Judge findings resolved" maps every judge error, cut and graft to its resolution.

**Revision 2** resolves all fifteen issues of the completeness critic (`u15-design/critic.md`); see "Critic issues resolved (revision 2)". Facts marked "probe pN" were checked by the synthesizer with scripts in the session scratchpad `u15-design/synth-probe/`:
- p1: numbers; p2: SQLite behaviour; p3: sizes; p4: the worked example; p5: the anchor-lag model; p6: the genesis transaction;
- revision 2 added p7 (`NO_CKPT_ON_CLOSE` evidence preservation), p8 (open-scan cost) and p9 (full-length goldens), and re-ran the critic's q2, q6 and q7.

Probes ran on macOS 25.6 (APFS) with Python 3.13.7 and SQLite 3.50.4. They show what this machine does, not what the venue's disk does.

**Proposal marking.** Every limit, field name, digest tag, file name, code string and storage setting below is a proposed routine choice that requires review (spec L341-347; integ L45-46). "Proposals requiring ratification" lists the ones that freeze into v1 records and replay rules.

**Citation keys.** `spec Lnn` is `reviews/ticket-37/recovery-specification.md`. `f31` and `sc31` are ticket-31 `fixture-spec.md` and `source-checks.md`. `acct` is `reviews/ticket-38/accounting-specification.md`. `integ` is `reviews/recovery-accounting-audit-integration.md`. `ADR12` is `docs/adr/0012-run-outcomes-and-recovery-are-explicit.md`. `J1 S-E1` and `J2 sqlite 1` name judge findings; `critic N` names critic issue N.

These facts were re-read against the working tree on 2026-09-23:
- **Receiver today.** `Receiver.accept` validates the body, writes it into a fresh Run directory and queues the Run; the handler then answers 202 (receiver.py L84-100, L135-149). Nothing survives a restart, and nothing is deduplicated.
- **Notification check.** `validate_notification` uses plain `json.loads` and requires only a truthy `fingerprint` and `status` per Alert (notification.py L22-43). This unit leaves it alone.
- **Legacy replay seam.** `replay.SEQUENCE` posts three fixtures (replay.py L25-29), and `tests/test_replay.py` L24-32 expects `[202, 202, 202]` and three spawns. `notification-firing.json` and `notification-firing-repeat.json` carry the same `groupKey` and the identical tuple `(87e2f184874a3b71, firing, {A:0, B:1})`. Under ticket-31 dedupe the repeat is therefore suppressed (probe p9: both keys are `a99b74e0…`). All three fixtures and every capture carry `truncatedAlerts: 0` (critic 6).
- **Same uid.** Runs are child processes of the Receiver under the same uid (run_spawner.py L121-138). No filesystem isolation exists.
- **Runtime.**
  - `pyproject.toml` requires Python ≥ 3.11, and it stays unchanged.
  - The container is built `FROM node:24.21.0-trixie-slim` and installs Debian's `python3` (Dockerfile L20-21, L38). The local interpreter is 3.13.7. No 3.11 interpreter is available on this machine (`/usr/bin/python3` is 3.9).
  - `sqlite3.Connection.setconfig`/`getconfig` and the `SQLITE_DBCONFIG_*` constants exist only from Python 3.12. Probe p7 confirms them on 3.13.
- **JSON primitives** (reused unchanged from `forwarder_json`):
  - parse caps: depth 16, 256 array items, 16 KiB strings, number lexemes of at most 32 characters, |integer| ≤ 2^53-1, 1 MiB documents (L25-31);
  - `parse_json` returns tuples for arrays and `JSONDecimal` text for decimals in `numbers="finite"` mode (L57-65, L170-250);
  - `canonical_json` accepts only exact `dict` objects and `list`/`tuple` arrays, and refuses arrays of more than 256 items (L253-289);
  - `tagged_digest(tag, v) = sha256(tag || 0x00 || canonical_json(v, ascii_only=True))`, with tags matching `[a-z0-9][a-z0-9.-]{0,63}` (L42, L300-305).
- **Full suite at baseline:** 3500 passed, 36 skipped (the `6a3ecc2` commit message).

**Root implementation note, 2026-09-23: the unit is split into 15a and 15b.** Implementation crossed this plan's own thresholds:
- **Module 1.** It passed its 520-line split point, so its source-record section moved to `grafana_jsm_sandbox/journal_source.py`, with the same names and owner. Downstream import allowlists add named symbols from `.journal_source`. After the split, `journal_records.py` is 612 lines and `journal_source.py` 389.
- **Module 3.** `journal_store.py` was 946 lines at implementation (607 statements, 15 comment lines) against a target of about 440. After the review fixes it is 1,101 lines; `journal_records.py` is 624 and `journal_source.py` 396.

With about 1,950 lines in the lower layers alone, the "Size" rule applies, and the unit is reviewed and committed as two units:
- **15a:** `journal_source.py`, `journal_records.py` and `journal_store.py`, with tests A1-A12 and C1-C15, and the store-level parts of the documentation.
- **15b:** `journal_reducer.py` and `recovery_journal.py`, with tests B, D, E and F, the golden guard, and the rest of `docs/recovery-journal.md`.

The store deliberately leaves commit framing and replay (`journal_tail_unverified`, `journal_replay_mismatch`) to 15b.

**15b contract refinements from review.** These supersede the text below where they differ:
- `create` refuses with `journal_argument` for any failure before a file is written: bad bounds, clock or ID factory, or a genesis record that fails verification. Genesis is now verified before the store writes it. `journal_create_failed` means files may exist.
- At open, a `finish_open` failure is the process hold `journal_open_failed`, and a failed boot-ID mint is the process hold `journal_divergence`. Step 13.4 covers only re-anchor and restart-commit failures.
- An emptied events table is `journal_truncated`.
- Open calls `persist_hold` for every recovery finding, which completes a half-written hold. `persisted` means the newest anchor slot carries the code.
- While held, including holds latched after a ready open, the snapshot's projection fields are null and `pending()` is empty.
- `anchor.lag_at_open` is the head's `commit_seq` minus the anchor's at open (negative when truncated), or null when open stopped earlier.
- Genesis must be at generation 1 (`replay_generation`).

## Why this unit

Spec L193-196 makes the admission commit the first ordering point: "In one durable transaction append admission, its latest-admitted baseline update, and a dedupe decision. Commit before the Receiver acknowledges". ADR12 L27 says "Admission that cannot be durably recorded must not be acknowledged as successful". Today the Receiver acknowledges with no durable record at all.

Every later ordering point (spec L197-212) reuses the same machinery:
- the record envelope, canonical encoding, digest chain and transaction framing;
- the synced commit plus anchor;
- full-chain verification before any prefix is applied (spec L242);
- the closed hold vocabulary.

That machinery is therefore built and reviewed first, on the smallest real record family that exercises all of it: the admission pair, with latest-admitted dedupe, pending reduction, capacity refusal and restart replay.

**Integration is deliberately excluded.** Wiring `admit` into `receiver.py` now would make every restart hold dispatch forever, because no operator resume exists yet. It would also change the legacy three-Run replay seam, since the canned repeat is suppressed. Both belong with the operator and Run-lifecycle units (Deferred 2, 3 and 6).

## Unit boundary

**In** (one reviewed local commit):
1. `journal_records.py`: the envelope, the closed v1 registry, canonical encoding, the record and content digests, transaction numbering and typed validators; also the bounded `SourceRecord`, its strict validator, `canonical_number` and the dedupe key (spec L96-104, L149-159).
2. `journal_reducer.py`: a pure deterministic fold with plan functions, `verify_commit` and `apply_delta`, shared by the live path and replay (spec L128-129, L245).
3. `journal_store.py`: one SQLite database in WAL mode with `synchronous=FULL`, `fullfsync` and a mandatory no-checkpoint-on-close setting; an append-only table; an exclusive single-writer lock; and a two-slot anchor file that detects loss of acknowledged commits and carries durable verdicts (spec L142-154, L242-247).
4. `recovery_journal.py`: explicit create, verified open and replay, `admit`, bounds, holds and a nonsecret snapshot (spec L193-196, L213-239, L271-286).
5. Six new test files, one golden data file, and a new `docs/recovery-journal.md`.

**In-scope record types:** `journal_genesis` (new), `restart_recovery`, `capacity_hold`, `admission` and `dedupe_decision`. The spec's "baseline update" (L193-194) is folded into `dedupe_decision.baseline_before/after`, which is its "latest baseline key" (L164).

**Out** (see "Deferred"):
- raw Notification parsing and sanitizing, `body_digest` computation, the body spool and the HTTP 400/413 mapping;
- `receiver.py` and `run_spawner.py` integration;
- run hold, run intent, launch, spawn and terminal records;
- effect intent, receipt and reconciliation;
- ticket-38 reservations and accounting;
- operator actions, resume, verify-only inspection and reset;
- retention and compaction;
- reconstruction and handoff, which are the only way to lift a durable recovery hold.

## Modules

The four new modules live in `grafana_jsm_sandbox/`. They follow the Forwarder house rules:
- exact-type checks (`type(x) is int`, never `isinstance` for scalars);
- closed code sets in `frozenset`s and `MappingProxyType` registries, and `__all__`;
- every `except` body only assigns a local code; a fresh error is raised after the `try` statement with `from None`, so no exception carries caller data in `args`, `__cause__` or `__context__` (forwarder_json.py L6-14).

None opens a socket, starts a process, reads a credential or logs.

### Module 1: `journal_records.py` (pure, about 440 lines)

**Responsibility:** the envelope, the v1 registry, canonical encoding and digests, and the bounded sanitized source record. It has no clock, randomness, filesystem or state; stamps and IDs are always inputs.

**Imports (AST-checked, exact):**
- `from __future__ import annotations`;
- `dataclasses`, `hashlib`, `math`, `re`, `collections.abc.Mapping`, `types.MappingProxyType`;
- `datetime` (`datetime`, `timezone`), with an AST check banning the attribute calls `now`, `utcnow` and `today`;
- from `.forwarder_json`: `JSONDecimal`, `JSONPolicyError`, `MAX_JSON_NUMBER_CHARS`, `MAX_SAFE_INTEGER`, `canonical_json`, `parse_json`, `tagged_digest`.

**Constants:**
- Format: `SCHEMA_VERSION = 1`, `MAX_RECORD_BYTES = 16_384`, `MAX_ID_BYTES = 128`, `MAX_COMMIT_RECORDS = 8`, `MAX_SEQ = 2**53 - 1`, `MAX_GENERATION = 2**31 - 1`, `ZERO_DIGEST = "0" * 64`.
- `V1_BOUND_CEILINGS = MappingProxyType({"max_admissions": 10_000, "max_pending_fingerprints": 1_024, "ordinary_bytes": 112 * 2**20, "total_bytes": 128 * 2**20})`. These are frozen v1 ceilings that validate genesis bounds. They are independent of the reducer's mutable `DEFAULT_BOUNDS` (critic 10).
- Registry: `EVENT_TYPES = ("journal_genesis", "restart_recovery", "capacity_hold", "admission", "dedupe_decision")`. `RECORD_CLASS` maps the first three to `"recovery"` and the last two to `"ordinary"`.
- `ACTORS = ("receiver", "spawner", "forwarder", "operator")`. This follows spec L150-151 and is additive: acct L108-109 adds `billing_import`.
- `IDENTITY_KEYS = ("admission_id", "job_id", "run_id", "attempt_id", "effect_id", "operation_id", "intent_id", "reservation_id", "lease_id")` (spec L55-66).
- Decision vocabulary: `DEDUPE_RULE = "latest-admitted-v1"`, `DEDUPE_RESULTS = ("admitted", "suppressed", "pending_reduced")`, `ADMISSION_DECISIONS = ("admitted", "held")`.
- Hold vocabulary: `CAPACITY_CODES = ("capacity_admissions", "capacity_pending", "capacity_bytes")`, `DISPATCH_HOLD_CODES = CAPACITY_CODES + ("restart_recovery",)`.
- Source vocabulary: `ALERT_STATUSES = ("firing", "resolved")`, `PROVENANCE_KINDS = ("http",)`.
- Source bounds: `MAX_ALERTS = 32`, `MAX_VALUES = 64`, `MAX_SOURCE_RECORD_BYTES = 4_096`, `MAX_FINGERPRINT_BYTES = 64`, `MAX_REF_ID_BYTES = 32`, `MAX_GROUP_KEY_BYTES = 1_024`, `MAX_STARTS_AT_BYTES = 30`, `MAX_TRUNCATED_ALERTS = 2**31 - 1`.
- Digest tags: `RECORD_TAG = "rj.record.v1"`, `CONTENT_TAG = "rj.content.v1"`, `SOURCE_TAG = "rj.source.v1"`, `SOURCE_GROUP_TAG = "rj.source-group.v1"`, `DEDUPE_KEY_TAG = "rj.dedupe-key.v1"`. `BODY_TAG = "rj.body.v1"` is documented for the ingress unit and is not computed here.
- `RECORD_ERROR_CODES = {record_argument, record_digest, record_json, record_not_canonical, record_too_large, record_unsupported, record_field, record_type, record_id, record_time}`.
- `SOURCE_ERROR_CODES = {source_argument, source_shape, source_group, source_fingerprint, source_duplicate_fingerprint, source_order, source_status, source_values, source_number, source_too_many_alerts, source_too_many_values, source_too_large, source_starts_at, source_truncated, source_body_digest, source_provenance}`.

**Public API:**

```python
class RecordError(ValueError): code: str          # args == (code,)
class SourceError(ValueError): code: str

@dataclass(frozen=True) class Provenance: kind: str; path: str; line: int | None
HTTP_PROVENANCE = Provenance("http", "/notification", None)
@dataclass(frozen=True)
class SourceAlert:
    fingerprint: str; status: str                         # "firing" | "resolved"
    values: tuple[tuple[str, str | None], ...] | None     # sorted by refId; canonical number strings
    starts_at: str | None                                 # provenance only
@dataclass(frozen=True)
class SourceRecord:
    source_group: str                  # hex64
    alerts: tuple[SourceAlert, ...]    # 1..32, sorted by fingerprint, unique
    truncated_alerts: int | None       # None = unknown
    body_digest: str                   # hex64, computed by the later ingress unit
    provenance: Provenance
@dataclass(frozen=True) class Head: generation: int; commit_seq: int; event_seq: int; record_digest: str
@dataclass(frozen=True) class Stamp: boot_id: str; wall_time: str; mono_us: int
@dataclass(frozen=True) class WalFound: size: int; digest: str      # shared by store and reducer (critic 13 iv)
@dataclass(frozen=True) class Position: journal_generation: int; event_seq: int; commit_seq: int
                                        commit_index: int; commit_size: int; prev_record_digest: str
@dataclass(frozen=True) class Draft: event_id: str; event_type: str; actor: str
                                     ids: Mapping[str, str]; data: Mapping[str, object]
@dataclass(frozen=True) class Record: position: Position; stamp: Stamp; event_id: str; event_type: str
                                      actor: str; ids: Mapping[str, str]; data: Mapping[str, object]
                                      body: bytes; record_digest: str

def validate_id(value: object) -> str                     # record_id
def canonical_number(value: int | JSONDecimal) -> str     # source_number
def is_canonical_number(text: object) -> bool
def source_group_digest(group_key: str) -> str            # source_group
def validate_source(source: object) -> SourceRecord       # exact type + full re-validation
def source_to_json(source: SourceRecord) -> dict[str, object]
def source_from_json(value: object) -> SourceRecord       # strict; never re-sorts
def source_digest(source: SourceRecord) -> str            # rj.source.v1 over source_to_json(source)
def dedupe_key(source: SourceRecord) -> str               # rj.dedupe-key.v1 (definition in "Sanitized source record")
def format_wall_time(epoch_ns: int) -> str                # record_time
def thaw(value: object) -> object                         # MappingProxyType -> dict, tuple kept; recursive
def seal(draft: Draft, position: Position, stamp: Stamp) -> Record
def verify_body(body: bytes, record_digest: str) -> dict  # raw-byte digest, then strict parse (critic 2)
def decode_record(envelope: dict, body: bytes, record_digest: str) -> Record   # canonical + typed
def open_record(body: bytes) -> Record                    # verify_body + decode_record (tests, live checks)
def content_digest(record: Record) -> str                 # computed on demand; never stored
```

**Frozen mappings and encoding (critic 13 i).** `Record.ids` and `Record.data` are deep-frozen views: `MappingProxyType` for objects and tuples for arrays. `canonical_json` accepts only exact `dict` objects, so `seal`, `content_digest` and every digest helper encode from `thaw(...)` copies. `body` bytes are the source of truth.

**`verify_body`** checks `hashlib.sha256(b"rj.record.v1\x00" + body).hexdigest() == record_digest` **before** any parsing, raising `record_digest` on a mismatch. It then runs `parse_json(body, max_bytes=MAX_RECORD_BYTES, numbers="integer", ascii_only=True)`, raising `record_json`. The digest is computed from the raw bytes, not by re-canonicalizing (critic 15).

**`decode_record`** requires `canonical_json(parsed, ascii_only=True) == body` (`record_not_canonical`), then runs the envelope and per-type validators.

**`validate_source`** requires `type(source) is SourceRecord` and `source_from_json(source_to_json(source)) == source`, so a forged or mutated frozen instance is re-validated.

**Split point.** If the module exceeds about 520 lines, the source-record section (about 200 lines) moves to `journal_source.py` with the same API and the same owner.

### Module 2: `journal_reducer.py` (pure, about 350 lines)

**Responsibility:** the projection and every decision. Plan functions build sealed records. `verify_commit` re-derives every journal-computed field from a projection and the records and raises on any difference. `apply_delta` and `replay` complete the fold. The live path and replay call the same functions.

**Imports (AST-checked, exact):** `from __future__ import annotations`; `dataclasses`; `hashlib`; `collections.abc` (`Iterable`, `Iterator`, `Sequence`); `types.MappingProxyType`; from `.forwarder_json`: `canonical_json`, `tagged_digest`; named symbols from `.journal_records`. No clock, randomness, OS, filesystem, `sqlite3` or `threading`.

```python
RECORD_OVERHEAD_BYTES = 384          # charged per record; probe p3 measured 381
REPLAY_ERROR_CODES = frozenset({"replay_chain", "replay_framing", "replay_generation", "replay_boot",
    "replay_clock", "replay_tail_incomplete", "replay_shape", "replay_mismatch"})
class ReplayError(ValueError): code: str

@dataclass(frozen=True)
class JournalBounds:                           # defaults may be lowered later; validation uses V1_BOUND_CEILINGS
    max_admissions: int = 10_000               # per generation, suppressed included
    max_pending_fingerprints: int = 1_024
    ordinary_bytes: int = 112 * 2**20
    total_bytes: int = 128 * 2**20             # total - ordinary = 16 MiB recovery reserve
DEFAULT_BOUNDS = JournalBounds()

@dataclass(frozen=True) class Baseline: admission_id: str; dedupe_key: str; complete: bool
@dataclass(frozen=True) class PendingEntry: fingerprint: str; admission_id: str; arrival_seq: int
                                            source_group: str; status: str; values: tuple | None
@dataclass(frozen=True) class CapacityRefusal: code: str; limit: int; observed: int; requested: int
@dataclass(frozen=True) class Plan: records: tuple[Record, ...]; charge: int; outcome: Mapping[str, object]
@dataclass(frozen=True) class Delta: ...                  # opaque; built only by verify_commit

class Projection:                # plain mutable fields
    journal_uuid: str | None; generation: int; bounds: JournalBounds | None
    head: Head | None; boot_id: str | None; last_mono_us: int; seen_boot_ids: set[str]
    logical_bytes: int; admission_count: int; last_arrival_seq: int
    baselines: dict[str, Baseline]; pending: dict[str, PendingEntry]
    dispatch_holds: dict[str, int]                        # code -> commit_seq that set it

def new_projection() -> Projection
def plan_genesis(*, journal_uuid: str, bounds: JournalBounds, event_id: str, stamp: Stamp) -> Plan
def plan_restart(p, *, event_id: str, stamp: Stamp, anchor_lag: int,
                 wal_found: WalFound | None) -> Plan | CapacityRefusal
def plan_admission(p, source: SourceRecord, *, admission_id: str, dedupe_event_id: str,
                   stamp: Stamp) -> Plan | CapacityRefusal
def plan_capacity_hold(p, refusal: CapacityRefusal, *, event_id: str, stamp: Stamp,
                       refused_source_digest: str) -> Plan | CapacityRefusal | None
def verify_commit(p: Projection, records: Sequence[Record]) -> Delta   # pure; ReplayError
def apply_delta(p: Projection, delta: Delta) -> None                   # plain assignments; cannot fail
def group_commits(records: Iterable[Record]) -> Iterator[tuple[Record, ...]]
def replay(records: Iterable[Record]) -> Projection
def dispatch_holds(p) -> tuple[str, ...]                               # sorted
def pending_entries(p) -> tuple[PendingEntry, ...]                     # sorted by fingerprint
def pending_digest(p) -> str
def state_digest(p) -> str
```

There is no slice class hierarchy. Later units add plain projection fields that only their own record types write (extension rule R4).

### Module 3: `journal_store.py` (I/O, about 440 lines, of which the anchor is about 150)

**Responsibility:** physical storage only. That covers:
- capability, path, permission and lock checks;
- the SQLite connection and settings, and the exact DDL;
- the ordered row-verification pipeline and SQLite error classification;
- duplicate lookup and the append transaction;
- the anchor file and the sync primitive.

It knows nothing about admission semantics.

**Imports (AST-checked, exact):** `from __future__ import annotations`; `dataclasses`; `errno`; `fcntl`; `hashlib`; `os`; `sqlite3`; `stat`; `struct`; `sys`; `collections.abc`; `pathlib.Path`; from `.forwarder_json`: `JSONPolicyError`, `canonical_json`, `parse_json`; named symbols from `.journal_records`. No `socket`, `subprocess`, `http`, `threading`, `time` or `logging`.

```python
DB_FILENAME = "journal.sqlite3"; WAL_FILENAME = "journal.sqlite3-wal"
ANCHOR_FILENAME = "anchor"; LOCK_FILENAME = "lock"
APPLICATION_ID = 0x524A4E4C          # "RJNL"
USER_VERSION = 1; MIN_SQLITE_VERSION = (3, 37, 0)
PAGE_SIZE = 4_096; MAX_PAGE_COUNT = 40_960; JOURNAL_SIZE_LIMIT = 8 * 2**20
ANCHOR_BYTES = 8_192; ANCHOR_SLOT_BYTES = 1_024; ANCHOR_SLOT_OFFSETS = (0, 4_096)
ANCHOR_MAGIC = b"RJANCHOR"; ANCHOR_FORMAT = "rj.anchor.v1"; MAX_ANCHOR_BODY_BYTES = 960
WAL_TAG = b"rj.wal.v1"
SCHEMA_SQL: tuple[str, ...]          # the exact DDL below
RECOVERY_HOLD_CODES: frozenset[str]; PROCESS_HOLD_CODES: frozenset[str]; STORE_ERROR_CODES: frozenset[str]
RECOVERY_SQLITE_PRIMARY = frozenset({sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB})   # 11, 26

class StoreError(Exception): code: str
@dataclass(frozen=True) class AnchorHold: code: str; boot_id: str; observed_commit_seq: int | None
@dataclass(frozen=True) class AnchorState: journal_uuid: str; counter: int; head: Head; hold: AnchorHold | None
@dataclass(frozen=True) class Finding: code: str; scope: str; sqlite_error: str | None   # scope "recovery" | "process"
@dataclass(frozen=True) class Duplicate: event_seqs: tuple[int, ...]

def no_ckpt_supported() -> bool      # Connection.setconfig and SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE exist
def classify_sqlite_error(error: sqlite3.Error) -> Finding

class JournalStore:
    @classmethod
    def create(cls, directory: Path, genesis: Record, *, journal_uuid: str) -> "JournalStore"
    @classmethod
    def open(cls, directory: Path) -> "JournalStore"   # never creates a DB, WAL or anchor
    finding: Finding | None; anchor: AnchorState | None; wal_found: WalFound | None
    verified_head: Head | None      # last fully verified commit, for AnchorHold.observed_commit_seq
    def rows(self) -> Iterator[Record]                 # ordered pipeline; stops at the first finding
    def finish_open(self) -> None                      # query_only=OFF
    def write_anchor(self, head: Head) -> None         # re-anchor at open (lag 1)
    def persist_hold(self, code: str, *, boot_id: str) -> bool
    def find_duplicate(self, records: Sequence[Record]) -> Duplicate | None   # read-only; conflict raises
    def append(self, records: Sequence[Record], *, sync_directory: bool = False) -> tuple[int, ...]
    def close(self) -> None
    # private seams patched by tests: _connect, _commit_sql, _write_slot, _read_anchor;
    # module-level _full_sync(fd) and _encode_slot(state) -> bytes
```

`open` and `create` raise `StoreError` only for failures that cannot be inspected safely: argument, capability (`sqlite_unsupported`), path, permissions, lock contention, unsupported platform sync, and an existing journal at create. Integrity and transient findings are returned in `finding`.

### Module 4: `recovery_journal.py` (I/O shell, about 270 lines)

**Responsibility:** the Receiver-facing object. It owns one `threading.Lock` that serializes every public operation, clock and ID reading, the latch state, and the mapping of store and reducer codes to holds.

**Imports (AST-checked, exact):** `from __future__ import annotations`; `dataclasses`; `threading`; `time`; `uuid`; `collections.abc`; `pathlib.Path`; `types.MappingProxyType`; named symbols from `.journal_records`, `.journal_reducer` and `.journal_store`. No `sqlite3`, `os`, `fcntl`, `socket`, `subprocess` or `http`.

```python
JOURNAL_ERROR_CODES: frozenset[str]; HOLD_SCOPES = ("recovery", "process")
class JournalError(Exception): code: str

@dataclass(frozen=True)
class AdmissionReceipt:
    admission_id: str; arrival_seq: int; commit_seq: int; event_seqs: tuple[int, int]
    result: str; decision: str; dispatch_holds: tuple[str, ...]
    source_group: str; dedupe_key: str; superseded: tuple[tuple[str, str], ...]   # (fingerprint, admission_id)

def new_id() -> str                                    # str(uuid.uuid4()), lowercase (acct L71)
def create_recovery_journal(directory: Path, *, bounds: JournalBounds = DEFAULT_BOUNDS,
        wall_clock: Callable[[], int] = time.time_ns, mono_clock: Callable[[], int] = time.monotonic_ns,
        id_factory: Callable[[], str] = new_id) -> "RecoveryJournal"
def open_recovery_journal(directory: Path, *, wall_clock=time.time_ns, mono_clock=time.monotonic_ns,
        id_factory=new_id) -> "RecoveryJournal"

class RecoveryJournal:
    state: str                           # "ready" | "held" | "closed"  (read-only property)
    hold: tuple[str, str] | None         # (code, scope)
    dispatch_holds: tuple[str, ...]
    def admit(self, source: SourceRecord) -> AdmissionReceipt
    def pending(self) -> tuple[PendingEntry, ...]
    def snapshot(self) -> dict[str, object]
    def close(self) -> None
    def __enter__(self) -> "RecoveryJournal"; def __exit__(self, *exc) -> None
    def _commit(self, plan: Plan) -> tuple[int, ...]    # the only write path; seam for later writers
```

**IDs.** Every ID the journal mints comes from `id_factory` (critic 12): `journal_uuid`, every `boot_id`, `admission_id`, and every other `event_id`. A test factory can therefore make the records deterministic, apart from the random WAL salts reflected in `wal_found`.

**Held handles.** `open_recovery_journal` raises `JournalError` only for failures that cannot be inspected safely. Every integrity or transient finding returns a **held** journal. Its `snapshot()` is readable, and every `admit` raises `journal_held`. This is the `ReceiptLedger` held-but-readable pattern: a later integration can answer 503 with a visible reason instead of hiding it behind a missing object.

**Size.** The targets are about 440 + 350 + 440 + 270 = about 1,500 source lines. Revision 1 targeted about 1,420; the critic fixes add about 80. If review finds more than about 1,550, split into:
- **15a:** `journal_records` + `journal_store` and their tests;
- **15b:** `journal_reducer` + `recovery_journal`, the crash suite and the adversarial suite.

The store does not import the reducer, so the cut is clean.

## Storage and durability

### Files, ownership and locks

```
<journal_dir>/            0700, owned by euid, not a symlink; made by deployment, never by this code
  journal.sqlite3         0600; pre-created with O_CREAT|O_EXCL|O_NOFOLLOW before SQLite opens it
  journal.sqlite3-wal     0600 (SQLite copies the DB mode; probe p6); kept across closes (probe p7); no -shm
  anchor                  0600; exactly 8,192 bytes; two 1,024-byte slots at offsets 0 and 4,096
  lock                    0600; flock(LOCK_EX|LOCK_NB) held for the journal's lifetime
```

- Every path is checked with `os.lstat`: the directory must be `S_ISDIR`, each file `S_ISREG`, and no path a symlink. The owner must be `os.geteuid()`, `st_mode & 0o077` must be 0, and every file must have `st_nlink == 1`, so a hard link from elsewhere is refused.
- Files this code opens itself use `O_NOFOLLOW | O_CLOEXEC`.
- **Single writer.** `fcntl.flock` on `lock` fails with `EWOULDBLOCK` for a second opener, including in the same process (J1 P3). `PRAGMA locking_mode=EXCLUSIVE` is set as the first statement, so any other SQLite connection gets "database is locked" (J1 P1). `mode=ro` is not an inspection path, because under EXCLUSIVE it fails with `SQLITE_IOERR_LOCK` 3850 (critic q1). Operators inspect only through `snapshot()`.
- `open` checks that at least one of DB, WAL or anchor exists before it opens or creates `lock`. It then repeats every file check under the lock.

### Connection settings (each set, then read back)

| Setting | Value | Why |
|---|---|---|
| `sqlite3.connect(f"file:{db}?mode=rw", uri=True, isolation_level=None, check_same_thread=False)` | | `mode=rw` never creates. Explicit transactions only. Used only under the journal lock. |
| `setconfig(SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)` | set **immediately after connect, before the first statement**, read back with `getconfig`, **never cleared** | Close never checkpoints or deletes the WAL, so no open (held or ready) can destroy evidence. Probe p7: without it, a held open plus close of a mid-WAL-flip image deleted the WAL, including frames of 10 committed rows; with it, DB and WAL stayed byte-identical (critic 1). Requires Python ≥ 3.12 (P26). |
| `locking_mode` | `EXCLUSIVE` (first statement) | Single writer; the WAL index lives in heap memory, so there is no `-shm`. |
| `journal_mode` | set to `WAL` **only by `create`**; `open` only **reads** it and requires `wal` | A hold must not write the header, and setting a mode on a non-WAL file writes. |
| `synchronous` | `FULL` (2) | The WAL is synced at every COMMIT. `NORMAL` survives a process crash but not power loss. |
| `fullfsync`, `checkpoint_fullfsync` | `ON` (1) | `F_FULLFSYNC` on darwin: a commit takes about 19 ms with ON and about 0.2 ms with OFF (J1 P1). Ignored on Linux. |
| `trusted_schema` | `OFF` | Triggers run no untrusted functions. |
| `cell_size_check` | `ON` | Extra B-tree checking on read. |
| `max_page_count` | 40,960 (160 MiB) | Physical backstop above the 128 MiB logical budget. `SQLITE_FULL` latches `journal_write_failed`. |
| `journal_size_limit` / `wal_autocheckpoint` | 8 MiB / 1,000 pages | Bounds the WAL after checkpoints. |
| `query_only` | `ON` during open verification, `OFF` after | Nothing is written before verification completes. |
| `page_size` | 4,096, at create, before the first write | |
| `application_id` / `user_version` | `0x524A4E4C` / 1, set inside the genesis transaction | Probe p6: both roll back with the transaction. |

**Readback failures.** A readback mismatch raises `sqlite_unsupported`, and so does a missing no-checkpoint capability. `create` and `open` check that capability first, with `no_ckpt_supported()`, before touching any file, and fail closed on Python 3.11 (critic 1).

**WAL lifetime.** Because close never checkpoints, the WAL keeps its inode across closes and reopens (probe p7). A clean close leaves recent commits only in the WAL, so backups must copy the whole directory. Checkpoints still happen automatically during commits (`wal_autocheckpoint`).

### Schema (exact DDL; compared at open with every `sqlite_schema` row as `(type, name, tbl_name, sql)`)

```sql
CREATE TABLE journal_events (
  event_seq     INTEGER PRIMARY KEY CHECK (event_seq >= 1),
  event_id      TEXT NOT NULL UNIQUE CHECK (length(event_id) BETWEEN 1 AND 128),
  event_type    TEXT NOT NULL CHECK (length(event_type) BETWEEN 1 AND 64),
  body          BLOB NOT NULL CHECK (length(body) BETWEEN 2 AND 16384),
  record_digest TEXT NOT NULL UNIQUE CHECK (length(record_digest) = 64)
) STRICT;
CREATE TRIGGER journal_events_no_update BEFORE UPDATE ON journal_events
  BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER journal_events_no_delete BEFORE DELETE ON journal_events
  BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER journal_events_contiguous BEFORE INSERT ON journal_events
  WHEN NEW.event_seq != (SELECT coalesce(max(event_seq), 0) + 1 FROM journal_events)
  BEGIN SELECT RAISE(ABORT, 'event_seq'); END;
```

- **No projection tables.** The projection is rebuilt from the verified chain at every open.
- **No `content_digest` column.** This changed in revision 2. The content digest is computed on demand, only on the duplicate path, so open does no per-record re-canonicalization for it (critic 15).
- **`event_id` and `event_type` duplicate body fields.** They serve the UNIQUE index and the duplicate lookup. Open verifies them against the digest-verified body.
- **Triggers are defence in depth against our own bugs.** A same-uid process can drop them; the exact DDL compare turns a dropped trigger, or an extra table or index, into a hold.
- **STRICT has limits.** It still coerces lossless text into INTEGER (J1 P4), so typed validation happens in Python before binding.
- **Ticket 38.** Its records join this table as an additive record family, with no DDL change (J2 graft 4).

### Anchor file (the one custom durability path)

A hash chain cannot detect a lost **suffix**, because every prefix of a valid chain is valid. SQLite silently drops committed transactions when the WAL is truncated or a middle frame is damaged, and `integrity_check` still says `ok` (J1 P2). The anchor records the last anchored commit outside SQLite's files.

**Slot layout:** `ANCHOR_MAGIC` (8 bytes), then `u32be L` with 1 ≤ L ≤ 960, then L bytes of canonical ASCII JSON, then `sha256(MAGIC || u32be L || body)` (32 bytes). Every remaining byte up to the next slot offset, or to the end of the file, is zero.

**Body** (worst case 503 bytes, probe p3):

```
{"counter":int,"format":"rj.anchor.v1",
 "head":{"commit_seq":int,"event_seq":int,"generation":int,"record_digest":hex64},
 "hold":null|{"boot_id":id,"code":<recovery hold code>,"observed_commit_seq":int|null},
 "journal_uuid":<lowercase uuid>}
```

`observed_commit_seq` is the `commit_seq` of the last commit group that fully verified before the finding, or `null` when the finding precedes the row scan (critic 13 vi).

**Write.**
1. Set `c = counter + 1` and `slot = c % 2`.
2. `os.pwrite` the full 1,024-byte slot at its offset. A short write is a failure.
3. `_full_sync(fd)`.

The in-memory anchor advances only after the sync returns. The slot being written never holds the newest valid state, so a torn write can damage only the older one. The file size never changes after creation.

**Read.** A slot is *intact* when its magic, length range, checksum and zero padding pass, and its body parses as canonical JSON.
- An intact slot whose `format` is not `rj.anchor.v1`, whose hold `code` is not a v1 recovery code, or whose key set differs from the v1 set is a **newer format**. If it is the newest intact slot, the result is the process hold `journal_schema_unsupported`, and the anchor is never rewritten (critic 14).
- An intact v1 slot is *valid* when its types check and `counter % 2 == slot index`. The newest valid counter wins.
- The file is **invalid** (`journal_anchor_invalid`) when:
  - its size is not 8,192, or no slot is intact;
  - two valid slots have counters that differ by anything other than 1, or different `journal_uuid`s;
  - the newer slot's head is behind the older's;
  - the older slot carries a hold and the newer one does not.

**Sync primitive (fail-closed).** `_full_sync(fd)` is `fcntl.fcntl(fd, fcntl.F_FULLFSYNC)` on `sys.platform == "darwin"` and `os.fsync(fd)` on `"linux"`.
- Any other platform, or darwin without `fcntl.F_FULLFSYNC`, raises `journal_sync_unsupported` at create or open.
- Any exception from the sync propagates as a write failure. **It never falls back.**
- Probe p2: `F_FULLFSYNC` on `/dev/null` fails with `ENODEV`, so the failure path is real.

**Cost.** An admission costs 38.8 ms median on macOS, two full syncs (critic q3). Captured Grafana delivery rates are a few Notifications per minute.

### Genesis (explicit create only)

1. Check the no-checkpoint capability (`sqlite_unsupported`), the platform sync and the directory.
2. Open or create `lock` and take the flock. DB, WAL and anchor must all be absent, or the result is `journal_exists`.
3. Pre-create `journal.sqlite3` with `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW`, mode 0600, and close it.
4. Connect, `setconfig(NO_CKPT_ON_CLOSE)`, then the settings, including `page_size` and `journal_mode=WAL` before the first write, with readbacks.
5. In one synced transaction (probe p6): `BEGIN IMMEDIATE`; `PRAGMA application_id`; `PRAGMA user_version`; the DDL; `INSERT` genesis; `COMMIT`.
6. `_full_sync(directory fd)`, which makes the DB and WAL directory entries durable. `F_FULLFSYNC` works on a directory fd (probe p2).
7. Create `anchor` with `O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW`, mode 0600. `ftruncate` it to 8,192 bytes, write slot 1 (counter 1, naming the genesis head), then `_full_sync(fd)` and `_full_sync(directory fd)`.
8. Return a ready journal. There is no `restart_recovery`, because the create boot is the genesis boot.

A failure or crash between steps 3 and 7 raises `journal_create_failed` and leaves the files in place:
- `open` then gives the held `journal_anchor_missing` or `journal_anchor_invalid`;
- `create` gives `journal_exists`;
- nothing was ever acknowledged, so the operator removes the files and creates again.

The code never deletes anything.

### Duplicates and append (the only write path)

**`find_duplicate(records)`** is a read-only lookup of every `event_id`, run before verification and before any write:
- **none stored:** returns `None`;
- **exact duplicate:** every record is stored in the same order, forming exactly one stored commit group, and each has an equal on-demand `content_digest`. It returns `Duplicate(stored event_seqs)` (spec L101-102).
- **any other overlap:** raises `store_event_conflict`.

**`append(records, *, sync_directory=False)`** runs under the journal lock:
1. `_commit_sql(records)`: `BEGIN IMMEDIATE`, one `INSERT` per record, `COMMIT`.
2. When `sync_directory` is set, `_full_sync(directory fd)`. Open uses this for the `restart_recovery` commit (critic 11).
3. `_write_slot(head of the last record)`: `pwrite`, then `_full_sync`.
4. **Failure.** Any `sqlite3.Error` or `OSError`, including a UNIQUE or contiguity violation, `SQLITE_FULL` and a failed sync, attempts a `ROLLBACK` outside the handler and raises `store_write_failed`. A `completed` flag checked in `finally` marks the store broken on any other non-clean exit, including a test's `SimulatedCrash(BaseException)`. After that it refuses every append.

**Lag invariant.** Every commit is followed by its anchor write before the next commit can begin, and open re-anchors a lagging head **before** it appends anything. Together these keep the anchor at most one commit behind the durable head across any sequence of crashes. Probe p5 enumerated every sequence of up to three crashes:
- with this order, the maximum lag is 1 and no path would hold;
- with `design-sqlite`'s original order, 24 paths reach lag 2 (J1 S-E1).

### What an acknowledgement proves

`admit` returns an `AdmissionReceipt` if and only if, in order under the journal lock:
1. the lookup found none of the planned `event_id`s;
2. `verify_commit` accepted the planned records against the live projection;
3. `BEGIN IMMEDIATE` and both INSERTs succeeded, with constraints and triggers passing;
4. `COMMIT` returned OK under WAL, `synchronous=FULL` and `fullfsync=ON`, so SQLite wrote the commit frame and issued its WAL sync (`F_FULLFSYNC` on darwin, or a silent plain-`fsync` fallback, as explained under "Durability primitives");
5. the anchor slot naming this commit (`commit_seq`, last `event_seq`, `record_digest`) was written in full and synced by `F_FULLFSYNC` on darwin or `os.fsync` on Linux, with no fallback.

It is never an in-memory callback (spec L152-153). It does **not** prove:
- that the device honours flushes;
- that the venue volume survives a pod restart;
- that no consistent rollback of all files happens later;
- that Grafana received the 202;
- any Run or effect;
- that Runs cannot reach the journal.

### Durability primitives, stated precisely

**darwin, SQLite side.** `fullfsync=ON` makes SQLite issue `F_FULLFSYNC` for WAL syncs; the latency difference confirms it (J1 P1). SQLite's `os_unix.c` `full_fsync` **falls back to plain `fsync()` when `fcntl(F_FULLFSYNC)` fails, and reports success.** That comes from source reading and was **not probed**: no failing volume was available. A successful COMMIT alone proves at most an `fsync`.

**darwin, anchor side.** The anchor sync is what makes the acknowledgement fail closed.
- On a volume without `F_FULLFSYNC` support, the anchor sync fails, so no admission is ever acknowledged there (tests C8, E14).
- Where the anchor's `F_FULLFSYNC` succeeds, Apple documents it as asking the drive to flush all buffered data. That would include WAL pages a fallback `fsync` handed to the drive, but this rests on documentation and is not qualified.

**WAL directory entry (critic 11).** SQLite syncs a newly created WAL's directory with a plain `fsync` and ignores errors (os_unix.c `unixSync`; source reading via the critic). The journal therefore full-syncs the directory at genesis, and again after every `restart_recovery` COMMIT, before that commit's anchor write and before any later acknowledgement. The WAL is normally never deleted, because close never checkpoints (probe p7). If the WAL was removed and SQLite recreated it at open, this sync makes its entry durable. The residual gap, the directory metadata between genesis and a later deletion, is stated under "Residual risks".

**Linux.** `fullfsync` is ignored. SQLite syncs the WAL with `fsync` or `fdatasync`, and the anchor uses `os.fsync`. With default ext4 and XFS barriers these flush the device cache. The suite runs on macOS, so the Linux path is covered only by primitive selection unless it also runs in a Linux container.

**After a sync error: latch, never retry in-process.** The kernel may mark failed pages clean and report a later `fsync` as success ("fsyncgate").
- A fresh process on the same kernel reads **kernel-visible state**, which can include pages that never reached disk, and may adopt such a commit as the one-commit lag.
- If those pages are later lost, the anchor, which was synced after the adoption, turns the loss into a detected `journal_truncated` rather than silent loss, provided the anchor's own sync was honest (J1 S-E3).

**Process crash versus power loss.** A kill leaves kernel-visible writes intact without any sync. Crash-image tests model that case; power-loss variants are simulated by editing images (tests E3, E8).

### Open sequence (full verification before any prefix is applied; spec L242)

1. **Capability, arguments, directory, platform and version.** A missing no-checkpoint capability raises `sqlite_unsupported`, before any file is touched. Other failures raise `journal_path_invalid`, `journal_permissions`, `journal_sync_unsupported`, or `sqlite_unsupported` for SQLite below 3.37.
2. **Presence and lock.** If DB, WAL and anchor are all absent, raise `journal_missing`. Nothing is created, so a failed mount never becomes a fresh journal (spec L262-263). Otherwise take the lock (`journal_locked`) and repeat the file checks (`journal_permissions`).
3. **Read the anchor** with one full read:
   - absent: `journal_anchor_missing`;
   - malformed: `journal_anchor_invalid`;
   - newest intact slot in a newer format: process `journal_schema_unsupported`;
   - `OSError`: process `journal_open_failed`.
4. **Persisted verdict.** If the newest valid slot carries a hold, return held with that code (scope `recovery`). SQLite is never opened.
5. **Anchor missing or invalid.** Return held (recovery). The anchor is evidence and is never rewritten.
6. **DB absent** while the anchor is valid: `journal_truncated`, persisted, held.
7. **Record `wal_found`:** the size and streamed `sha256(WAL_TAG || 0x00 || bytes)` of the WAL, or `None` when it is absent. This happens before SQLite touches it. An `OSError` gives process `journal_open_failed`.
8. **Connect.** `setconfig(NO_CKPT_ON_CLOSE, True)` with `getconfig` readback, before the first statement; then the settings with readbacks, without setting `journal_mode`; then `query_only=ON`.
9. **Presentation and format checks**, in order:
   1. **Empty presentation:** no `sqlite_schema` rows, `application_id` 0 and `user_version` 0 give `journal_truncated`. This is what a lost or dropped genesis WAL frame looks like (critic 5).
   2. `application_id` differs: `journal_identity_mismatch`.
   3. `user_version > 1`: process `journal_schema_unsupported`.
   4. Any other `user_version`, DDL other than `SCHEMA_SQL`, or `journal_mode` not `wal`: `journal_schema_invalid`.
   5. `PRAGMA integrity_check` not exactly `[("ok",)]`: `journal_corrupt`.
10. **Row pipeline** `ORDER BY event_seq`. Physical checks come **before** typed checks (critic 2), and the scan stops at the first finding:
    1. **Digest:** `verify_body`'s raw-byte check against the `record_digest` column fails: recovery `journal_record_invalid`.
    2. **Parse:** strict parse of a digest-verified body fails: process `journal_schema_unsupported`.
    3. **Chain:** the body's `event_seq` must be an exact int equal to the column and to the previous row's + 1, and `prev_record_digest` must be hex64 equal to the previous row's `record_digest` (`ZERO_DIGEST` at 1). A present, well-typed field that disagrees gives recovery `journal_chain_broken`. An absent or ill-typed field gives process `journal_schema_unsupported`.
    4. **Columns:** the `event_id` and `event_type` columns must equal present, `str`-typed body fields, else recovery `journal_record_invalid`; absent or ill-typed body fields give process. An `event_id` already seen in this scan gives recovery `journal_event_conflict` (defence in depth; unreachable while the UNIQUE index and `integrity_check` hold).
    5. **Typed:** `decode_record` (canonical round trip, envelope and per-type validators, bounds, versions, enums, `rule`) fails: process `journal_schema_unsupported`, **never persisted**.
    6. **Framing:** `group_commits` framing or generation failure gives recovery `journal_chain_broken`; a final incomplete group gives recovery `journal_tail_unverified`.
    7. **Replay:** `verify_commit`/`apply_delta` on a **candidate** projection. `replay_shape`, `replay_mismatch`, `replay_boot` and `replay_clock` give recovery `journal_replay_mismatch`.
11. **Anchor agreement:**
    - the record at `anchor.event_seq` must exist, be the last record of commit `anchor.commit_seq`, have an equal `record_digest`, and carry a `journal_generation` equal to `anchor.head.generation`, else `journal_anchor_conflict` (critic 14);
    - the genesis `journal_uuid` must equal the anchor's, else `journal_identity_mismatch`;
    - `head.commit_seq < anchor.commit_seq` gives `journal_truncated`;
    - `head.commit_seq - anchor.commit_seq > 1` gives `journal_tail_unverified`;
    - a difference of 1 is the legitimate C3/C4 window (lag 1).
12. **On a finding:** persist a recovery finding into the anchor (see "Where a durable verdict lives"), **then** close the connection. Because no-checkpoint-on-close is set, nothing is checkpointed or deleted. Return held; the live projection is never installed.
13. **On success:**
    1. Record `verified_state_digest = state_digest(candidate)` (critic 12), install the candidate, and set `query_only=OFF`.
    2. **If the lag is 1, `write_anchor(head)` runs first** (J1 graft 1).
    3. Then `plan_restart(anchor_lag, wal_found)`, and `_commit` with `sync_directory=True`.
    4. A re-anchor or commit failure latches `journal_write_failed`. A `CapacityRefusal` from `plan_restart` latches `journal_capacity_recovery`.

**SQLite errors during steps 8-10 (critic 4).** Python's `sqlite_errorcode` is the **extended** code; a UNIQUE violation reports 2067 (critic q2).
- `classify_sqlite_error` uses the primary code `sqlite_errorcode & 0xFF`.
- Primary `SQLITE_CORRUPT` (11), which covers `CORRUPT_INDEX` 779, `CORRUPT_SEQUENCE` 523 and `CORRUPT_VTAB` 267, and `SQLITE_NOTADB` (26; header damage, probe p2) give recovery `journal_corrupt`.
- Every other code, including IOERR 10, `IOERR_SHORT_READ` 522, `IOERR_LOCK` 3850, CANTOPEN 14, BUSY 5 and FULL 13, a missing `sqlite_errorcode` attribute (hand-built exceptions), and any `OSError`, gives process `journal_open_failed`.
- `sqlite_errorname` (a fixed identifier) is kept in `Finding.sqlite_error` and shown in the snapshot.
- These attributes exist on module-raised errors from Python 3.11 on; only 3.13 was probed.

**Why the order matters (critic 2).** A digest- and chain-verified row is exactly what some writer wrote. A typed failure on such a row therefore means a writer of a different version (or a bug), not corruption. It stays a visible process hold and is never persisted, so a rollback binary cannot brick the journal for the roll-forward (R1, R2).

A physical failure, meaning the digest, the chain, the columns, the anchor, or a framing or semantic contradiction under a *known* version and rule, is durable. Under R1 and R6, no legitimate writer of any version produces a semantic contradiction under a known version and `rule`. That is why `replay_mismatch` stays durable (spec L128-129, L243).

The first finding stops the scan. A process finding can therefore hide a later physical failure until a binary that understands the row opens the journal; the journal is held either way.

**Open cost (critic 15).** Probe p8, for 2,000 realistic pairs (4,000 records of 1,099 bytes mean): raw-byte digests 20 ms, strict parse 1.59 s, canonical round trip 1.13 s, re-derivation digests 0.29 s, 3.0 s in total.
- Extrapolated, that is about 15 s for 10,000 realistic pairs, and about 20 s with typed validation, replay bookkeeping and `integrity_check`.
- Adversarial 5-9 KiB bodies at the byte bound come to about 1.5-2 minutes.
- The Receiver cannot admit during open.
- E18 measures an open at 2,000 pairs and records it without asserting it. `docs/recovery-journal.md` states the budget.
- The canonical round trip is the first optimization candidate (Deferred 11).

### Where a durable verdict lives

This section resolves the J1/J2 conflict about sticky integrity holds, refined by critic 2 and 3.

**Verified physical failures are durable recovery holds** (spec L242-247). The bytes were read without an I/O error, and they prove a violation:
- a digest or chain mismatch, a column/body mismatch, or a framing contradiction;
- `integrity_check` failure, or primary `SQLITE_CORRUPT`/`SQLITE_NOTADB`;
- two stored rows sharing an `event_id`;
- a head below the anchor, including an empty presentation with a valid anchor;
- more than one commit beyond the anchor, or an incomplete final commit group;
- a semantic contradiction under a known version and `rule`;
- a DDL, format or `journal_mode` mismatch at `user_version` 1;
- a missing or invalid anchor.

**Transient, environmental or writer-format findings are process holds.** These are:
- an `OSError`, or a SQLite error whose primary code is not 11 or 26, while opening or reading;
- a newer format: `user_version > 1`, a newer anchor slot, or any typed failure on a digest- and chain-verified row;
- the missing no-checkpoint capability, which raises instead.

They are visible in the snapshot, never persisted, and a later open retries. So a flaky mount at startup cannot brick admission (J2 sqlite 1), and a rollback cannot either (critic 2).

**Where the verdict is stored.** In the anchor. When the newest valid slot has `hold: null` and open finds a recovery finding, `persist_hold` writes the hold into **both** slots in turn: counter n+1, then n+2, each with a full `pwrite` plus `_full_sync`. The slots keep the anchor's own head, not the DB's. After both writes no slot without the hold remains, and a torn second write leaves the first hold slot as the newest valid one.

The verdict is persisted before the SQLite connection closes. The writer refuses any later slot without a hold, and the reader treats "older slot held, newer slot not" as `journal_anchor_invalid`. Every open reads the anchor first; when it carries a hold, SQLite is never opened. When the anchor itself is the failure (absent, or no intact slot), it cannot carry the verdict: it is left byte-identical as evidence, and every open re-derives the same verdict from those unchanged bytes.

**Persisted verdicts need stored evidence (critic 3).** Every persisted code corresponds to bytes that remain on disk. Nothing is checkpointed, deleted or rewritten, because of no-checkpoint-on-close and the append-only rules. An append-time `event_id` overlap is refused before anything is written, so it leaves no evidence. It is therefore the process hold `journal_divergence`, not a persisted verdict (see "Admission").

**Why replacing files cannot silently clear it, and exactly when it can:**
- Replacing or repairing `journal.sqlite3` or `-wal` after a persisted hold changes nothing, because they are never read (test F6a).
- Deleting or damaging the anchor gives `journal_anchor_missing` or `journal_anchor_invalid`, which is still held. Zeroing the newest hold slot leaves the other hold slot (F6b, F6c).
- **Non-claim:** a *consistent* replacement of DB, WAL and anchor with an older self-consistent set clears it silently, as it would hide any rollback (F6d). So does a same-uid process writing a valid hold-free anchor, since the digests are unkeyed. Detecting either needs the off-volume anchor of a later handoff unit (integ L84).
- A verdict whose persistence write failed, for example on a read-only volume, is held in-process with `persisted: false`. The next open re-derives it from the unchanged bytes.
- A false positive from storage that once returned wrong bytes without an error is persisted too. That is the conservative reading of spec L245; see "Residual risks".

**What lifts a durable hold.** Nothing in this unit, and nothing in place. A later reconstruction unit builds a **new journal in a new directory** from an authoritative reconstruction (new `journal_uuid`, generation + 1, genesis referencing the old head digest). It leaves the held directory byte-identical as evidence (spec L245-246; acct L247-248). The v1 anchor therefore needs no "lifted" state (critic 14).

### Crash matrix (in-scope windows; spec L249-253)

| # | Crash or fault window | Durable state after | Next open | Notification outcome | Spec |
|---|---|---|---|---|---|
| C1 | Before `BEGIN` (lookup, verification, plan, capacity) | unchanged | ready; `restart_recovery` | not recorded, not ACKed; a retry is validated anew | L251 |
| C2 | In `_commit_sql`, before the commit frame is durable | WAL frames without a valid commit frame, which SQLite ignores | ready; `wal_found` records the WAL bytes | not recorded, not ACKed; a retry is admitted | L251 |
| C3 | COMMIT durable, before the anchor `pwrite` | head = anchor + 1 commit | ready; re-anchored **before** `restart_recovery`; `anchor_lag: 1` | retained, never ACKed; a retry is suppressed | L252 |
| C4 | Anchor slot torn or reverted (crash before its sync) | older slot valid | as C3 | as C3 | L252 |
| C5 | Anchor synced, before the receipt or 202 | lag 0 | ready | retained; a retry is suppressed | L252 |
| C6 | After the ACK (no run intent exists in this unit) | full chain | ready; pending rebuilt; `restart_recovery` dispatch hold | pending retained and held; later decisions are `held` | L253, L260-263 |
| C7 | BEGIN, INSERT or COMMIT raises (I/O, `SQLITE_FULL`, authorizer) | committed or not (unknown) | process latch `journal_write_failed` now; the next open verifies | 503 class, not ACKed; retained (a retry is suppressed) or not (a retry is admitted) | L195-196, L211 |
| C8 | Anchor `pwrite` or sync raises after COMMIT | committed, not anchored | latch; next open as C3 | 503 class; retained | L211 |
| C9 | Crash during an autocheckpoint | safe in SQLite | ready | none | n/a |
| C10 | Crash in `create` before the anchor exists or is complete | DB (maybe WAL), no valid anchor | held `journal_anchor_missing`/`_invalid`; `create` gives `journal_exists` | nothing was ever ACKed; the operator removes the files | L242-246 |
| C11 | Crash during open's re-anchor | lag 1 (write lost or torn) or 0 | as C3, or ready | none | L252 |
| C12 | Crash during open's `restart_recovery` commit, directory sync or anchor | lag ≤ 1, because the re-anchor ran first | ready; one more `restart_recovery` | none | L260 |
| C13 | Crash during hold persistence, in either slot | pre-hold slot newest, or first hold slot newest | re-derived and re-persisted, or held | 503 class | L243-245 |
| S1 | Storage loses acknowledged commits: WAL truncated, deleted or mid-frame corrupt; stale restore; a dropped sync with the anchor surviving | a prefix, or an empty presentation | `journal_truncated`, persisted; DB and WAL left byte-identical | refused until a later reconstruction | L243-244 |
| S2 | Byte flip in a stored body; a forged, reordered or re-signed row; schema tamper | varies | `journal_record_invalid`, `_chain_broken`, `_replay_mismatch`, `_schema_invalid` or `_corrupt` | as S1 | L243 |
| S3 | Consistent rollback of all files, or a same-uid forger | an older self-consistent set | ready (undetectable) | admissions acknowledged after the rollback point are lost silently | non-claim |

The run-intent, spawn, effect-intent, receipt and terminal windows (spec L254-258) belong to later units.

## Record schema

### Envelope (every record; canonical ASCII JSON; exactly these 15 keys)

| Field | Type and bound | Rule |
|---|---|---|
| `schema_version` | int, exactly 1 | Any other value is `record_unsupported` (spec L98-100). |
| `journal_generation` | int 1..2^31-1 | Equals the generation set by the latest `journal_genesis`; only a future `reset_commit` changes it (spec L57, L292). |
| `event_id` | `[A-Za-z0-9._-]{1,128}` | Unique (UNIQUE index). Minted by `id_factory` (lowercase uuid4 by default). |
| `event_seq` | int 1..2^53-1 | Contiguous from 1. |
| `commit_seq` | int 1..2^53-1 | Contiguous from 1. Genesis is commit 1. |
| `commit_index`, `commit_size` | ints; 0 ≤ index < size ≤ 8 | Transaction framing (J1 graft 1, J1 S-E6). |
| `event_type` | registry enum | Unknown values are `record_unsupported`. |
| `actor` | `ACTORS`; every v1 type requires `receiver` | spec L150-151 |
| `boot_id` | ID from `id_factory`; new at every create or open | Equal across one commit. |
| `wall_time` | exactly `YYYY-MM-DDTHH:MM:SS.ffffffZ` (27 characters), years 2000-9999, calendar-valid | UTC RFC 3339 (spec L103). Informational; may go backwards. Equal across one commit. |
| `mono_us` | int 0..2^53-1 (`monotonic_ns // 1000`) | Non-decreasing within a `boot_id`; never compared across boots (spec L102-103, L132-133). Microseconds, because nanoseconds pass 2^53 after about 104 days. |
| `ids` | object; the per-type exact key set from `IDENTITY_KEYS`; values are IDs | spec L151 |
| `data` | per-type closed object; unknown keys are `record_field` | |
| `prev_record_digest` | 64 lowercase hex; `ZERO_DIGEST` at `event_seq` 1 | Hash predecessor (spec L153-154). |

Scalar discipline: `type(x) is int` (so `bool` is rejected), exact `str`, and exact booleans only where declared (`Baseline.complete`). **No floats exist anywhere**: Notification numbers are canonical strings. The body limit is `len(body) ≤ 16,384`.

### Canonical encoding, digests and transaction numbering

- **Encoding.** `body = canonical_json(thaw(envelope), ascii_only=True)`. Decoding must reproduce the same bytes.
- **Record digest.** `record_digest = sha256(b"rj.record.v1\x00" + body)`, which equals `tagged_digest("rj.record.v1", envelope)` for a canonical body. It covers `prev_record_digest` and the framing, but never itself. It is stored only in the row column (integ L83-84), and open recomputes it from the raw bytes.
- **Content digest.** `content_digest = tagged_digest("rj.content.v1", {schema_version, journal_generation, event_id, event_type, actor, ids, data})`. It excludes positions, framing, stamps and the chain. It is computed on demand for the duplicate lookup and never stored.
- **Chain.** Each `prev_record_digest`, including within a commit, equals the previous record's `record_digest`. That detects in-place edits, reorders, insertions and gaps. Suffix loss is left to the anchor.
- **Transaction numbering.** A commit of n records has:
  - consecutive `event_seq`s;
  - one `commit_seq`, the previous commit's + 1;
  - `commit_index` 0..n-1 and `commit_size` n;
  - one shared `boot_id`, `wall_time` and `mono_us`.
- **`group_commits`** yields only complete groups. A group interrupted by another `commit_seq`, or with a wrong index or size, is `replay_framing`. A stream that ends inside a group is `replay_tail_incomplete`. SQLite commits are atomic, so both indicate tampering or a bug.
- **Commit shapes** (closed, additive registry): `[journal_genesis]`, `[restart_recovery]`, `[capacity_hold]`, and `[admission, dedupe_decision]` sharing one `admission_id`. Any other shape is `replay_shape`.

### Record types in scope

"R" is the recovery class, which may use the reserved region; "O" is ordinary.

| Type | Class | `ids` | `data` (every key required) |
|---|---|---|---|
| `journal_genesis` (new) | R | `{}` | `format: "rj.journal.v1"`; `journal_uuid` (lowercase canonical UUID text); `bounds: {max_admissions, max_pending_fingerprints, ordinary_bytes, total_bytes}`: ints with 1 ≤ each ≤ its `V1_BOUND_CEILINGS` value and ordinary ≤ total (critic 10). Only at event 1, commit 1, generation 1. |
| `restart_recovery` | R | `{}` | `previous_boot_id` (equals the prior record's `boot_id`); `recovered: {commit_seq, event_seq, record_digest}` (equals the head before this commit); `anchor_lag` (0 or 1); `wal_found` (`null` or `{size, digest}`, observed facts that are only type-checked); `dispatch_hold: "restart_recovery"`; `prior_leases: "invalid"` (spec L33, L260). Its `boot_id` must be unseen. |
| `capacity_hold` | R | `{}` | `code` (a `CAPACITY_CODES` value not already active); `limit` (equals the recorded bound; ordinary bytes for `capacity_bytes`); `observed` (equals current usage: admission count, pending count or logical bytes); `requested` (int ≥ 1, with `observed + requested > limit`); `refused_source_digest` (hex64, the first refused arrival); `action: "set"`. |
| `admission` | O | `{admission_id}`, equal to its own `event_id` | `arrival_seq` (previous + 1, per generation); `decision` (`admitted` or `held`); `dispatch_holds` (sorted active dispatch hold codes before this commit, at most 8); `source` (the sanitized source record); `source_digest` (recomputed). |
| `dedupe_decision` | O | `{admission_id}` (the same) | `rule: "latest-admitted-v1"`; `result`; `source_group`; `dedupe_key`; `baseline_before` (`null` or `{admission_id, complete, dedupe_key}`); `baseline_after` (`{admission_id, complete, dedupe_key}`); `superseded` (a list of `{admission_id, fingerprint}` sorted by fingerprint, at most 32); `pending_count_after` (int). |

Every derived field is recomputed and compared at replay by `verify_commit`. Measured worst cases (probe p3): `admission` 4,966 bytes; `dedupe_decision` 8,983 bytes (32 superseded entries with 128-character IDs); `restart_recovery` 1,127 bytes. A realistic pair is about 2.2 KiB.

### Sanitized source record (`admission.data.source`; spec L156-159)

```json
{"alerts":[{"fingerprint":"5e8d72dc87b1ff35","starts_at":"2026-09-17T21:56:20Z","status":"firing",
            "values":{"A":"0.11440082443757411","B":"1"}}],
 "body_digest":"<hex64>","provenance":{"kind":"http","line":null,"path":"/notification"},
 "source_group":"<hex64>","truncated_alerts":0}
```

- **`source_group`** is `source_group_digest(groupKey) = tagged_digest("rj.source-group.v1", {"group_key": groupKey})`, where `groupKey` is printable ASCII of 1..1,024 bytes. The exact `groupKey` already carries `grafana_folder` in every capture (f31 L43), so no folder component is added (J1 L-E6, D-E7).
- **`alerts`** are 1..32 entries, sorted by fingerprint in ASCII order and unique. The validator refuses unsorted input (`source_order`) and never re-sorts it.
- **`fingerprint`** is 1..64 characters of `[A-Za-z0-9._-]`, which accepts Grafana hex and f31's synthetic `fixture-w1` (f31 L111). **`status`** is exactly `firing` or `resolved`.
- **`values`** is `null`, or an object of refId (`[A-Za-z0-9._-]{1,32}`) to a canonical number string or `null`, with at most 64 values across all alerts. `null` and `{}` are distinct, with different keys (probe p9).
- **Canonical number strings** (probe p1):
  - an integer lexeme n with |n| ≤ 2^53-1 gives `str(n)`;
  - a decimal lexeme becomes a float f, which must be finite; if f is integral and |f| ≤ 2^53-1 the result is `str(int(f))`, otherwise `repr(f)`;
  - so `100`, `100.0` and `1e2` give `"100"`; `10.0` gives `"10"`; `0.1` and `0.10000000000000001` give `"0.1"`; `-0.0` gives `"0"`; `1e16` gives `"1e+16"`; `1e-7` gives `"1e-07"`.
  - `is_canonical_number(s)` requires the grammar `-?(0|[1-9][0-9]*)(\.[0-9]+)?(e[+-][0-9]+)?`, at most 32 characters, and `canonical_number(lexeme(s)) == s`.
- **`starts_at`** matches `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?Z$` with at most 30 characters, or is `null`. It is provenance only.
- **`truncated_alerts`** is `null` (unknown) or 0..2^31-1 (J1 graft 6). A value other than 0 disables suppression (see "The pure reducer").
- **`body_digest`** is hex64: `sha256(b"rj.body.v1\x00" + raw body)`, computed by the ingress unit. It is provenance only, and it is the lookup key for the later Run-input spool (J2 graft 3).
- **`provenance`** is exactly `HTTP_PROVENANCE` in v1; `capture` arrives additively with the ingress unit.
- **Size.** `len(canonical_json(source_to_json(s), ascii_only=True)) ≤ 4,096` (spec L277). With 64-character fingerprints, 23 alerts fit (probe p3).
- **Never present:** raw body, labels, annotations, `message`, `title`, URLs, `valueString`, `receiver`, `externalURL`, `orgId` or any free text. The type has no field for them (spec L158-159; ADR12 L25).
- **`dedupe_key(s)`** (critic 13 ii) is `tagged_digest("rj.dedupe-key.v1", [[a["fingerprint"], a["status"], a["values"]] for a in source_to_json(s)["alerts"]])`.
  - `a["values"]` is the JSON **object** form (a `dict`) or `None`, never a tuple of pairs. The tuple encoding of key A would give `06b0db0f…` and must not be used.
  - The key excludes `source_group` (the comparison is within a group), `starts_at`, `truncated_alerts`, `body_digest` and provenance (f31 L63-65).
  - Pending entries hold `values` in the same object form for their digests.
- **`source_digest(s)`** is `tagged_digest("rj.source.v1", source_to_json(s))`, the spec's "canonical digest" (L157). The record carries no digest of itself.

**Full goldens** (probe p9):

| Name | 64-hex value |
|---|---|
| CG1 `source_group` (payment line 1 `groupKey`) | `5deaf914a2a751fefe64e9b9077fdadad2f5fe11c224ba5451d6d66bb6c7876e` |
| CG2 `source_group` (payment line 4) | `9d37267f6830d441f2c6ce82698704b397a29c16eb135973907fa2fa38045ce4` |
| Legacy fixtures' `source_group` | `aa57d128272b37ba89511a41b61e587aa198e2676d80f71925332c0d582bb7f8` |
| Key A: PF firing `{A:"1",B:"1"}` | `8fd41b0b50e9410d251c4802436605e54f65a8bbb6989f0fe170cbdc078d874a` |
| Key B: PF firing `{A:"2",B:"1"}` | `032a43329187bc6b93f1434f0b0b0d4ee53b5c32fe93b3cb10c6182bc3da4dd9` |
| Legacy firing: `87e2f184874a3b71` firing `{A:"0",B:"1"}` | `a99b74e0622bbf52ab6f66f38af0034e030e8b301bd0a399b97e7931f81f262d` |
| Legacy resolved | `107b7990e93f96f157da3e1ca394fd0697020a1d94647a7cf30d91b5fe8963f6` |
| PF firing, `values: null` | `db1901d7290e2697801453a6f829fb717479abfe954ad061e16400f0c731e810` |
| PF firing, `values: {}` | `6a3c39155abbaf9364c9f427f84ebeea57bebbb2aab2c615d78a6ee16551ecd3` |

### Extension rules for later units

- **R1.** A `(event_type, schema_version)` validator is frozen once committed. **Any change to the envelope or to a type's validator, including growing or shrinking a bound, bumps `schema_version` for every affected type.** Validators of old versions stay forever (critic 2). Genesis bounds are checked against the frozen `V1_BOUND_CEILINGS`, never against code defaults (critic 10).
- **R2.** An older binary meets only process holds, never persisted:
  - `user_version > 1`, which covers any DDL change such as a larger body `CHECK`;
  - a digest- and chain-verified record with an unknown or out-of-bound version, type, enum or `rule`;
  - a newer anchor slot.

  A rollback deployment can therefore refuse to run, but it can never brick the journal. The roll-forward binary finds the bytes and the anchor exactly as it left them (F7, F9).
- **R3.** Commit shapes are an additive registry.
- **R4.** New record families add their own projection fields. Admission transitions never read or write them.
- **R5.** Every decision input is in a record. Replay never consults the clock, the filesystem or configuration, apart from the bounds recorded in genesis.
- **R6.** `dedupe_decision.rule` versions the decision function (J2 graft 5). A change adds `latest-admitted-v2` rather than re-reading old journals as `replay_mismatch`.
- **R7.** Every list-valued record field stays at or below 256 items, the `canonical_json` cap. A later `run_intent` records `{through_arrival_seq, consumed_set_digest, consumed_count}` plus a bounded summary, **never** a list of admission IDs (J2 graft 6). The IDs stay derivable by replay (spec L173).

## The pure reducer

**Decision function** (shared by `plan_admission` and `verify_commit`):

```python
def _decide(p, source, admission_id):
    key, group = dedupe_key(source), source.source_group
    complete = source.truncated_alerts == 0                        # None (unknown) or >0 is incomplete
    before = p.baselines.get(group)
    if complete and before is not None and before.complete and before.dedupe_key == key:
        # suppressed: the group's baseline is unchanged; pending entries of its members that another
        # group has since claimed return to this, the latest, arrival (P25); nothing is created
        reclaimed = tuple(sorted((a.fingerprint, p.pending[a.fingerprint].admission_id)
                                 for a in source.alerts
                                 if a.fingerprint in p.pending
                                 and p.pending[a.fingerprint].source_group != group))
        return Decision("suppressed", before, before, superseded=reclaimed, new_pending=0)
    superseded = tuple(sorted((a.fingerprint, p.pending[a.fingerprint].admission_id)
                              for a in source.alerts if a.fingerprint in p.pending))
    return Decision("pending_reduced" if superseded else "admitted", before,
                    Baseline(admission_id, key, complete), superseded,
                    new_pending=len(source.alerts) - len(superseded))
```

**Truncation (critic 6 i).** An arrival whose `truncated_alerts` is not 0, including `null`, is never `suppressed`: its key covers only the members Grafana sent, so exact duplication is unprovable. It still advances the baseline, with `complete: false`, so no later arrival is suppressed against it. All captures and fixtures carry 0.

**Capacity** (in `plan_admission`, before anything is written; spec L277-279), checked in this order:
1. `admission_count + 1 > max_admissions` gives `capacity_admissions`, with `requested` 1. Suppressed arrivals count.
2. When the result is not suppressed, `len(pending) + new_pending > max_pending_fingerprints` gives `capacity_pending`, with `requested = new_pending`. A suppressed arrival's reclaim replaces entries, so it adds none.
3. Seal both records. Then `logical_bytes + Σ(len(body) + 384) > ordinary_bytes` gives `capacity_bytes`, with `requested` equal to that charge.

Recovery-class plans are checked against `total_bytes`. A `plan_restart` or `plan_capacity_hold` that does not fit returns a `CapacityRefusal`, which the shell latches as `journal_capacity_recovery`. `plan_capacity_hold` returns `None` when the code is already an active dispatch hold.

**`verify_commit(p, records) -> Delta`** checks, without mutating:
- **Framing:** the count, `event_seq`, `commit_seq`, index, size, the chain (within the commit too), the generation, and stamps equal across the commit.
- **Boot rules:**
  - genesis requires an empty projection;
  - `restart_recovery` requires an unseen `boot_id` and `previous_boot_id == p.boot_id`;
  - any other record requires `boot_id == p.boot_id` and `mono_us ≥ p.last_mono_us`.
- **Shape.**
- **Per-shape re-derivation:**
  - admission: `admission_id == event_id`; `source_from_json`; `source_digest`; `_decide` with capacity, which must not refuse; and equality of `arrival_seq`, `dispatch_holds`, `decision`, `rule`, `result`, both baselines (including `complete`), `superseded`, `dedupe_key` and `pending_count_after`;
  - `capacity_hold`: the limit and observation rules, and not already active;
  - `restart_recovery`: the recovered head, the previous boot and the region fit;
  - genesis: bounds within `V1_BOUND_CEILINGS`.

Any difference raises `ReplayError`.

**The `Delta`** carries:
- the new head, and the boot, clock and byte counters;
- for a non-suppressed admission, `baselines[group] = baseline_after`, and `pending[fp] = PendingEntry(fp, admission_id, arrival_seq, group, status, values)` for every alert;
- for a suppressed admission, the same `PendingEntry` replacement for each reclaimed Fingerprint only;
- dispatch-hold additions: `restart_recovery` sets `restart_recovery`, and `capacity_hold` sets its code.

A suppressed admission with nothing to reclaim changes only the counters, the head and the bytes. No admission transition touches holds except through its own records, or any later family's fields (spec L223, L237-239).

**Live path and replay are the same code.** The shell runs `verify_commit` on its own planned records **before** the store is written; a failure there is the latched `journal_divergence` with nothing written (J1 graft 7). The shell then appends and calls `apply_delta`. Replay is `for group in group_commits(rows): apply_delta(p, verify_commit(p, group))`.

**Digests over sets larger than 256 items (critic 13 iii).**
- `_list_digest(tag, items) = sha256(tag || 0x00 || u32be(n) || b"".join(sha256(c) for c in sorted(canonical_json(item, ascii_only=True) for item in items)))`. The items are hashed one by one, the leaf hashes are concatenated, and they are sorted by the items' canonical bytes.
- `pending_digest` uses `"rj.pending-set.v1"` over `[fingerprint, admission_id, arrival_seq, source_group, status, values]` entries, with `values` in object form.
- `state_digest = tagged_digest("rj.state.v1", {...})` covers `journal_uuid`, the generation, the head, the counters, the logical bytes, the sorted `[code, since_commit_seq]` dispatch holds, `pending_digest`, and `_list_digest("rj.baseline-set.v1", [[group, admission_id, complete, dedupe_key], ...])`.

These work for 1,024 pending entries and 10,000 baselines, above the 256-item array cap.

## Admission and dedupe

### `admit(source)` (under the journal lock)

1. A closed journal raises `journal_closed`; a held one raises `journal_held`.
2. `validate_source(source)`. A `SourceError` raises `JournalError("source_invalid")`; nothing is latched or written.
3. **Stamp.** `wall_clock()` and `mono_clock()` must each be an exact int ≥ 0, the formatted wall time must fall in years 2000-9999, and `mono_us` must not be below the last value of this boot. Any failure latches `journal_clock_invalid` and the call raises it.
4. Mint `admission_id` and `dedupe_event_id` from `id_factory`. Both must pass `validate_id` and differ, or the journal latches `journal_divergence`.
5. `plan = plan_admission(...)`. On a `CapacityRefusal r`:
   - increment `refusals_this_boot[r.code]`, and keep its last `source_digest` (memory only);
   - build `plan_capacity_hold(..., refused_source_digest=source_digest(source))`;
   - on `None`, write nothing;
   - on a `CapacityRefusal`, latch `journal_capacity_recovery` and raise it;
   - on a `Plan`, `_commit` it;
   - then raise `JournalError(r.code)`. Nothing is evicted (spec L278-279, L284-286).
6. **`_commit(plan)`:**
   1. `store.find_duplicate(plan.records)`:
      - a `Duplicate` returns its stored `event_seq`s. No verification, write or `apply_delta` runs, and the head is unchanged (critic 9). This is unreachable through `admit`, because its IDs are fresh.
      - `store_event_conflict` latches the **process** hold `journal_divergence` and raises it. Nothing is written or persisted (critic 3).
   2. `delta = verify_commit(p, plan.records)`. A `ReplayError` latches `journal_divergence`.
   3. `store.append(plan.records, sync_directory=<restart commit>)`. Any failure, or a `BaseException`, latches `journal_write_failed`. The `BaseException` re-raises unchanged; an ordinary failure raises `journal_write_failed`.
   4. `apply_delta(p, delta)`.
7. Return the `AdmissionReceipt`. Only this object permits an ACK.

### The failed A / new B / A example (spec L224-235; f31 L89, F03), worked

**Setup.**
- CG1 is the exact `groupKey` of payment line 1, `{}:{alertname="Service error rate is elevated", grafana_folder="demo"}`, with `source_group` `5deaf914…`.
- PF is `5e8d72dc87b1ff35`.
- **A** is PF firing `{A:"1",B:"1"}`, with key `8fd41b0b…`; **B** is the same with `A:"2"`, key `032a4332…` (full values above).
- `design-sqlite`'s CG1 prefix `9d37267f…` is actually CG2's, payment line 4.

**As observable in unit 15** (nothing consumes pending; probe p4):

| Step | Arrival | CG1 baseline before | Result | Superseded | Baseline after | Pending PF after |
|---|---|---|---|---|---|---|
| 1 | A (adm1) | none | admitted | none | adm1 / 8fd4… | adm1 |
| 2 | B (adm2) | adm1 / 8fd4… | pending_reduced | PF ← adm1 | adm2 / 032a… | adm2 |
| 3 | A (adm3) | adm2 / 032a… | pending_reduced | PF ← adm2 | adm3 / 8fd4… | adm3 |
| 4 | A (adm4) | adm3 / 8fd4… | **suppressed** | none | unchanged | adm3 (unchanged) |
| 5 | restart, then A (adm5) | adm3 / 8fd4… | suppressed; decision **held** (`restart_recovery`) | none | unchanged | adm3 |

**With a later-unit consumption after step 1.** This unit asserts it only against the pure reducer, on a constructed projection with baseline adm1 and empty pending. Step 2 B is `admitted`; step 3 A is `pending_reduced` (PF ← adm2); step 4 A is `suppressed` (probe p4). The later units then act as spec L226-235 describes:
- A's job and effect keep their IDs and state;
- recovery reconciles A's prior effect first;
- fresh work comes from the outstanding obligation plus pending PF = adm3, under current Match eligibility;
- a confirmed effect is not reissued, and an unknown one stays held;
- one operator retry gets fresh IDs.

**What this shows:**
- Step 3 is admitted because the comparison is with the latest *admitted* tuple (B), not the last completed one (spec L216-218; f31 L97).
- adm2 is superseded but never lost: its admission record stays, and the superseding decision names it (spec L221-223).
- Steps 4 and 5 are visible dedupe events that change no pending or obligation state (spec L237-239).

### Cross-group reclaim (critic 7; P25)

Critic q7, re-run by the synthesizer:

| Step | Arrival | Result | Pending PF after (option (a), adopted) | Pending PF after (option (b)) |
|---|---|---|---|---|
| 1 | CG1 PF resolved (adm1) | admitted | adm1 / CG1 resolved | adm1 / CG1 resolved |
| 2 | CG2 PF firing (adm2) | pending_reduced (PF ← adm1) | adm2 / CG2 firing | adm2 / CG2 firing |
| 3 | CG1 PF resolved (adm3) | suppressed against CG1's adm1 baseline; `superseded` names PF ← adm2 | **adm3 / CG1 resolved** | adm2 / CG2 firing (a Resolved lost to the released aggregate) |

Spec L221-222 and f31 L65-66 say pending retains "the latest arrival" per Fingerprint, and a suppressed delivery is still an arrival (spec L58). Option (a) therefore keeps pending equal to the latest arrival without moving the group's baseline, and without ever creating an entry. That last condition matters: a suppressed repeat after consumption must not create new work (F01).

### Fixture coverage at the admission seam

- **F01:** A twice gives admitted, then suppressed.
- **F02:** payment lines 1 and 2 (sc31 L9-10) give admitted, then pending_reduced.
- **F03:** the worked example above.
- **F04:** lines 16, 18 and 20 (sc31 L11-13) leave PC and PX pending at line 20's firing.
- **F05:** firing then an explicit resolved leaves PF pending resolved.
- **F06:** PF/PC/PX, then PF only, leaves PC and PX untouched; omission is never Resolved (spec L38).
- **F07:** lines 20 (CG1) and 21 (CG2) keep separate baselines, and pending carries seven Fingerprints with their groups.
- **Cross-group:** an equal tuple in another group is admitted (spec L218-219). The q7 reclaim sequence runs as in the table above.
- **Truncated:** an identical repeat with `truncated_alerts` 2 or `null` is not suppressed, and an identical complete repeat after it is not suppressed either.
- **Legacy pair:** firing and firing-repeat give admitted, then suppressed; resolved gives pending_reduced.

## Holds and closed code sets

**Recovery holds.** Durable. They refuse every append and set `state == "held"` with scope `recovery`. Each is persisted in the anchor, or re-derived from unchanged anchor bytes when the anchor is the failure.

| Code | Trigger |
|---|---|
| `journal_truncated` | DB absent while the anchor or WAL exists; empty presentation with a valid anchor; empty table; head below the anchor |
| `journal_anchor_missing` | DB present, anchor absent |
| `journal_anchor_invalid` | Anchor of the wrong size, with no intact slot, or breaking a v1 slot rule |
| `journal_anchor_conflict` | The record at the anchored `event_seq` is absent, not the last of its commit, or differs in digest or generation |
| `journal_identity_mismatch` | `application_id` differs; the anchor's `journal_uuid` differs from genesis |
| `journal_schema_invalid` | `user_version` ≤ 1 but not 1; the DDL differs; `journal_mode` is not `wal` |
| `journal_corrupt` | `integrity_check` not `ok`; primary code `SQLITE_CORRUPT`/`SQLITE_NOTADB` |
| `journal_record_invalid` | Raw-byte digest mismatch; a present, well-typed column/body mismatch |
| `journal_chain_broken` | Sequence, predecessor, framing or generation failure |
| `journal_tail_unverified` | Incomplete final commit group; head more than one commit beyond the anchor |
| `journal_replay_mismatch` | A re-derived field differs; an unknown commit shape; a boot or clock rule broken (all under a known version and rule) |
| `journal_event_conflict` | Two stored rows share an `event_id` (open only; stored evidence; unreachable while the UNIQUE index holds) |

**Process holds.** Never persisted. They refuse every append and set `state == "held"` with scope `process`; close and reopen clears them.

| Code | Trigger |
|---|---|
| `journal_open_failed` | `OSError`, or a SQLite error whose primary code is not 11 or 26, while opening or reading |
| `journal_schema_unsupported` | `user_version > 1`; a newer anchor slot; any parse, canonical or typed failure on a digest- and chain-verified row |
| `journal_write_failed` | Any failure or non-clean exit inside `append`, including an anchor or directory sync failure and `SQLITE_FULL` |
| `journal_clock_invalid` | A clock raised, returned a non-int or negative value, gave a year outside 2000-9999, or regressed within the boot |
| `journal_divergence` | A journal-built ID or record failed its own validation before commit; an append-time `event_id` overlap (critic 3; J1 graft 7) |
| `journal_capacity_recovery` | `restart_recovery` or `capacity_hold` does not fit the total budget |

**Dispatch holds.** Admission continues. They are derived at replay from records, and none is cleared in this unit.

| Code | Set by |
|---|---|
| `restart_recovery` | every `restart_recovery` record (spec L32-33, L260-263) |
| `capacity_admissions`, `capacity_pending`, `capacity_bytes` | the first `capacity_hold` per code (spec L284-286) |

**`JournalError` codes.**
- **Raised by open or create when nothing can be inspected:** `journal_argument`, `journal_path_invalid`, `journal_permissions`, `journal_locked`, `journal_missing`, `journal_exists`, `journal_sync_unsupported`, `sqlite_unsupported` (including the missing no-checkpoint capability on Python 3.11), `journal_create_failed`.
- **Raised by `admit`:** `journal_closed`, `journal_held`, `source_invalid`, `capacity_admissions`, `capacity_pending`, `capacity_bytes`. On the call that latches, also `journal_write_failed`, `journal_clock_invalid`, `journal_divergence` or `journal_capacity_recovery`.

Every code is retryable backpressure (503 class) for the later integration, except `source_invalid`, which is a caller bug. The ingress unit owns the 400/413 mapping.

**Snapshot** (fixed shape and nonsecret; projection fields are `null` when held):

```
{state, hold: null|{code, scope, persisted, sqlite_error}, journal_uuid, generation, boot_id,
 head: {commit_seq, event_seq, record_digest}, anchor: {counter, commit_seq, event_seq, lag_at_open},
 wal_found: null|{size, digest}, dispatch_holds: [{code, since_commit_seq}],
 counts: {records, admissions, pending_fingerprints, source_groups},
 bytes: {logical, ordinary_limit, total_limit}, bounds: {...},
 refusals_this_boot: {code: {count, last_source_digest}},
 verified_state_digest, pending_digest, state_digest}
```

`verified_state_digest` is the state digest of the verified projection before this open's `restart_recovery` (critic 12). Pending entries are read through `pending()`.

## Proposed bounds

| Bound | Value | Enforced where | Basis |
|---|---|---|---|
| Alerts per source record | 32 | `validate_source` | Proposal; captured maximum 4 |
| Numeric values per source record (total) | 64 | `validate_source` | spec L277-278 |
| Canonical source record | 4,096 B | `validate_source` | spec L277; captured maximum 849 B |
| Fingerprint / refId / `groupKey` | 1..64 / 1..32 / 1..1,024 B | validators | Proposal; captured `groupKey` maximum 83 B |
| Canonical number string / `starts_at` | ≤ 32 / ≤ 30 characters | `validate_source` | forwarder_json L30 / proposal |
| `truncated_alerts` | `null` or 0..2^31-1 | `validate_source` | Proposal |
| ID | 1..128 of `[A-Za-z0-9._-]` | records | spec L102 |
| Record body | 16,384 B (measured worst 8,983) | records and DB `CHECK` | Proposal |
| Records per commit | 1..8 | records | Proposal |
| Generation / sequences / `mono_us` | 2^31-1 / 2^53-1 / 2^53-1 | records | Proposal |
| Admissions per generation (suppressed included) | 10,000 (v1 ceiling) | reducer, before writing | spec L275 |
| Pending Fingerprints | 1,024 (v1 ceiling) | reducer, before writing | spec L275-276 |
| Logical bytes: ordinary / total | 112 MiB / 128 MiB (16 MiB reserve) | reducer, before writing | spec L273-274 |
| Charge per record | `len(body) + 384` | reducer | probe p3: 381 B per record on 10,000 realistic pairs |
| Physical main DB | `max_page_count` 40,960 (160 MiB) | SQLite | Backstop at 1.25 × total |
| WAL | 8 MiB after a checkpoint; autocheckpoint at 1,000 pages; kept across closes | SQLite | |
| Anchor | 8,192 B file; slot body ≤ 960 B | store | probe p3 worst 503 B |
| `capacity_hold` | ≤ 1 per code per generation | reducer | Proposal |

**Budgeting.**
- The adversarial pair (4,966 + 8,983 + 768 bytes) binds on bytes at about 7,900 admissions.
- A realistic pair (about 2.2 KiB + 768 bytes) reaches 10,000 admissions at about 29 MiB, so the count binds first.
- A `restart_recovery` costs about 1.5 KiB, so the reserve holds about 11,000 restarts.
- `JournalBounds` may only be lowered below the `V1_BOUND_CEILINGS`, and only at create time (for tests). It is recorded in genesis, and open always uses the recorded values.
- Retention and compaction are not implemented, and nothing is ever deleted. "Never evict" (spec L279) therefore holds structurally: no UPDATE or DELETE DML exists (AST-checked).

## Invariants

Each invariant has a test.

- **I1. ACK only after durability.** No receipt exists unless both records committed in one `BEGIN IMMEDIATE` transaction under WAL, `FULL` and `fullfsync`, **and** the anchor naming that commit was synced with no fallback (spec L152-153, L193-196; ADR12 L27; integ L10).
- **I2. Failure is backpressure, never admission.** Every failure before the receipt raises a fixed code and leaves the projection unchanged. An ambiguous storage failure latches a visible hold (spec L195-196, L211-212).
- **I3. Append-only, and evidence-preserving.** No UPDATE or DELETE DML exists, and triggers abort both. Open compares the DDL exactly. **No open or close checkpoints or deletes the WAL**, because no-checkpoint-on-close is set before the first statement and never cleared (spec L151-152, L243-246; critic 1).
- **I4. Contiguous chain, complete transactions.** `event_seq` and `commit_seq` are contiguous from 1, every record chains to its predecessor, and every commit group is complete (spec L100, L153-154).
- **I5. Duplicate `event_id`** (spec L100-102):
  - an exact duplicate of one stored commit writes nothing and returns the stored positions, without verification or `apply_delta`;
  - any other append-time overlap writes nothing and latches the process hold `journal_divergence`, so last write never wins;
  - two stored rows sharing an ID are a durable hold at open.
- **I6. Strict canonical typed bodies.** Canonical ASCII JSON, exact key sets and types, bounded sizes and a closed registry (spec L98-104).
- **I7. Verify before applying, physical before typed.** Open installs no projection and permits no write until everything passes: capability, ownership, settings, presentation, format, `integrity_check`, and, for every row in order, digest, chain, columns, typed decode, framing and semantic replay, then anchor agreement (spec L242; critic 2).
- **I8. At most one commit beyond the anchor.** A lag of 1 is adopted and re-anchored before any append; more than 1, or an incomplete group, is durable (spec L243, L251-252; probe p5).
- **I9. Missing acknowledged records hold.** Head below the anchor, an empty presentation, a digest conflict at the anchor, or a missing DB or anchor never lets the journal continue on a prefix (spec L243-244).
- **I10. Only evidenced physical failures persist.** Recovery holds are persisted in both anchor slots, or re-derived from unchanged anchor bytes. Process holds, including every typed failure on a verified row, are never persisted (spec L243-246, L211; critic 2 and 3).
- **I11. Restart holds dispatch.** Every open of an existing journal appends `restart_recovery`, bound to the prior head and boot, before any admission. Later admissions record `decision: "held"` (spec L32-33, L260-263).
- **I12. Dedupe baseline.** An arrival is suppressed iff it is complete (`truncated_alerts == 0`), its group's baseline is complete, and its key equals that baseline's. Cross-group equality never suppresses (spec L35-38, L215-219; f31 L63-64; critic 6).
- **I13. Pending is the latest arrival per Fingerprint.**
  - There is one entry per Fingerprint: the latest arrival from any group, with its group.
  - A non-suppressed arrival sets all its members.
  - A suppressed arrival reclaims only entries another group holds and never creates one.
  - Omitted members are unchanged.
  - Every replaced ID is named in the replacing decision (spec L36-38, L221-223; f31 L65-68; P25).
- **I14. Admission transitions stay in their lane.** A suppressed arrival changes counters, head, bytes and at most its reclaimed pending entries. No admission transition moves another group's baseline, touches holds except through its own record types, or touches later families (spec L223, L237-239).
- **I15. Capacity refuses before crossing and evicts nothing.** At most one `capacity_hold` per code, naming the first refused source digest (spec L277-279, L284-286).
- **I16. Region split.** Ordinary records stay within the ordinary budget; recovery records may use the reserve up to the total (spec L273-274).
- **I17. No forbidden content.** Every string leaf in a stored body is a digest, a restricted-charset ID, fingerprint or refId, an enum, a canonical number, a fixed-format time, or the fixed provenance path (spec L156-159; ADR12 L25).
- **I18. Single writer.** `flock` and SQLite EXCLUSIVE locking for the journal's lifetime (spec L142; acct L58-61).
- **I19. Monotonic time per boot.** `mono_us` never decreases within a boot and is never compared across boots. A boot changes only at `restart_recovery`, and a retired boot never reappears (spec L102-103, L132-133).
- **I20. One decision function.** Every recorded derived field equals `verify_commit`'s recomputation, live and at replay (spec L128-129, L245).
- **I21. Explicit genesis only.** `open` never creates a DB, WAL or anchor (spec L262-263; acct L247-248).
- **I22. Anchor and directory syncs never fall back.** A failed `F_FULLFSYNC` or `fsync` on the anchor or the directory means no receipt (spec L152-153; critic 11).
- **I23. File ownership.** The directory is 0700, files are 0600, all are owned by euid, and there are no symlinks or hard links. This is necessary but not sufficient for "inaccessible to Runs" (spec L31-32).
- **I24. Purity.** `journal_records` and `journal_reducer` import no clock, randomness, OS, filesystem, `sqlite3` or `threading` (AST-checked).
- **I25. Rollback safety.** An older binary can only produce process holds when it meets newer bytes, and never writes to them (R1, R2; critic 2).

## Existing-module changes

**None.** `receiver.py`, `notification.py`, `run_spawner.py`, `replay.py`, `reset.py`, every `forwarder_*` module, `pyproject.toml` and every existing document are untouched. `forwarder_json` is imported as-is, and every existing test file stays byte-identical.

The unit adds four modules, six test files, one test data file and `docs/recovery-journal.md`.

**Consequences to state plainly in the outcome:**
- The running Receiver still acknowledges before any durable record. This unit does not make the demo durable.
- The journal needs Python ≥ 3.12 capability (P26). On 3.11 it refuses to construct with `sqlite_unsupported`, while the rest of the package keeps its 3.11 floor.

## Ownership and validation

**Real-sync budget (critic 8).** This counts every full sync, SQLite's COMMIT syncs included:
- per operation: create 4 (COMMIT, directory, anchor, directory); ready open 3, or 4 with lag 1 (restart COMMIT, directory, anchor); a held open that persists a verdict 2; an admission 2; a capacity refusal that writes its hold 2; close 0, since it never checkpoints;
- about 19 ms each on macOS (critic q3: admission 38.8 ms, create 71 ms);
- caps: C ≤ 250, D ≤ 450, E ≤ 500 and F ≤ 300, so at most about 1,500 syncs, about 30 s plus scan time.

Open-only tests copy module-scoped base images, built once per module (create plus a few admissions, then close), with `shutil.copytree`, instead of rebuilding. Timings are recorded in `validation.json` and **never asserted**. Combinatorial load runs on the pure layer. No source has a durability-weakening switch.

**Python version gate.** Every journal test file carries `pytestmark = pytest.mark.skipif(not journal_store.no_ckpt_supported(), reason=...)`, except the capability test C14. On 3.12 and later, which includes the local 3.13 and the container, nothing is skipped.

**Implementer A** owns `journal_records.py` and `tests/test_journal_records.py` (pure).
- A1: known-answer canonical bytes, `record_digest` and `content_digest` for one record of each of the five types. Each is cross-checked with an independent `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True)` encoding and `sha256(tag + b"\0" + body)`.
- A2: `open_record(seal(...).body)` equals the record. Each of these gives `record_not_canonical` (with the digest recomputed so it passes): whitespace, reordered keys, an ASCII letter written as a JSON unicode escape (backslash, `u0041`), a trailing newline. An unsigned byte flip gives `record_digest` **before** any parse is attempted (critic 2).
- A3: envelope bounds:
  - ID lengths 128 and 129, and the charset;
  - sequences 0 and 2^53; `commit_index ≥ commit_size`; `commit_size` 0 and 9; generation 0 and 2^31;
  - `mono_us` −1;
  - `wall_time` with an offset, a lowercase `t`, no fraction, February 30, 1999 and 10000;
  - `schema_version` 2, an unknown `event_type` and an unknown `rule` give `record_unsupported`;
  - an unknown key gives `record_field`; `True` for an int gives `record_type`; a 16,385-byte body gives `record_too_large`.
- A4: `content_digest` ignores positions, framing, stamps and the predecessor, and changes with any `ids` or `data` bit. `record_digest` equals the raw-byte `sha256`. `thaw` makes `canonical_json` accept `Record.ids`/`data`, and passing the frozen view directly gives `json_type` (critic 13 i).
- A5: per-type validators: required keys and enums; `superseded` sorted, unique and at most 32; `dispatch_holds` sorted and unique; baselines including exact-bool `complete`; `requested ≥ 1`; the `wal_found` shape; genesis bounds against `V1_BOUND_CEILINGS` (10,000 accepted, 10,001 rejected), and unaffected by a monkeypatched lower `DEFAULT_BOUNDS` (critic 10).
- A6: `canonical_number` table from probe p1 (`100`, `100.0`, `1e2`, `10.0`, `0.1`, `0.10000000000000001`, `-0.0`, `-0`, `1e16`, `1e-7`, `9007199254740992.0`, `5e-324`). `bool`, `str` and `float` inputs give `source_number`.
- A7: `is_canonical_number` accepts the outputs above and rejects `"1.0"`, `"-0"`, `"1e16"`, `"1E+16"`, `"+1"`, `"01"`, `"9007199254740992"`, `"nan"`, `"inf"` and a 33-character string.
- A8: `SourceRecord` validation:
  - the sc31 L9-20 projections, built as records, validate;
  - unsorted alerts give `source_order`;
  - rejections: a duplicate fingerprint, `"Firing"`, 33 alerts, 65 values, 4,097 canonical bytes (4,096 accepted), fingerprints of 65 characters (64 accepted) or outside the charset, refIds of 33 (32 accepted);
  - `starts_at` valid and invalid; `truncated_alerts` `None`, 0 and 2^31-1 accepted, and −1, 2^31 and `True` rejected;
  - a non-hex `body_digest`; non-http provenance;
  - `values` `None` versus `{}`;
  - a mutated frozen instance fails `validate_source`.
- A9: the nine full-length goldens in "Full goldens", exact. Keys are computed from `source_to_json`'s object-form `values`; the tuple encoding must differ (`06b0db0f…`). The key excludes `starts_at`, `truncated_alerts`, `body_digest` and provenance (critic 13 ii).
- A10: `source_group_digest` rejects an empty, a 1,025-byte and a non-printable `groupKey`.
- A11: every `RecordError`/`SourceError` has `args == (code,)`, `__cause__` and `__context__` equal to `None`, and a code in its closed set.
- A12 (AST): the exact import allowlist; `except` bodies are only `Assign`/`AnnAssign`/`Pass`; no `datetime.now`, `utcnow` or `today`.

**Implementer B** owns `journal_reducer.py` and `tests/test_journal_reducer.py` (pure; the heavy suite). B starts against A's signatures.
- B1: scenario tables F01, F02, F04, F05, F06, F07, cross-group, and **the q7 reclaim sequence** (critic 7), built from sc31 projections. Per step: result, baselines, superseded and pending.
- B2: the worked A/B/A/A, plus restart then A (suppressed, `held`). Variant 2 runs on a constructed projection (baseline adm1, empty pending).
- B3: suppressed neutrality. Without cross-group entries, the projection before equals the one after, except counters, head and bytes. With them, exactly the reclaimed entries change, and no entry is created: a suppressed repeat after a test-only pending clear leaves pending empty.
- B4: capacity with small bounds:
  - admissions exactly at the limit; suppressed arrivals count;
  - pending refuses only new Fingerprints, and a reclaim never trips it;
  - an admission is refused on bytes while `capacity_hold` and `restart_recovery` still fit;
  - at most one hold per code;
  - replay uses the bounds recorded in genesis.
- B5: **property test against a reference model, bounded (critic 8).**
  - 100 seeds × 50 operations over 3 groups, 4 Fingerprints, both statuses, values from {0, 1, 1.0, 2, null} and `values: null`, and `truncated_alerts` from {0, 0, 0, 2, null}, with restarts and capacity refusals mixed in.
  - At **every** step, the live plan with `verify_commit`/`apply_delta` must equal an independent 30-line scan-the-history reference model that implements I12 and I13.
  - At every 10th step and at the end, `replay(all records)` must also agree.
  - Comparison is by fields, `pending_digest` and `state_digest`. Estimated about 8 s (critic q5 scaling); recorded, not asserted.
- B6: prefix property on 5 seeds × 20 commits: every commit-boundary cut replays to the live state at that commit, and a cut inside a group gives `replay_tail_incomplete`.
- B7: chain and framing edits give specific codes: delete, swap, duplicate, generation change, boot reuse, `mono_us` regression within a boot, and a boot change outside `restart_recovery`.
- B8: commit shapes: an admission alone, a mismatched `admission_id`, reversed order, a three-record group, and an unknown shape each give `replay_shape`.
- B9: **re-signed semantic divergence.** Changing any of these, with the digests and chain recomputed so they stay valid, still gives `replay_mismatch`: `result`, `superseded`, either baseline including `complete`, `arrival_seq`, `dispatch_holds`, `decision`, `dedupe_key`, `source_digest`, `pending_count_after`, the capacity observation or limit, or the restart recovered head.
- B10: `pending_digest` and `state_digest` are equal for equal histories, differ on any single field, are independent of dict insertion order, and work at 1,024 pending entries.
- B11 (AST): the purity allowlist.
- B12: truncation. An identical repeat with `truncated_alerts` 2, and one with `null`, is admitted or pending_reduced, never suppressed. The baseline gets `complete: false`. A later identical complete repeat is not suppressed against it, but a second complete repeat is (critic 6 i).

**Implementer C** owns `journal_store.py` and `tests/test_journal_store.py` (real SQLite, real sync; at most 250 syncs).
- C1: create layout: modes 0700 and 0600; the four files; no `-shm`; an 8,192-byte anchor. Every setting is read back, including `getconfig(NO_CKPT_ON_CLOSE) is True`, along with `application_id`/`user_version` and the exact schema rows (no `content_digest` column).
- C2: create refusals: a missing directory gives `journal_path_invalid`; mode 0750 gives `journal_permissions`; a symlinked directory is refused; an existing DB, WAL or anchor gives `journal_exists`.
- C3: open ownership: a symlinked DB, anchor or lock; a hard-linked DB; a 0644 file. An empty directory gives `journal_missing` and stays empty.
- C4: locking: a second open in-process and one from a subprocess give `journal_locked`. A raw `sqlite3.connect` while the journal is open gets "database is locked".
- C5: a raw UPDATE or DELETE is aborted by the triggers. An AST test finds no UPDATE or DELETE DML outside the DDL.
- C6: anchor codec:
  - slots alternate by counter parity;
  - a torn newest slot falls back to the older;
  - `journal_anchor_invalid`, with the file byte-identical after open: both slots torn; wrong size; a counter gap other than 1; a parity mismatch; a newer non-hold slot after a hold slot;
  - a foreign `journal_uuid` gives `journal_identity_mismatch`.
- C7: **sync primitive.** On darwin, `fcntl.fcntl` is monkeypatched to record and delegate:
  - each append issues exactly one `F_FULLFSYNC` on the anchor fd and never an `os.fsync` on it;
  - the order is COMMIT → `pwrite` → `F_FULLFSYNC` (instrumented `_commit_sql` and `os.pwrite`);
  - with `sync_directory=True` the order is COMMIT → directory `F_FULLFSYNC` → `pwrite` → anchor `F_FULLFSYNC` (critic 11).

  A Linux variant, skipped on darwin, asserts `os.fsync`. An unsupported `sys.platform` gives `journal_sync_unsupported`.
- C8: **fsync-failure injection.** `fcntl.fcntl` raising `OSError(ENOTSUP)`, and separately `OSError(ENODEV)`, for `F_FULLFSYNC` on the anchor fd gives `store_write_failed`, and every later append is refused. The same holds for the directory fd. A reopen still sees the committed row.
- C9: `find_duplicate`: an exact duplicate commit gives `Duplicate(stored seqs)` with no write and an unchanged anchor counter. A differing content digest, a partial overlap or a reordering gives `store_event_conflict`, with no rows written.
- C10: `classify_sqlite_error` works on the primary code (critic 4): 11, 26, 779, 523 and 267 are recovery; 10, 522, 3850, 14, 5, 13, 2067 and a missing attribute are process. `sqlite_error` carries the name.
- C11: format tamper on closed images: a dropped trigger, an added index or table, or `journal_mode` rewritten to DELETE gives `journal_schema_invalid`; `user_version` 2 gives process `journal_schema_unsupported`; a changed `application_id` gives `journal_identity_mismatch`; an empty presentation with a valid anchor gives `journal_truncated`.
- C12: `wal_found` size and digest are recorded before connecting; an absent WAL gives `None`.
- C13: `persist_hold` writes counters n+1 and n+2, each synced. A torn second write still reads as held. The writer refuses any later slot without a hold.
- C14: capability gate (runs on every Python). With `journal_store.no_ckpt_supported` monkeypatched to `False`, `create` and `open` raise `sqlite_unsupported` before any file is created or opened: the directory listing is unchanged. On a real 3.11 interpreter the same path is taken without the patch; that was not run here (P26).
- C15: anchor forward compatibility (critic 14). A checksum-valid newest slot with `format: "rj.anchor.v2"`, an unknown hold code, or an extra key gives process `journal_schema_unsupported`, with the anchor bytes unchanged.

**Implementer D** owns `recovery_journal.py` and `tests/test_recovery_journal.py` (at most 450 syncs). D starts after A, B and C are green.
- D1: create gives ready, generation 1, no dispatch holds, and a first `decision: "admitted"`. Every minted ID comes from `id_factory`.
- D2: fixtures through `admit`, with SourceRecords built from captured bodies (projection fields per sc31, `source_group_digest` of the real `groupKey`, `body_digest` from the raw bytes): F01, F02, F04, F06, F07, cross-group and **q7**. Each is asserted through receipts, `pending()`, the snapshot and a reopened replay.
- D3: A/B/A/A, then close and reopen, then A: suppressed and `held`, with `restart_recovery` among the dispatch holds.
- D4: restart replay:
  - `pending_digest`, baselines and counts are equal across a reopen, and `verified_state_digest` equals the pre-close `state_digest`;
  - exactly one `restart_recovery` per reopen, with the correct recovered head, `anchor_lag: 0`, `wal_found` and a new boot;
  - the call order is restart COMMIT → directory sync → anchor.
- D5: capacity through small bounds:
  - the 4th arrival gives `capacity_admissions`, with one `capacity_hold` naming its source digest; the 5th writes no second hold, and the refusal counter reaches 2;
  - suppressed arrivals count;
  - with pending full, suppressed and existing-Fingerprint arrivals are still accepted;
  - bytes;
  - a reserve too small for the `capacity_hold` gives `journal_capacity_recovery`, and one too small for `restart_recovery` at open gives the held process `journal_capacity_recovery`.
- D6: latches (critic 3):
  - a clock that raises, returns a non-int or regresses, or a wall year of 1999, gives `journal_clock_invalid` with nothing written;
  - an `id_factory` returning an invalid ID gives `journal_divergence`;
  - an `id_factory` returning **an existing event ID** gives the process `journal_divergence`: nothing written, anchor bytes unchanged, and the reopen **ready** with the chain intact.
- D7: commit failures:
  - an SQLite authorizer denying INSERT gives `journal_write_failed`, then `journal_held`; the reopen is ready, and the repeat is admitted;
  - `_commit_sql` executing COMMIT and then raising latches; the reopen retains the admission, and the repeat is suppressed.
- D8: anchor-sync failure gives `journal_write_failed` and no receipt. The reopen accepts lag 1, re-anchors, and suppresses the repeat (spec L252).
- D9: held handles. A recovery hold gives `held`/`recovery` with a readable snapshot and `null` projection fields; a process hold gives `held`/`process`; `admit` gives `journal_held`.
- D10: 8 threads × 5 distinct admissions give contiguous `arrival_seq`, `event_seq` and `commit_seq`, and the reopen verifies.
- D11: the snapshot has exactly its key set, every code comes from the closed sets, and no source content appears beyond digests.
- D12: shell-level property: 3 seeds × 15 operations, with a reopen mid-sequence, against B's reference model.
- D13 (AST): `recovery_journal`'s import allowlist.
- D14: **duplicate at the shell seam (critic 9).** `_commit(plan)` with a plan that re-seals a stored commit's drafts (same IDs and content, new positions) returns the stored `event_seq`s. The head, `state_digest` and anchor counter are unchanged, no row is written, and the next `admit` succeeds.

**Tester E** owns `tests/test_recovery_journal_crash.py` and `tests/data/recovery_journal_v1_golden.jsonl` (at most 500 syncs).

**Crash images.** A fixture patches one named seam (`_commit_sql`, `_write_slot`, `_full_sync`, `persist_hold` or `write_anchor`) to `shutil.copytree` the live directory into an image and raise `SimulatedCrash(BaseException)`. The image is the kernel-visible state after a process crash. Power-loss variants edit the image:
- the newest anchor slot kept, reverted (restored to the bytes captured before the write) or torn (half written);
- the WAL trimmed to its pre-transaction size, which is legal only before COMMIT returned;
- garbage appended.

WAL frames are located by parsing frame headers, whose commit marker is the "db size after commit" field (critic q6). They are named by the commit they belong to, never by a fixed frame index.
- E1 (C2): crash in `_commit_sql` before COMMIT: ready, the admission absent, and a repeat admitted.
- E2 (C3): crash after COMMIT, before `pwrite`: ready at lag 1, re-anchored, with `restart_recovery.anchor_lag == 1`; a repeat is suppressed.
- E3 (C4): the anchor slot torn, reverted or kept gives the E2, E2 and E4 outcomes respectively.
- E4 (C5): an image taken after `admit` returns: ready at lag 0, retained, and a repeat suppressed.
- E5 (C10): crash in create before the anchor gives `journal_anchor_missing`, and create then gives `journal_exists`. A torn anchor at create gives `journal_anchor_invalid`.
- E6: **two-crash cases.** The E2 image is opened with a second crash (i) after the re-anchor, before the restart commit; (ii) after the restart COMMIT, before the directory sync; (iii) after the directory sync, before its anchor; (iv) mid re-anchor `pwrite`. Each second image opens ready with lag ≤ 1, every acknowledged admission present, and one `restart_recovery` per completed open.
- E7: two-crash during hold persistence. The E8a image is opened with a crash after the first hold slot, and again after half of the second. Each reopen is held with the same code.
- E8: **torn WAL, by commit (critic 5):**
  - (a) flipping a byte in the first frame of the **last anchored** admission commit gives `journal_truncated`;
  - (b) flipping a byte in a **genesis** frame gives an empty presentation, and so `journal_truncated`, not an identity mismatch;
  - (c) flipping a byte in the frame of the **unanchored lag-1 commit** (from an E2 image) gives ready at lag 0, with `wal_found.digest` equal to the damaged WAL's tagged digest;
  - (d) trimming the WAL by one frame after acknowledged commits gives `journal_truncated`;
  - (e) appending garbage gives ready, with `wal_found` recording it;
  - (f) deleting the `-wal` before any autocheckpoint gives `journal_truncated`, from the empty presentation.
- E9: stale restore. Copy DB and WAL at k, run to k+m, then restore the copy while keeping the newer anchor: `journal_truncated`. Restoring the good files afterwards stays held (sticky).
- E10: an older anchor copy with a newer DB gives `journal_tail_unverified`; another journal's anchor gives `journal_identity_mismatch`; a deleted anchor gives `journal_anchor_missing`.
- E11: body damage in the main file. The test helper checkpoints the image with a raw connection first, because the journal itself never checkpoints on close.
  - An **un-re-signed** flip inside `"decision":"admitted"` gives recovery `journal_record_invalid`, with the anchor carrying the hold (critic 2).
  - A damaged page header gives `journal_corrupt`.
- E12: on an image whose triggers were dropped and re-created:
  - a forged row with valid self-digests but a wrong predecessor gives `journal_chain_broken`;
  - swapped bodies give `journal_chain_broken`;
  - a re-signed `dedupe_decision` changed to `suppressed`, with the chain rebuilt, gives recovery `journal_replay_mismatch`.
- E13: transient open failure. `_read_anchor` or `_connect` raising `OSError(EIO)`, or a `sqlite3.OperationalError` with code 522, gives held/process `journal_open_failed`. The anchor, DB and WAL bytes are unchanged, and the next open is ready.
- E14: end-to-end fsync failure. `fcntl.fcntl` raising `ENOTSUP` for the anchor's `F_FULLFSYNC` gives `journal_write_failed` and no receipt; the reopen adopts lag 1.
- E15: SIGKILL loop, 5 iterations. A child admits in a loop and prints each `admission_id` after `admit` returns; the parent SIGKILLs it after n receipts. Every reopen is ready, every printed ID is present, and the lag is ≤ 1. This is labelled process-crash evidence only.
- E16: **golden guard.**
  - The data is a 13-record JSONL: genesis with `max_admissions` 5; A, B, A, A; `restart_recovery`; A; then the 6th arrival's `capacity_hold`. It is generated once by a deterministic helper in the test (a seeded UUID `id_factory` for every ID including `boot_id`, and fixed clocks), then committed.
  - It is loaded into a fresh store with raw inserts and `_encode_slot`.
  - `replay(open_record(b) for b in bodies)` must give the pinned `state_digest` and head digest.
  - `open_recovery_journal` must then be ready, with `verified_state_digest` equal to the same pinned value, and a pinned `pending_digest`.
  - Later units keep this test green.
- E17: **no evidence destroyed (critic 1).** After a held open and close, the DB **and** `-wal` are byte-identical for the E8a (mid-WAL), E8b (genesis frame), E9 (stale restore) and E10 images. So is the anchor for anchor-missing and anchor-invalid images. A ready open followed by close keeps the WAL's inode.
- E18: open-time measurement (critic 15). A 2,000-pair image is built through the golden loader path: pure-planned records, one raw transaction, and the anchor via `_encode_slot`. The test times `open_recovery_journal` and records the extrapolation to 10,000 pairs in `validation.json`. It never asserts on the time.

**Tester F** owns `tests/test_recovery_journal_adversarial.py` (at most 300 syncs).
- F1: mutation matrix (pure). For every leaf of every golden record: delete the key; add a sibling; or substitute `None`, `True`, 0, −1, 2^53, `"x"*N`, `[]` or `{}`. After re-signing (recomputing the digest and the chain), `open_record` plus `verify_commit` must reject each with a typed error. Mutations that are valid by type are explicitly allow-listed.
- F2: 40 seeded single-bit flips of a checkpointed DB image. Each open is held, or ready with a `verified_state_digest` identical to the original's. It is never ready with different state (critic 12).
- F3: free-text audit. Every string leaf of every stored body in D's and E's journals matches one of the closed grammars (I17).
- F4: custody. Marker-carrying invalid inputs to all four modules give errors with `args == (code,)` and no cause or context. The markers are absent from `repr`, snapshots and anchor bytes.
- F5 (AST, all four modules): `except` bodies; `from None` after `try`; exact allowlists; no UPDATE or DELETE DML; no `print`, `logging`, `subprocess`, `socket` or `http`; `open(` and `os.open` only in `journal_store`.
- F6: hold stickiness after a persisted `journal_truncated`:
  - (a) restoring pristine DB and WAL leaves it held;
  - (b) zeroing the newest hold slot leaves it held;
  - (c) zeroing both slots gives `journal_anchor_invalid`;
  - (d) a pre-hold anchor with a pristine DB at that head gives ready. This asserts the documented consistent-rollback **non-claim**.
- F7: process holds (write failure, clock, open I/O, append-time ID overlap) leave the anchor, DB and WAL bytes unchanged.
- F8: **classification by verification order (critic 2).** Through store images:
  - an un-re-signed flip gives recovery `journal_record_invalid`, persisted;
  - a re-signed record with `commit_size: 9` and the chain rebuilt gives process `journal_schema_unsupported`, with the anchor bytes unchanged;
  - a re-signed `schema_version: 2` does the same;
  - a re-signed unknown enum value does the same;
  - a re-signed semantic change gives recovery `journal_replay_mismatch`.
- F9: **rollback cannot brick (R2).** After an F8 process hold, close. Restoring the pre-mutation copy of that one record's image (the "roll-forward" view) opens ready, because no verdict was persisted.

**Root** owns:
- `docs/recovery-journal.md` (next section);
- the baseline, measured before any edit: plain `pytest -q`, expecting 3500 passed and 36 skipped;
- the focused command, with its wall time recorded (estimated 60-90 s on macOS; never asserted):
  `pytest -q tests/test_journal_records.py tests/test_journal_reducer.py tests/test_journal_store.py tests/test_recovery_journal.py tests/test_recovery_journal_crash.py tests/test_recovery_journal_adversarial.py tests/test_forwarder_json.py tests/test_forwarder_json_adversarial.py tests/test_receiver.py tests/test_replay.py`;
- the full suite, `pytest -q`: 0 failures, and a skip count equal to 36 plus this unit's platform-specific skips (the Linux primitive variant on darwin), each named in the outcome;
- `ruff check` on the new files, and `git diff --check`;
- `git diff --stat` empty for every existing path, and `git status --porcelain` showing only the new files plus the four protected paths, unchanged (hashed before and after);
- `.scratch/many-alerts-one-incident/reviews/recovery-journal/validation.json`, with SHA-256 hashes of sources, tests, golden data, docs and both suite logs, plus the recorded timings.

An independent reviewer binds the final hashes before the single local commit. There is no push.

## Documentation (`docs/recovery-journal.md`, root, new)

1. **What it is and is not:** not wired into the Receiver; no dispatch; the running demo still acknowledges without a durable record.
2. **Files, modes and locks, and the runtime constraint:** Python ≥ 3.12 capability, with `sqlite_unsupported` on 3.11. **Operator rules:**
   - `create` is explicit, and the code never deletes;
   - recovering from a failed create means removing the three files;
   - backups copy the whole directory, because the WAL is kept across closes;
   - never edit the files.
3. **Settings, the acknowledgement and the durability primitives**, including SQLite's silent `F_FULLFSYNC` fallback, the fail-closed anchor and directory syncs, and no-checkpoint-on-close.
4. **Anchor format**, and where durable verdicts live: what clears them and what does not, and lifting only by reconstruction into a new directory.
5. **Records:** envelope, types, commit shapes, digests, transaction numbering, and the verification order.
6. **Admission semantics:** the dedupe key, the truncation rule, results, pending and cross-group reclaim, decision, the worked example, and the legacy-pair consequence.
7. **Hold tables** (three kinds) and error codes.
8. **Crash matrix.**
9. **Bounds, and the open-time budget:** about 1.5 ms of codec work per realistic pair on the dev Mac (probe p8), about 20 s at 10,000 realistic admissions, about 1.5-2 minutes at the adversarial byte bound, with no admission during open.
10. **Extension rules R1-R7:** the consumption watermark; the ticket-38 record family (`billing_import` actor; reset never resets accounting, acct L193-195 and spec L293-294); spool-before-commit order.
11. **Non-claims**, and the focused pytest command.

## Judge conflicts resolved

1. **Sticky integrity holds** (J1 praises them; J2 cut 3 removes them).
   - *Evidenced physical* failures are durable. They are persisted in both anchor slots, or re-derived from unchanged anchor bytes.
   - *Transient* failures (`OSError`, or SQLite primary codes other than 11 and 26) and *writer-format* failures (typed failures on digest- and chain-verified rows, newer formats) are visible process holds that are never persisted.
   - Replacing the DB or WAL cannot clear a persisted verdict. A consistent whole-directory rollback, or a same-uid anchor rewrite, can; that is a stated non-claim.
   - Revision 2 adds that opens never destroy evidence (critic 1), and that persisted codes always have stored evidence (critic 3).
2. **Raw-body sanitizer** (J2 cut 1): **applied**. Unit 15 keeps `SourceRecord`, `validate_source`, `canonical_number`, `source_group_digest` and `dedupe_key`. Tests build records from the sc31 projections and the real `groupKey` and body bytes. No concrete reason to keep the sanitizer was found: its open questions are observable only at the deferred HTTP seam.
3. **Numeric equality, the dedupe key, `pending_reduced`, suppressed-repeat capacity and strict limits** are decided concretely above. They are listed as P1-P6, P12 and P25, including the three rules the critic required for decision (c).
4. **SQLite's silent `F_FULLFSYNC` fallback** is stated from source reading and was not probed. The anchor and directory syncs fail closed and are tested (C7, C8, E14).

## Judge findings resolved

| Finding | Resolution |
|---|---|
| J1 S-E1, D-E3: anchor lag unbounded or any lag accepted | Lag ≤ 1; more gives `journal_tail_unverified`. Re-anchor before `restart_recovery`. Probe p5: 0 bad paths, against 24 with the old order. Tests E2, E6. |
| J1 S-E2, D-E4: "COMMIT ⇒ `F_FULLFSYNC`" overclaimed | Restated ("Durability primitives"). The anchor and directory syncs never fall back (I22; C7, C8, E14). |
| J1 S-E3, L-E5: fsyncgate overclaimed | Restated as "kernel-visible state; loss is later detected by the anchor". |
| J1 S-E4, L-E10, D-E5; J2 sqlite 5: conflict only a dispatch hold; invented `journal_hold` record; `id_collision` without a hold | No new record type. **Revision 2 (critic 3):** an append-time overlap is the process hold `journal_divergence`, which still holds the journal (spec L100-101) but persists nothing without evidence. Two stored rows sharing an ID are durable at open. |
| J1 S-E5: append-time validation failure only a refusal | A pre-commit `verify_commit` failure latches `journal_divergence` (J1 graft 7). |
| J1 S-E6: no transaction framing | `commit_seq`, `commit_index` and `commit_size`; `group_commits` (B6, B7). |
| J1 S-E7, D-E9: physical ceiling above the spec bound | The logical charge includes the measured 384 B overhead; the physical backstop is 160 MiB plus an 8 MiB WAL (P11). |
| J1 S-E8: absent `truncatedAlerts` stored as 0 | `null` means unknown, and never suppresses (P15; critic 6). |
| J1 S-E9: single-Fingerprint tension not flagged | P1. |
| J1 S-E10: `capacity_hold` does not name the refused arrival | It records `refused_source_digest` and `requested`; later refusals are counted per boot (P22). |
| J1 S-E11: idempotence unreachable through `admit` | Stated. Covered by C9 (store) and D14 (shell seam, critic 9). |
| J1 L-E1; J2 log 1: false hold after a double crash | Same lag rule and order; two-crash tests E6 and E7. |
| J1 L-E2: holds not persisted | Anchor-persisted verdicts ("Where a durable verdict lives"). |
| J1 L-E3; J2 log 6: quarantine and truncate at open | Not adopted. SQLite ignores uncommitted frames, `restart_recovery.wal_found` records them, and **no open deletes or checkpoints anything** (critic 1). |
| J1 L-E4: conflict records deduplicated per digest | No conflict record type. |
| J1 L-E6, D-E7: folder added to the source group | Not adopted. The group is the exact `groupKey` digest (P16). |
| J1 L-E7; J2 log 7: `values` absent or null mapped to `{}`; `null` inside rejected | Not adopted. `null` ≠ `{}`, and `null` is allowed inside `values` (P3). |
| J1 L-E8: untagged ingress digest | `body_digest` is tagged `rj.body.v1`; its use as a confirmation oracle is a non-claim (P15). |
| J1 L-E9: `source_time` from `endsAt` | Not adopted. Only `starts_at`, provenance only. |
| J1 L-E11; J2 log 4: durability tested through a fast IO | Not adopted. Real sync everywhere, with named private seams. |
| J1 D-E1; J2 domain 1: `Decimal.normalize` breaks equality | Float64 rule with known-answer rows (probe p1; A6, A7). |
| J1 D-E2; J2 domain 7: tmp+rename anchor, plain directory sync, two syncs | Two-slot in-place `pwrite` plus one full sync; rename is never used. |
| J1 D-E6; J2 domain 3: caller-asserted restart reason | Not adopted. `restart_recovery` records only observed facts. |
| J1 D-E8: 16 members | 32 alerts, bounded in practice by the 4 KiB record (probe p3). |
| J1 D-E10: refuted storage rationale | Moot. SQLite is kept for spec L142, J2 fit and ticket-38 co-location. |
| J2 sqlite 1: transient I/O becomes a permanent hold | The evidenced/transient split; transient failures are process holds (E13, F7). |
| J2 sqlite 2: ticket-38 needs a DDL migration | Accounting joins as a record family in the same table (J2 graft 4; P19). |
| J2 sqlite 3, log 5, domain 5: `run_intent` lists overflow | Watermark rule R7 (J2 graft 6). |
| J2 sqlite 4: no body correlation | `body_digest` (J2 graft 3). |
| J2 sqlite 6 and cut 4: `NO_CKPT_ON_CLOSE` needs 3.12 | **Reversed in revision 2 (critic 1).** The cut's premise, "the content survives a checkpoint", is false for a mid-WAL corrupt frame (probe p7). The setting is mandatory, and 3.11 fails closed (P26). |
| J2 sqlite 7: lifetime counts and generation equality | Counters per generation; "current generation" rule; the step-11 check compares the anchored record's generation (critic 14). |
| J2 sqlite 8, domain 2: test estimate low; over budget | Pure layer; about 3,400 test lines; sync-counted budget (critic 8); 4 modules of about 1,500 lines. |
| J2 log 2: caller-supplied `admission_id` | Not adopted. `admission_id` is the admission's own journal-minted `event_id` (P14). |
| J2 log 3: later-unit limits in genesis | Not adopted. Genesis records four bounds, validated against `V1_BOUND_CEILINGS`. |
| J2 log 8: invented enums not marked | All marked (P17). |
| J2 domain 4: durable hold on any `DatabaseError`; marker file | Classification by primary code (critic 4); no marker file. |
| J2 domain 6: in-chain exact duplicate becomes corrupt | Unreachable (UNIQUE); at open, two stored rows sharing an ID are `journal_event_conflict` (I5). |
| J2 domain 8: `test_replay.py` consequence omitted | Deferred 2. |
| J2 domain 9: authority citation | Re-read: the text is proposal L32-36. |
| J1 grafts 1, 2, 3 | Applied (framing and lag rule; B5, B6, B9, E1-E18; C7, C8, E14). |
| J1 graft 4 (non-silent WAL discard, with `NO_CKPT_ON_CLOSE`) | Applied **in full** in revision 2: `wal_found` plus mandatory no-checkpoint-on-close. |
| J1 grafts 5-9 | Applied (P22, P15, `journal_divergence`, P1, do-not-adopt list). |
| J2 cuts 1, 2, 5 | Applied. |
| J2 cut 3 | Applied to transient and writer-format failures; evidenced physical failures remain durable per spec L243-246. |
| J2 cut 4 | Reversed (critic 1). |
| J2 grafts 1-10 | Applied. |

## Critic issues resolved (revision 2)

| Critic issue | Resolution |
|---|---|
| 1 (high). A held open's close destroys acknowledged WAL evidence | Reproduced by probe p7: 7 of 17 rows visible, and closing without the setting deleted the WAL, including frames of 10 committed rows. With the setting, DB and WAL stayed byte-identical. `SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE` is now **mandatory**: set before the first statement of every connection, read back, never cleared. `open` only reads `journal_mode`. Python 3.11 fails closed with `sqlite_unsupported` before touching any file (capability check, C14); `pyproject.toml` is unchanged, and the constraint is P26. The false "only invalid bytes are lost" claim is removed (I3, E17, "Residual risks"). J2 cut 4 is reversed. |
| 2 (high). Corruption misread as a newer format; rollback bricking | Row pipeline, in order: raw-byte digest, parse, chain, columns, typed, framing, replay. Digest, chain and column failures are durable; parse and typed failures on verified rows are process holds, never persisted. R1 now bumps `schema_version` on any validator or bound change. R2 lists the three process-only cases an older binary can meet, and newer anchor slots are process holds. Tests A2, E11, F8 and F9. |
| 3 (medium). Append-time conflict persisted without evidence | The process hold `journal_divergence`; nothing written or persisted (D6, F7). A durable `journal_event_conflict` only for two stored rows at open. P8 rewritten. |
| 4 (medium). Extended versus primary SQLite codes | Classified on `sqlite_errorcode & 0xFF`; `sqlite_errorname` shown. C10 covers 779, 523, 267, 522, 3850 and 2067. |
| 5 (medium). E8 expected code wrong; whole-WAL loss misnamed | Step 9.1 treats an empty presentation with a valid anchor as `journal_truncated` before the identity checks. E8 rewritten by commit, with expected codes (a)-(f), frames located by header. |
| 6 (medium). Decision (c) additions | (i) An arrival with `truncated_alerts` not 0, or `null`, is never suppressed, and its baseline is `complete: false` (B12). (ii) Groups over 32 alerts, 64 values or 4 KiB are refused, never split or locally truncated, in v1 (P1). (iii) Cross-group pending is P25. |
| 7 (medium). Pending held the latest *non-suppressed* arrival | Decided per spec L221-222, f31 L65-66 and L58: option (a), where a suppressed arrival reclaims only entries another group holds and never creates one. The q7 sequence is in B1 and D2. Option (b) is the recorded alternative (P25). |
| 8 (medium). Test-time budget not achievable | B5 bounded: 100 × 50, with replay every 10th step, about 8 s. B6 on 5 seeds. The budget counts every sync, including create and open; module-scoped base images are copied. Timings are recorded, never asserted, and the focused estimate is 60-90 s. |
| 9 (low). Duplicate desyncs `_commit` | `find_duplicate` returns a typed `Duplicate` before verification; `_commit` returns stored positions and skips `apply_delta` (D14). |
| 10 (low). Genesis bounds tied to code defaults | Frozen `V1_BOUND_CEILINGS` (A5). |
| 11 (low). WAL directory entry after reopen | `append(..., sync_directory=True)` for the `restart_recovery` commit gives COMMIT → directory full sync → anchor (C7, D4). The WAL is no longer deleted at close (probe p7). The residual is stated. |
| 12 (low). F2 impossible; `boot_id` source | `verified_state_digest` in the snapshot (F2, D4, E16). Every ID, including `boot_id`, comes from `id_factory`. |
| 13 (low). API ambiguities | (i) `thaw` before encoding (A4). (ii) Key over `source_to_json` object-form `values`; nine full goldens (A9). (iii) `_list_digest` restated: concatenation, sorted by canonical bytes. (iv) `WalFound` in `journal_records`, used everywhere. (v) A2's escape restated in words. (vi) `observed_commit_seq` defined. |
| 14 (low). Later-unit fit of the anchor and seams | Intact newer-format slots give process holds (C15). Holds are lifted only by reconstruction into a new directory. The step-11 generation compares the anchored record. Spool-before-commit and the verify-only inspection mode are recorded in Deferred 2 and 6. |
| 15 (low). Open time at the bounds | Digest from raw bytes; the stored `content_digest` column dropped. Probe p8: 3.0 s for 2,000 pairs, extrapolated to about 20 s at 10,000 (E18 records it). The budget is in the docs, and a fast path is Deferred 11. |

None of the critic's issues is rejected. Two resolutions go further than the critic proposed:
- **Issue 1.** No-checkpoint-on-close stays set on the ready path too, not only while held. This keeps close behaviour uniform and the WAL inode stable, and it narrows issue 11.
- **Issue 15.** The `content_digest` column is removed rather than kept and re-verified.

## Proposals requiring ratification

Each of these freezes into v1 records or replay rules; changing one later needs a schema or `rule` version.

- **P1. Record granularity and the dedupe key.**
  - One `SourceRecord` per Notification, with a sorted member list. The key digests the whole sorted `(fingerprint, status, values)` list, compared with the latest admitted key of the same `source_group` (f31 L63-64).
  - Spec L156-158 describes a single-Fingerprint source record. This plan therefore reads "64 numeric values per source record" as the total across members, "4 KiB canonical source record" as the whole Notification's record, and the pending bound as counting Fingerprints.
  - **(i) Truncation.** `truncated_alerts` other than 0, or `null`, never suppresses, and its baseline is incomplete.
  - **(ii) Large groups.** A Notification with more than 32 alerts, more than 64 values or more than 4 KiB canonical is **not admissible** in v1. The ingress unit refuses it and chooses the HTTP class; it must never split the Notification into several admissions or drop members locally. Splitting would change what "suppressed" means, and local truncation would change what `truncated_alerts` means; either requires `latest-admitted-v2`. No capture comes close (at most 4 alerts and 849 B).
- **P2. Numeric equality** is float64 value equality through canonical strings: `100 = 100.0 = 1e2` gives `"100"`, and `0.1 = 0.10000000000000001` gives `"0.1"`. Go's deterministic float64 encoding makes this coincide with lexeme equality for real senders (critic 6). Integer lexemes above 2^53-1 are refused by `parse_json` at the future ingress, although Go prints integral floats up to 1e21 without an exponent.
- **P3. `values`:** `null` (absent, or JSON `null` at ingress) is distinct from `{}`; a `null` value inside the object is allowed; refIds use `[A-Za-z0-9._-]{1,32}`.
- **P4. `pending_reduced`** means the arrival superseded at least one unconsumed pending entry. `admitted` means it was not suppressed and superseded none. Reduction happens whenever an entry is unconsumed: in unit 15 always, and in the full system exactly "while a job is held or running" (spec L221).
- **P5. Pending bound:** 1,024 distinct pending Fingerprints. Suppressed arrivals and reclaims never fail it.
- **P6. Suppressed repeats** get an `admission_id` and both records. They count against the 10,000 admissions per generation and the bytes, never against pending (spec L58).
- **P7. `decision: "held"`** means at least one journal-derived dispatch hold was active before the commit. It never authorizes dispatch (spec L297-302). After the first restart every admission is `held` until the operator unit exists.
- **P8. Event-ID conflicts.**
  - An append-time overlap is the **process** hold `journal_divergence`: the journal is held (spec L100-101), and nothing is persisted, because no conflicting bytes are stored.
  - Two stored rows sharing an ID are the durable `journal_event_conflict`.
  - An exact duplicate is idempotent (spec L101-102).
  - The effects unit must add retained conflict records for externally keyed receipts (spec L120) and revisit this rule. If the literal "durable" reading is ratified instead, the anchor hold must carry the refused `content_digest` and the stored `event_seq`, which is a format change.
- **P9. Tail policy.**
  - SQLite ignoring frames without a valid commit frame is the spec L251 window; `wal_found` records it, and the WAL is never deleted.
  - Exactly one complete, verified commit beyond the anchor is adopted and re-anchored before any append.
  - More than one, an incomplete group, a missing or invalid anchor, a head below the anchor, or an empty presentation is durable.
- **P10. Hold scopes**, as in the tables:
  - evidenced physical failures are durable;
  - transient and writer-format failures are process holds, including every typed failure on a verified row;
  - `journal_capacity_recovery` is a process hold.
- **P11. Byte bound.** Logical charge is `len(body) + 384` per record; 112 MiB ordinary and 128 MiB total. The physical backstop is `max_page_count` 40,960 plus a WAL of at most 8 MiB after checkpoints, so up to about 168 MiB on disk.
- **P12. Strict limits** as in "Proposed bounds".
- **P13. Record types:** `journal_genesis` is new; `restart_recovery` and `capacity_hold` fields as tabled; the baseline update is folded into `dedupe_decision`; the `rule` field and the `complete` baseline flag; closed commit shapes.
- **P14.** The `admission` record's `event_id` is its `admission_id`.
- **P15. Provenance-only fields:** `truncated_alerts` (`null` means unknown and disables suppression), `starts_at` and `body_digest`. `body_digest` is a confirmation oracle for a guessed body; a keyed digest would need a secret, which is the ingress unit's decision.
- **P16. Source group:** the tagged digest of the exact `groupKey`.
- **P17.** The v1 enums and the additive rule R2; provenance kinds are `{http}`.
- **P18.** The anchor sits on the same volume, so it is not the independent integrity anchor of integ L84.
- **P19. Ticket-38 co-location.** The `acct.*` family goes in the same table, chain and commit groups. This couples 30-day and 52-week retention, and needs the ticket-38 owner's agreement (acct L45-56, L229-240).
- **P20. Operational sequencing.** Every restart holds dispatch, and this unit has no resume. An operator inspect/resume unit must therefore precede or accompany `receiver.py` integration.
- **P21. Durability primitives:** `F_FULLFSYNC` on darwin and `fsync` on Linux for the anchor and directory, failing closed. SQLite's own WAL sync may fall back silently.
- **P22.** At most one `capacity_hold` per code per generation, naming the first refused source digest. Later refusals are counted per boot in memory only. A durable refusal summary is deferred to the ingress unit.
- **P23.** Bounds are injectable only at create, capped by `V1_BOUND_CEILINGS`, and recorded in genesis. Counters are per generation.
- **P24. Names:** digest tags `rj.*.v1`, the file names, `application_id` "RJNL", and `event_seq`/`commit_seq` starting at 1.
- **P25. Cross-group pending** (critic 7). Option (a), adopted: a suppressed arrival keeps its result and its group's baseline, and reclaims existing pending entries of its members that another source group holds, naming them in `superseded`. It never creates an entry. Option (b): keep pending at the latest non-suppressed arrival, and document the lost-Resolved corner of critic q7.
- **P26. Runtime constraint** (critic 1). The journal requires `sqlite3.Connection.setconfig` and `SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE`, which means Python ≥ 3.12. On 3.11 construction raises `sqlite_unsupported` before any file is touched. `pyproject.toml` keeps `>=3.11` for the rest of the package. The container and the local interpreter are 3.13.
- **P27. Verification order and classification** (critic 2), as in open step 10. It relies on the R1/R6 versioning discipline, enforced by the E16 golden guard.

## Deferred

1. **Raw ingress and sanitizer.**
   - `sanitize_notification`, with a bounded body (256 KiB) and `parse_json(numbers="finite")`;
   - `body_digest` computation; Go zero time; the `capture` provenance kind;
   - tests over the 115 captured bodies;
   - the P1 (ii) refusal and its HTTP class (a lost Resolved leaves OPS stale);
   - a durable refusal summary.
2. **`receiver.py` integration.**
   - Open at startup; a held journal gives 503 for admission.
   - `admit` before the 202; `JournalError` gives 503 with `Retry-After`.
   - Check that the journal directory lies outside `runs_directory`; the conftest `receiver` fixture creates a fresh journal per test.
   - The **body spool** keyed by `body_digest` must be written and synced **before** the admission commit, with orphans (spooled but never admitted) collected by digest absence (critic 14).
   - Health showing holds.
   - A deliberate change to `test_the_sequence_arrives_in_order_and_starts_one_run_each`, because the legacy repeat is suppressed; `replay()` still returns `[202, 202, 202]`.
   - Must follow, or ship with, item 6.
3. **Run lifecycle.**
   - `run_hold`; `run_intent` consuming pending by watermark (R7);
   - lease and launch claim; spawn and terminal observations;
   - "run intent without spawn observation means launch unknown, plus a hold";
   - evidence-byte reservations (acct L224-227 pattern).
4. **Effects.** `effect_intent`, `effect_receipt` and `reconciliation`. Receipt `event_id`s derive from the Forwarder `receipt_id`, and conflicting receipts are retained as records (spec L120), which revisits P8.
5. **Ticket-38 reservations.** The `acct.*` family in the same commit groups; `billing_import`; reset never touches accounting.
6. **Operator actions.** Inspect through a **verify-only open mode** that appends nothing (critic 14); resume, which clears `restart_recovery`; capacity clear; cancel, retry and abandon; `reset_commit` (generation + 1).
7. **Retention and compaction.** 30-day compaction to a digest/identity manifest, and the overdue-retention hold (spec L281-286).
8. **Reconstruction and handoff.** Lifting durable recovery holds by building a new journal in a **new directory** (new `journal_uuid`, generation + 1, genesis referencing the old head), leaving the held directory as evidence; `handoff_manifest`; an off-volume anchor (spec L245-246, L269-270; integ L84).
9. **Venue.** OS or mount isolation from Runs; venue volume durability; a Linux-container suite run; a real Python 3.11 run of the fail-closed path.
10. **Gates.** The dispatch-gate conjunction, and the venue, budget and reference holds (spec L297-313).
11. **Open fast path.** Skipping the canonical round trip, or a faster strict decoder, only if a measured open exceeds a reviewed target (critic 15).

## Not qualified by this unit

- Power-loss durability on any real device, or whether the venue storage honours `fsync` or `F_FULLFSYNC`.
- SQLite's `F_FULLFSYNC` fallback, and its plain-`fsync` WAL directory sync. Both come from source reading and were not probed.
- Persistence across pod or container restart on the intended volume (spec L32-33), and survival of cluster destruction.
- Detection of a consistent directory rollback or a same-uid forger.
- Inaccessibility to Runs.
- Real Receiver HTTP admission before the ACK (spec L322); Grafana's retry behaviour.
- Notification shapes beyond the SourceRecords the tests build.
- Linux `fsync` semantics beyond primitive selection.
- Behaviour on a real Python 3.11 interpreter, which was unavailable here; only the capability seam is tested.
- `flock` and SQLite locking on network or multi-node volumes.
- Open time at the full bounds, which is extrapolated from 2,000 pairs.
- The ratification items.
- Any spawner, Forwarder, effect, accounting, operator, venue or reference-revocation behaviour.

## Residual risks the reviewers must accept

- **Same-volume anchor.** A consistent rollback of all files, or a device that drops both WAL and anchor writes, is undetectable locally.
- **Sticky false positives.** Storage that once returns wrong bytes *without* an I/O error persists a recovery hold that nothing in this unit can lift. A later reconstruction unit must build a new directory.
- **Stopping at the first finding.** A process-scoped writer-format finding stops the scan, so it can hide a later physical failure until a newer binary opens the journal. The journal is held either way.
- **Python 3.12 capability.** The journal cannot run on a 3.11 interpreter that `pyproject.toml` still allows. It fails closed with `sqlite_unsupported`.
- **WAL-only recent commits.** Close never checkpoints, so a clean close leaves recent commits only in the WAL. Copying only `journal.sqlite3` is an incomplete backup, which open reports as `journal_truncated`.
- **WAL directory metadata.** The WAL's directory entry is fully synced at genesis and after every restart commit. A WAL deleted and recreated by something outside the journal is covered only from the next open onwards.
- **Dispatch after restart.** Every restart holds dispatch until the operator unit lands, so integration before that means no Runs after the first restart.
- **Latency.** About 39 ms per admission on macOS serializes handler threads. That is acceptable at the captured rates.
- **Open time.** About 20 s at 10,000 realistic admissions, and 1.5-2 minutes at the adversarial byte bound, with no admission during open.
- **Refused Notifications.** Strict validation and the P1 (ii) refusal of large groups can refuse real Notifications; the ingress unit must make those refusals visible.
- **Simulated crashes.** Crash images and the SIGKILL loop model process crashes only; power loss is simulated by editing images.
- **Test time.** Real syncs dominate. The focused run takes an estimated 60-90 s on macOS.
- **Naming coupling.** The journal imports `forwarder_json`; renaming it to a neutral module is a later refactor.
