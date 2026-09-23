# Strict JSON, Receiver scope manifests and read-only Jira route policy

2026-09-22, revision 2. This is the twelfth separately authorized local application unit under the
[approval record](../native-runtime-source-implementation-approval.json). Revision 2 resolves all 16 critic issues. The "Critic issues resolved" section lists each one with its resolution. No issue is rejected.

**Baseline.** The baseline is the reviewed local commit of the eleventh (receipts) unit. This unit does not start until `forwarder_receipts.py`, `forwarder_response_send.py` and their tests are committed.

**Protected state.**
- Preserve the four protected dirty files: issue 19, `planning-frontier-2026-09-18.md`, and the two ticket-19 `c2-ingestion-*` files.
- Ticket 19 C2 is provider-blocked. This unit neither touches it nor depends on it.

**Out of bounds.** No push, no provider, native or tenant call, no real credential, no real tenant ID, no paid experiment and no deployment.

**Rules.**
- Existing modules and their tests stay unchanged.
- Neither new module has a `raise` statement inside an `except` block. This is AST-checked; see "Error discipline".
- Run the full suite before the commit.
- Root saves this plan as `.scratch/many-alerts-one-incident/reviews/forwarder-routes/implementation-plan.md`.

## Why this unit

The receipts ledger reserves each receipt with a `route_id` and a 64-lowercase-hex `request_digest`. It finalizes `TRANSPORT_CONFIRMED` with `ok` or `response_policy_rejected`. Nothing computes those values yet.

The "Route policies" section of the [Forwarder specification](../ticket-36/forwarder-specification.md) (L245-253) requires:
- undeclared routes, fields and schemas are rejected before dispatch;
- `scope_digest` binds allowed IDs, rehearsal, operation class and revision to the lease, and caller strings only select within it;
- JSON is strict and bounded: depth <=16, arrays <=256, strings <=16 KiB, finite integer ranges;
- route configuration is operator-owned, capped at 64 KiB, and digest-recorded.

The common HTTP boundary (L199-201) requires the Forwarder to rebuild the upstream request, never forward caller bytes.

This unit builds each piece that carries authority and proves it once, on the smallest route set that exercises all of them:
1. strict bounded JSON;
2. one pinned canonical encoding;
3. an operator venue policy digest;
4. a Receiver scope-manifest digest that is exactly the lease `scope_digest`, with a manifest-to-grant binding check;
5. a request digest over the reconstructed upstream request;
6. a validate-or-reject response policy mapped onto the receipt reasons.

Two routes are matchable:
- `jira.issue.get`, for manifest-registered issues;
- `jira.search`, first page only.

Both are reads, so no AuthorizeDispatch permit exists or is needed (spec L221). Together they exercise:
- path-ID selection;
- fixed-query re-encoding;
- a caller JSON body with an integer range and exact template selection;
- returned-scope verification (spec L268-269).

Every other route is explicitly unavailable, with closed missing-input codes. See spec L441-448 and ADR 0011: "A service route without enforceable scope remains unavailable".

Tenant values reach the code only through a trusted operator `JiraVenuePolicy` object. Tests fill it with obviously synthetic values that deliberately differ from the historical Skill bindings (`OPS`, `customfield_10085/10079/10096/10083`); see ADR 0004 L10 and spec L259-261.

**Out of scope for this unit:**
- resolving a sentinel to its lease or manifest;
- delivering manifests over control;
- calling `LeaseRegistry.check` or `ReceiptLedger` from source code;
- serializing or sending an upstream request;
- injecting credentials;
- projecting responses;
- tracking continuations;
- enabling any mutation;
- reading custom fields;
- wiring readiness.

## Module 1: `grafana_jsm_sandbox/forwarder_json.py`

No I/O, clock, state or authority. Direct imports are exactly `__future__`, `dataclasses`, `hashlib`, `json`, `math` and `re`, with no relative imports. Target: 300 lines or fewer.

**Constants**

| Name | Value | Source |
| --- | --- | --- |
| `MAX_JSON_DEPTH` | `16` | spec L251 |
| `MAX_JSON_ARRAY_ITEMS` | `256` | spec L251 |
| `MAX_JSON_STRING_BYTES` | `16_384` | UTF-8 bytes, for keys and values; spec L252 |
| `MAX_SAFE_INTEGER` | `2**53 - 1` | spec L252, "finite integer ranges" |
| `MAX_JSON_NUMBER_CHARS` | `32` | local lexeme bound, so `int()`/`float()` never see a huge token |
| `MAX_JSON_DOCUMENT_BYTES` | `1_048_576` | spec L169 response cap |

These bytes bound the object-member count and key length; there is no separate cap for either, and the spec gives no value.

**`JSON_ERROR_CODES`** is a `frozenset` of: `json_argument`, `json_too_large`, `json_encoding`, `json_syntax`, `json_unicode`, `json_duplicate_key`, `json_depth`, `json_array_too_long`, `json_string_too_long`, `json_number`, `json_type`.

**`JSONPolicyError(ValueError)`**
- `.code` is in `JSON_ERROR_CODES`.
- `args == (code,)` and `str(e) == code`.
- It has no attribute other than `code`.

**`JSONDecimal`** is a frozen dataclass `(text: str)`, produced only in `numbers="finite"` mode. It holds a validated RFC 8259 fraction/exponent lexeme and is never converted to `float` in output.

### Error discipline (load-bearing, applies to both modules)

`raise X from None` alone does not remove input from the exception chain. In CPython 3.13 it clears `__cause__` and sets `__suppress_context__`, but `__context__` still refers to the handled exception. This was verified:
- `e.__context__` is the `JSONDecodeError`, and its `.doc` is the full input text;
- a `UnicodeDecodeError` carries the raw input in `.object`;
- the same chain would form when `route()` wraps a `JSONPolicyError` in a `RoutePolicyError`.

Therefore:
- **Handlers only record.** An `except` block may only assign `code = "<fixed code>"`. After the `try` statement ends, the function runs `if code is not None: raise JSONPolicyError(code) from None`, or the Module 2 equivalent.
- **No exception is re-raised.** `parse_json` never re-raises an exception object created elsewhere, including a hook's `JSONPolicyError`. It records `e.code` and raises a fresh error outside the handler.
- **No exception is needed to find bad characters.** U+0000 and lone surrogates are detected with a compiled regex over `[\x00\ud800-\udfff]` (after `json.loads`, a valid pair is already one code point), not by catching `UnicodeEncodeError`.
- **Hooks raise directly.** Hook functions raise `JSONPolicyError` directly and contain no `except` blocks.
- **Claim.** Called outside any active handler, every error raised by either module has `__cause__ is None`, `__context__ is None` and `args == (code,)`, and no attribute holds caller data.
- **Non-claims.**
  - Python attaches an exception that is active in the caller's own handler as `__context__`.
  - `__traceback__` frames reference callee locals, including the input. Diagnostic logging must use fixed categories and must not capture frame locals (spec L427-429).

### `parse_json(data, *, max_bytes, numbers="integer", ascii_only=False) -> object`

Steps, in order:

1. **Arguments.**
   - `type(data) is bytes`.
   - `max_bytes` is an exact `int` (not `bool`) in `1..MAX_JSON_DOCUMENT_BYTES`.
   - `numbers` is `"integer"` or `"finite"`.
   - `ascii_only` is an exact `bool`.
   - Any violation gives `json_argument`. `len(data) > max_bytes` gives `json_too_large`.
2. **Encoding.**
   - A leading `EF BB BF` gives `json_encoding`.
   - `data.decode("utf-8", "strict")` failing gives `json_encoding`, recorded inside the handler and raised outside it. This covers overlong forms, UTF-8-encoded surrogates, bytes above U+10FFFF and truncated sequences.
   - With `ascii_only`, every byte must be in `0x20..0x7E`, else `json_unicode`.
3. **Depth prescan.** One linear pass with an escape state machine:
   - outside a string, `"` enters a string;
   - inside a string, `\` consumes exactly the next character, and an unescaped `"` leaves the string;
   - outside strings, `[` or `{` increments depth and `]` or `}` decrements it;
   - depth above 16 gives `json_depth` before `json.loads` runs, so no input reaches `RecursionError`.

   A compiled regex over `"`, `\`, `[`, `]`, `{` and `}` is acceptable if these semantics hold.
4. **`json.loads(text, object_pairs_hook=..., parse_int=..., parse_float=..., parse_constant=...)`** with `strict=True`.
   - `object_pairs_hook`: `len(dict(pairs)) != len(pairs)` raises `json_duplicate_key`. Keys are compared after unescaping, so `"a"` collides with `"a"` and `"/"` with `"\/"`.
   - `parse_int(s)`: `len(s) > 32` or `abs(int(s)) > MAX_SAFE_INTEGER` raises `json_number`. `-0` becomes `0`.
   - `parse_float(s)`: in `integer` mode it always raises `json_number`. In `finite` mode, `len(s) > 32` or `not math.isfinite(float(s))` raises `json_number`; otherwise it returns `JSONDecimal(s)`.
   - `parse_constant` (NaN, Infinity, -Infinity) raises `json_number` in both modes.
   - **Handler order is load-bearing.** The first handler is `except JSONPolicyError as e: code = e.code`. The second is `except (json.JSONDecodeError, ValueError, RecursionError, OverflowError): code = "json_syntax"`. CPython propagates hook exceptions unwrapped (verified), and `JSONPolicyError` is a `ValueError`, so reversing the order would mask every hook code. The fresh error is raised after the `try` statement. `json_syntax` covers:
     - trailing data;
     - comments, trailing commas and single quotes;
     - raw U+0000-U+001F inside strings;
     - `\f`, `\v`, U+00A0, U+2028 or U+FEFF used as whitespace;
     - empty or whitespace-only input.
5. **Post-walk.** An iterative walk with an explicit stack is authoritative. It rebuilds lists as `tuple` and checks:
   - container depth <= 16, with the root container at depth 1 (`json_depth`; this also catches prescan bugs);
   - every array has <= 256 items (`json_array_too_long`);
   - no key or string contains U+0000 or a lone surrogate (regex; `json_unicode`);
   - every key and string is <= 16_384 UTF-8 bytes (`json_string_too_long`);
   - with `ascii_only`, every decoded character is in `0x20..0x7E` (so `é` gives `json_unicode`).
6. **Output types.**
   - Objects become `dict[str, object]` and arrays become `tuple`; scalars are `str`, `int`, `bool` and `None`, plus `JSONDecimal` in finite mode only.
   - Top-level scalars are accepted; callers check the root type.
   - Consumers use `type(x) is ...`, never `isinstance` or `==` (`True == 1 == 1.0`).

**Mode use.** `integer` mode is for request bodies and scope manifests. `finite` mode is for upstream responses only, so finite non-integers (ADF `colwidth`, decimals) do not falsely reject, while `1e400`, out-of-range integer lexemes and non-finite constants are still rejected (spec L252). No policy-document parser exists in this unit. Operator file loading is deferred (Deferred item 12) and will use `integer` mode.

### `canonical_json(value, *, ascii_only=False) -> bytes`

An RFC 8785 (JCS) subset, integers only.

**Accepted input types:**
- exact `dict` with exact-`str` keys;
- exact `list` or `tuple`, both emitted as arrays;
- exact `str`;
- `bool`, checked before `int` and emitted as `true`/`false`;
- exact `int` with `|n| <= MAX_SAFE_INTEGER`;
- `None`, emitted as `null`.

**Rejections:**
- `float`, `JSONDecimal`, bytes, sets, subclasses and non-str keys give `json_type`.
- An out-of-range int gives `json_number`.
- Depth, array and string limits apply exactly as in parsing. A cycle fails as `json_depth`.
- U+0000 or a lone surrogate (regex) gives `json_unicode`. With `ascii_only`, any character outside `0x20..0x7E` also gives `json_unicode`.

**Output bytes:**
- Members are sorted by `key.encode("utf-16-be")`, so U+1F600 sorts before U+FF5E and ASCII keys sort bytewise.
- No whitespace; the separators are `,` and `:`.
- String escapes are exactly:
  - `"` becomes `\"` and `\` becomes `\\`;
  - U+0008, U+0009, U+000A, U+000C and U+000D become `\b`, `\t`, `\n`, `\f` and `\r`;
  - every other U+0001-U+001F becomes `\u00xx`, lowercase hex.
- Everything else, including `/`, U+007F and U+2028, is literal UTF-8.
- Integers are minimal decimal.
- `json.dumps(s, ensure_ascii=False)` matches this string escaping on CPython 3.13. The known answers below are what pin it.

### `tagged_digest(tag, value) -> str`

- The result is `sha256(tag.encode("ascii") + b"\x00" + canonical_json(value, ascii_only=True)).hexdigest()`.
- `tag` must fullmatch `[a-z0-9][a-z0-9.-]{0,63}`, else `json_argument`.

**Known answers** (recomputed with an independent reference encoder during this revision)
- The Python value `{"b": 1, "a": [True, False, None], "c": "é\n\x01\"\\/\x7f ", "\U0001F600": 0, "～": 1}` encodes to 72 bytes, hex `7b2261223a5b747275652c66616c73652c6e756c6c5d2c2262223a312c2263223a22c3a95c6e5c75303030315c225c5c2f7fe280a8222c22f09f9880223a302c22efbd9e223a317d`. The U+1F600 key precedes the U+FF5E key.
- `tagged_digest("maoi.test.v1", {})` = `55789aa27a10eff073ef2f86fceea079909d9ee9957238c063aa0e7d1dde3195`.

`__all__` lists exactly the public names above.

## Module 2: `grafana_jsm_sandbox/forwarder_routes.py`

**Imports** (AST-checked by exact name).
- Absolute stdlib imports are exactly `__future__`, `collections.abc`, `dataclasses`, `hashlib`, `hmac`, `re`, `threading`, `types` and `weakref`.
- Relative imports are exactly `.forwarder_json`, `.forwarder_http` (`ParsedRequest`), `.forwarder_http_response` (`ParsedResponse`, `serialize_response`, `HTTPResponseError`) and `.forwarder_services` (`SERVICE_PROFILES`).
- It does **not** import `forwarder_leases` or `forwarder_receipts`.

**Side effects.** No socket, clock, file, environment or credential access. The only state is each `RoutePolicy` instance's lock-guarded registry of issued `RoutedRequest` objects.

**Sentinel.** The module never reads `ParsedRequest.sentinel`.

**Size.** Target is 750 lines or fewer. Exceeding it is a review finding, not a reason to add modules.

**Errors.** The Module 1 error discipline applies unchanged.

### Constants and closed codes

**Route IDs**
- `ROUTE_ID_PATTERN = r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*"`, at most 64 characters. It admits dotless spec IDs such as `pod_list` and `grafana_health`, and it is a subset of the receipts/lease safe-ID grammar.
- `UNMATCHED_ROUTE_ID = "unmatched"` is reserved and is never a catalog ID.

**Schema, revision and tag strings**
- `JIRA_POLICY_SCHEMA = "maoi.forwarder.jira-policy.v1"`.
- `JIRA_ROUTES_CODE_REVISION = "maoi.forwarder.jira-routes.v1"`. It is part of the policy digest, and any code change to route semantics must bump it (review rule).
- `SCOPE_SCHEMA = "maoi.forwarder.scope.v1"`.
- Digest tags: `POLICY_DIGEST_TAG = "maoi.forwarder.policy.v1"`, `SCOPE_DIGEST_TAG = "maoi.forwarder.scope.v1"`, `REQUEST_DIGEST_TAG = "maoi.forwarder.request.v1"` and `DENIED_DIGEST_TAG = "maoi.forwarder.request-denied.v1"`. The tags are distinct, so a denial digest never equals a request digest.

**Size and count bounds**

| Name | Value | Source |
| --- | --- | --- |
| `MAX_POLICY_BYTES` | `65_536` | sum of configured services' canonical policy bytes; spec L252-253 |
| `MAX_MANIFEST_BYTES` | `16_384` | proposed control frame, spec L238. Today's frame is 8 KiB, so delivery is deferred. |
| `MAX_REQUEST_JSON_BYTES` | `262_144` | spec L169 |
| `MAX_RESPONSE_BYTES` | `1_048_576` | spec L268-269 |
| `MAX_SCOPED_ISSUES` | `256` | spec array bound |
| `MAX_SEARCH_LABELS` | `256` | spec array bound |
| `MAX_FIELDS` | `32` | spec L268, "fixed fields <=32". The system allowlist below caps it at 9 in practice. |
| `MAX_SEARCH_TEMPLATES` | `8` | local |
| `MAX_TEMPLATE_BYTES` | `8_192` | local |
| `MAX_SEARCH_RESULTS` | `100` | spec L269 |

**`JIRA_READABLE_SYSTEM_FIELDS`** = `frozenset({"created", "issuetype", "labels", "project", "resolution", "resolutiondate", "status", "summary", "updated"})`.
- These are the **only** admitted field names. Custom fields (`customfield_*`) are rejected in this unit.
- Custom fields can be user pickers or JSM identity fields (Responders, Request participants, Approvers) or unbounded paragraph/ADF text. Their IDs are the unresolved tenant input `tenant_field_ids` (ADR 0004 L10).
- `comment`, `worklog`, `attachment`, `reporter`, `assignee`, `creator`, `watches`, `votes`, `issuelinks`, `subtasks`, `parent`, `description` and every `*` or `-` form are therefore rejected in code. These fields carry comment history, user identity, other-issue identity or unbounded ADF.

**`ROUTE_ERROR_REASONS`** is a `MappingProxyType` from code to receipt reason. It is closed, and no code maps to `None`.

| Receipt reason | Codes |
| --- | --- |
| `request_rejected` | `request_invalid`, `selector_invalid`, `query_rejected`, `body_rejected` |
| `route_denied` | `service_unavailable`, `manifest_mismatch`, `route_unknown`, `route_not_in_scope`, `selector_out_of_scope`, `selector_ambiguous`, `upstream_unbuildable` |

`upstream_unbuildable` cannot be reached by construction; see `route` step 8.

**`RESPONSE_DETAILS`** = `frozenset({"ok", "routed_unknown", "response_invalid", "status_not_allowed", "json_invalid", "schema_invalid", "scope_mismatch", "count_exceeded"})`.

**Error classes**
- **`RouteConfigError(ValueError)`**
  - `.code` is one of `policy_invalid`, `policy_too_large`, `manifest_invalid`, `manifest_too_large`, `manifest_binding_mismatch` or `digest_input_invalid`.
  - It is raised only by dataclass constructors, `parse_scope_manifest`, `require_manifest_binding` and the public helpers `encode_query_value`, `request_digest` and `denied_request_digest`.
  - It never escapes `route` or `check_response`.
- **`RoutePolicyError(ValueError)`**
  - Attributes: `code`, `route_id` (the matched catalog ID, or `UNMATCHED_ROUTE_ID`), `receipt_reason` (`ROUTE_ERROR_REASONS[code]`) and `request_digest` (the denial digest below).
  - `args == (code,)`, and no attribute holds caller data.

**Programming errors.** These are never responses to caller-controlled content.
- `TypeError` is raised for a wrong argument type: anything other than exactly `ParsedRequest`, `ScopeManifest`, `RoutedRequest`, `ParsedResponse` or `JiraVenuePolicy | None`. It is also raised for a `ParsedRequest` whose fields have the wrong types.
- `ValueError("unknown service")` is raised for a service string outside `SERVICE_PROFILES`.

### Route catalog

**Types**
- `RouteStatus` is frozen, with fields:
  - `route_id` and `service`;
  - `state`: `"enabled"`, `"partial"` or `"unavailable"`;
  - `optional: bool` and `spec_named: bool`;
  - `missing_inputs: tuple[str, ...]`, sorted and drawn from `MISSING_INPUT_CODES`.
- `ROUTE_CATALOG` is a `MappingProxyType` with exactly 25 entries.
  - `SPEC_ROUTE_IDS` holds the 24 spec-named IDs.
  - `LOCAL_ROUTE_IDS = frozenset({"anthropic.messages"})` holds the local name for the spec's unnamed `POST /v1/messages`.
  - `OPTIONAL_ROUTE_IDS = frozenset({"traces_search", "trace_get"})` (spec L304).
  - `MATCHABLE_ROUTE_IDS = frozenset({"jira.issue.get", "jira.search"})`.
- **No route has state `"enabled"` in this unit.** Both matchable routes are `"partial"`.

**Unavailable routes.** An unavailable route has no matcher and cannot be named in a manifest, so it fails closed at two points.

**`MISSING_INPUT_CODES`** (closed)

| Code | Missing input |
| --- | --- |
| `effect_identity_binding` | trusted create receipt or admitted-candidate binding that extends selectable IDs without mutating the immutable lease scope (spec L138-142, L249-250) |
| `continuation_tracking` | server-issued continuation bound to the first page's request digest and lease; one continuation at most |
| `dispatch_permit` | AuthorizeDispatch plus ticket-37 intent and native-operation binding (spec L219-243, L441-443) |
| `adf_profile` | ticket-16 node/mark/attribute allowlist with pinned native support (ticket-16 L165) |
| `report_attempt_budget` | Report accounting: 8 KiB ADF, 16 KiB request, 64 KiB per attempt (spec L262-264) |
| `tenant_field_ids` | preflight Severity/Urgency/Source field and option IDs, with attested field types for any readable custom field (ADR 0004 L10) |
| `tenant_workflow_ids` | preflight Resolve transition ID and resolution (ADR 0004 L11) |
| `membership_state` | Receiver-admitted membership and done-state label sets (ticket 14 Answer) |
| `readback_seam` | required read-back path (spec L271-275; ticket 37) |
| `response_projection` | receipt field that binds a projected client body to the upstream response digest |
| `report_history_scope` | Receiver-supplied required Report revisions, so that `INCOMPLETE` is decidable (spec L273) |
| `tenant_space_ids` | verified MAOIREF/MAOIDRAFT space IDs (ADR 0017; ticket 43) |
| `delivery_receipt_seam` | Receiver `reference_delivery`/`read_receipt` committed before bytes cross the Run boundary (ticket 43) |
| `draft_mapping` | durable Incident-to-draft mapping (ticket 43) |
| `tenant_semantics` | tenant-verified draft status and expected-version behavior (ticket 43) |
| `eyes_schemas` | ticket-12 response schemas and returned-scope predicates |
| `datasource_mapping` | pinned datasource UID and verified proxy path (spec L289-294) |
| `query_templates` | server-owned PromQL/LogQL/TraceQL and ticket-35/41 templates |
| `rehearsal_window` | scope v2 time-window binding |
| `handle_binding` | admitted handle from a prior list or search |
| `event_selector_support` | pinned-cluster `involvedObject.uid` field-selector support |
| `operation_counters` | per-Run Eyes ceilings (32 operations; ticket-35 five queries) |
| `health_route` | exact Grafana health path and schema |
| `request_envelope` | ticket-38 accounting-approved request envelope |
| `client_profile` | operator-pinned `anthropic-version` ClientProfile |
| `sse_qualification` | qualified SSE route |
| `exposure_reservation` | ticket-38 exposure reservation |

**Catalog**

| Route ID | Service | State | Missing inputs |
| --- | --- | --- | --- |
| `jira.issue.get` | jira | partial | `effect_identity_binding` (only manifest-registered issues are selectable), `tenant_field_ids` (no custom fields) |
| `jira.search` | jira | partial | `continuation_tracking` (first page only), `tenant_field_ids` |
| `jira.issue.create` | jira | unavailable | `adf_profile`, `dispatch_permit`, `effect_identity_binding`, `report_attempt_budget`, `tenant_field_ids` |
| `jira.issue.update` | jira | unavailable | `dispatch_permit`, `membership_state`, `readback_seam`, `tenant_field_ids` |
| `jira.comment.add` | jira | unavailable | `adf_profile`, `dispatch_permit`, `readback_seam`, `report_attempt_budget` |
| `jira.comments.list` | jira | unavailable | `continuation_tracking`, `report_history_scope`, `response_projection` |
| `jira.comment.get` | jira | unavailable | `effect_identity_binding`, `readback_seam`, `response_projection` |
| `jira.transition` | jira | unavailable | `dispatch_permit`, `readback_seam`, `tenant_workflow_ids` |
| `reference.read` | confluence | unavailable | `delivery_receipt_seam`, `response_projection`, `tenant_space_ids` |
| `draft.create` | confluence | unavailable | `dispatch_permit`, `draft_mapping`, `tenant_semantics`, `tenant_space_ids` |
| `draft.read` | confluence | unavailable | `delivery_receipt_seam`, `draft_mapping`, `response_projection`, `tenant_semantics` |
| `draft.update` | confluence | unavailable | `delivery_receipt_seam`, `dispatch_permit`, `draft_mapping`, `tenant_semantics` |
| `pod_list` | kubernetes | unavailable | `continuation_tracking`, `eyes_schemas`, `response_projection` |
| `pod_status` | kubernetes | unavailable | `eyes_schemas`, `handle_binding`, `response_projection` |
| `pod_events` | kubernetes | unavailable | `event_selector_support`, `eyes_schemas`, `response_projection` |
| `service_endpoints` | kubernetes | unavailable | `continuation_tracking`, `eyes_schemas`, `response_projection` |
| `metrics_instant` | grafana | unavailable | `datasource_mapping`, `eyes_schemas`, `query_templates`, `rehearsal_window` |
| `metrics_range` | grafana | unavailable | `datasource_mapping`, `eyes_schemas`, `query_templates`, `rehearsal_window` |
| `logs_range` | grafana | unavailable | `datasource_mapping`, `eyes_schemas`, `query_templates`, `rehearsal_window`, `response_projection` |
| `traces_search` (optional) | grafana | unavailable | `datasource_mapping`, `eyes_schemas`, `query_templates`, `rehearsal_window` |
| `trace_get` (optional) | grafana | unavailable | `datasource_mapping`, `eyes_schemas`, `handle_binding` |
| `eyes.run_telemetry_query` | grafana | unavailable | `eyes_schemas`, `operation_counters`, `query_templates`, `rehearsal_window` |
| `eyes.change_query` | grafana | unavailable | `eyes_schemas`, `query_templates`, `rehearsal_window` |
| `grafana_health` | grafana | unavailable | `health_route` |
| `anthropic.messages` (local ID) | anthropic | unavailable | `client_profile`, `dispatch_permit`, `exposure_reservation`, `request_envelope`, `sse_qualification` |

**`policy_readiness_facts() -> dict[str, bool]`**
- A service is `True` only when every non-optional catalog route of that service has state `"enabled"`. Every service is `False` in this unit.
- `classify_readiness` of these facts gives `mandatory_ready=False`, unavailable `("jira", "grafana", "kubernetes", "anthropic")` and degraded `("confluence",)`.
- It is not wired into `Ready()` or admission.
- Candidate judgment from Reports (ADR 0006) also needs `jira.comments.list`, which stays unavailable.

### Operator venue policy: `JiraVenuePolicy`

A frozen dataclass. Its `__post_init__` validates exact types; any violation raises `RouteConfigError("policy_invalid")`.

| Field | Rule |
| --- | --- |
| `revision` | safe ID: 1-128 characters of `[A-Za-z0-9._-]` |
| `project_id`, `issue_type_id` | `[1-9][0-9]{0,17}` |
| `project_key` | `[A-Z][A-Z0-9_]{1,9}` |
| `issue_fields` | tuple, strictly ascending and unique, each in `JIRA_READABLE_SYSTEM_FIELDS`. Must include `issuetype` and `project`. |
| `search_fields` | same grammar. Must include `issuetype`, `labels`, `project` and `status`. |
| `search_templates` | tuple of 1..8, strictly ascending and unique. Each is printable ASCII (`0x20..0x7E`), at most 8_192 bytes, contains `{label}` exactly once and only as `"{label}"` (always a quoted JQL literal), and has no other `{` or `}`. |
| `search_max_results` | exact `int` (not `bool`), 1..100 |
| `open_status_category_keys` | tuple of 1..4, strictly ascending and unique, each `[a-z][a-z0-9-]{0,31}` |

**Eager canonical form and digest.**
- `__post_init__` builds the document: all fields plus `"schema": JIRA_POLICY_SCHEMA` and `"code_revision": JIRA_ROUTES_CODE_REVISION`.
- It computes `canonical_json(document, ascii_only=True)`. More than 65_536 bytes raises `policy_too_large`; for example, eight 8_192-byte templates fail at construction.
- It caches the bytes and `tagged_digest(POLICY_DIGEST_TAG, document)` in private `field(init=False, repr=False, compare=False)` slots via `object.__setattr__`.
- `canonical_bytes()` and the `digest` property return the cached values, so they never raise. A constructed policy always has a valid digest.
- No catalog prose is in the digest.

**Why templates and status keys are operator data.**
- Ticket 14 and ADR 0006 fix only the semantics: the exact Fingerprint/cascade label, and an open Incident created within 30 minutes. The template text is therefore operator data pinned by digest.
- The installed swagger does not pin the status-category vocabulary; its examples show `in-flight` and `completed`.

**No origin.** `origin` is deliberately absent. Upstream origin and Host belong to the deferred serializer and its own service-config digest (see "Request digest", rule v2).

### Receiver scope manifest

**Types.** All are frozen dataclasses; violations raise `RouteConfigError("manifest_invalid")`.
- `ScopedIssue(issue_id: str, issue_key: str)`
- `JiraScope(issues: tuple[ScopedIssue, ...], search_labels: tuple[str, ...])`
- `ScopeManifest(service, run_id, attempt_id, rehearsal_id, revision, routes: tuple[str, ...], policy_digest, scope: JiraScope)`

**Validation**
- **`service`** is `"jira"`. No other scope type exists, so no manifest exists for any other service. See the seam, step 2.
- **The four IDs** are safe IDs.
- **`routes`** has 1..2 entries, strictly ascending, each in `MATCHABLE_ROUTE_IDS`.
- **`policy_digest`** is 64 lowercase hex.
- **`issues`**:
  - at most 256, strictly ascending by `int(issue_id)`, with unique IDs and keys;
  - `issue_id` matches `[1-9][0-9]{0,17}`;
  - `issue_key` matches `[A-Z][A-Z0-9_]{1,9}-[1-9][0-9]{0,17}`;
  - non-empty if and only if `jira.issue.get` is in `routes`.
- **`search_labels`**:
  - at most 256, strictly ascending and unique, each `[a-z0-9][a-z0-9._-]{0,127}`;
  - non-empty if and only if `jira.search` is in `routes`;
  - no quote, backslash or space (no JQL injection) and lowercase only (no case aliases).

**The label grammar is a local constraint.** Fingerprint labels (`fp-` plus lowercase hex) fit it. The cascade label value (`cascade-<value>`, ticket 14) comes from the Grafana rule label and its grammar is not settled. A label outside the grammar makes the manifest invalid, so the search route is unavailable for it. This is fail-closed and listed as a non-qualification and an open input.

**Eager canonical form and digest.**
- `__post_init__` builds `{"attempt_id", "policy_digest", "rehearsal_id", "revision", "routes": [...], "run_id", "schema": SCOPE_SCHEMA, "scope": {"issues": [{"id", "key"}...], "search_labels": [...]}, "service"}`.
- It encodes the document with `ascii_only=True`. More than 16_384 bytes raises `manifest_too_large` at construction; 256 maximum-length issues alone are 16_896 bytes.
- It caches the bytes and `tagged_digest(SCOPE_DIGEST_TAG, document)` the same way as the policy.
- `digest` is 64 lowercase hex and never raises. It passes `forwarder_leases._require_digest` and is the exact value for `register(scope_digest=...)` and `check(scope_digest=...)`.

**What the digest binds** (spec L249-250):
- allowed IDs (issues and labels);
- rehearsal (`rehearsal_id`);
- operation class (`routes`);
- manifest/recipe revision (`revision` plus `policy_digest`);
- `run_id` and `attempt_id`.

Cross-attempt reuse is refused only when `require_manifest_binding` is enforced at store installation. The digest alone does not refuse it, because `LeaseRegistry` treats `scope_digest` as opaque. A policy change invalidates every old manifest.

The rehearsal *time window* is scope v2 (Eyes). The Jira 30-minute window is enforced only by the operator template; see the non-claims.

**`parse_scope_manifest(data: bytes) -> ScopeManifest`**
1. The size check comes first (`manifest_too_large`).
2. Then `parse_json(data, max_bytes=16_384, numbers="integer", ascii_only=True)` runs; a `JSONPolicyError` is recorded and `manifest_invalid` is raised outside the handler.
3. Exact key sets are required at every level.
4. It constructs the dataclasses and requires `canonical_bytes() == data`, so it accepts canonical bytes only.

**`require_manifest_binding(manifest, *, service, run_id, attempt_id, scope_digest) -> None`**
- This is the check the deferred sentinel store runs before installing an entry. It takes plain fields so that the module does not import `forwarder_leases`.
- Wrong types raise `TypeError`.
- It raises `RouteConfigError("manifest_binding_mismatch")` unless all of these hold:
  - `manifest.service == service`;
  - `manifest.run_id == run_id`;
  - `manifest.attempt_id == attempt_id`;
  - `hmac.compare_digest(manifest.digest, scope_digest)`.

### `RoutePolicy`

**Constructor.** `RoutePolicy(*, jira: JiraVenuePolicy | None = None)`.
- A wrong type raises `TypeError`.
- It checks the total configured canonical policy bytes against `MAX_POLICY_BYTES`. That check is redundant with a single service but remains the rule for future services.

**`ParserOptions`** is a frozen dataclass with `allowed_query_keys: frozenset[str]` and `accept: str`.

**Methods.** For every `service` argument, a non-`str` raises `TypeError` and a string outside `SERVICE_PROFILES` raises `ValueError`.
- `policy_digest(service) -> str | None`:
  - `jira.digest` when Jira is configured, otherwise `None`;
  - this is the value a future `Ready(service)` reports (spec L123).
- `parser_options(service) -> ParserOptions`:
  - configured Jira gets `(frozenset({"fields"}), "application/json")`;
  - every other service, and Jira when `jira=None`, gets `(frozenset(), "application/json")`;
  - this exists only so the owner can parse and extract the sentinel. For such services the store has no entry (seam, step 2), so the owner closes without response bytes.
- `route(request, manifest) -> RoutedRequest` (below).
- `check_response(routed, response) -> ResponseVerdict` (below).

**`route` checks, in order.** The first failure raises `RoutePolicyError`.
1. **Programming checks.** `request` must be an exact `ParsedRequest` with the right field types (`service`, `method`, `path`, `accept` of type `str`; `query` a tuple of `(str, str)`; `body` of type `bytes`), and `manifest` an exact `ScopeManifest`; otherwise `TypeError`. `request.service` must be in `SERVICE_PROFILES`; otherwise `ValueError`.
2. **Service configured.** `request.service` must have a configured policy (only Jira here), else `service_unavailable`.
3. **Manifest agreement**, else `manifest_mismatch`:
   - `manifest.service == request.service`;
   - `hmac.compare_digest(manifest.policy_digest, policy.digest)`;
   - every manifest `issue_key` starts with `policy.project_key + "-"`.
4. **Accept.** `request.accept == "application/json"`, else `request_invalid`.
5. **Match.** Matching uses exact, case-sensitive ASCII; anything else is `route_unknown`.
   - `jira.issue.get` is `GET` with `request.path.split("/") == ["", "rest", "api", "3", "issue", <selector>]` and a non-empty `<selector>`.
   - `jira.search` is `POST` with `request.path == "/rest/api/3/search/jql"`.
6. **Route in scope.** `route_id in manifest.routes`, else `route_not_in_scope`.
7. **Route-specific checks** (below).
8. **Build the upstream request** from manifest and policy values only, then compute `request_digest`.
   - Inputs are validated at construction, so neither `encode_query_value` nor `request_digest` can fail here. The worst-case search body is about 8.5 KiB and the worst-case issue target is under 200 bytes.
   - Any `RouteConfigError` from those helpers is still recorded in its handler and becomes `RoutePolicyError("upstream_unbuildable")` outside it (route_denied, 403). A test monkeypatches a helper to prove the conversion.
9. **Issue.** Construct the `RoutedRequest`, add it to the instance's lock-guarded `weakref.WeakSet`, and return it.

Checks 2-5 use route ID `unmatched`. Checks 6-8 use the matched route ID.

**Leak rule.** A `JSONPolicyError` inside `route` is recorded, and `RoutePolicyError("body_rejected")` is raised after the `try` statement. **`route` raises only `RoutePolicyError`, or `TypeError`/`ValueError` from check 1.**

**Denials on non-Jira listeners.** A non-Jira request always yields `service_unavailable` with `denied_request_digest(service, "unmatched")`, whatever the manifest. Tests use this to prove fail-closed ordering; the seam never reaches it (step 2).

**`jira.issue.get`**
- **Body:** `request.body == b""`, else `request_invalid`.
- **Query:** either `()` or exactly `(("fields", ",".join(policy.issue_fields)),)`, else `query_rejected`.
  - The decoded value is compared, so a raw `,` and `%2C` are equivalent.
  - `fields=a+b` decodes to a space and is rejected.
  - An absent `fields` means the same csv.
- **Selector:** must fullmatch `[1-9][0-9]{0,17}` or `[A-Z][A-Z0-9_]{1,9}-[1-9][0-9]{0,17}`, else `selector_invalid`. This rejects `%3B`, `;`, lowercase keys and leading zeros.
- **Lookup:** an exact dict lookup by ID or key in `manifest.scope.issues`; a miss is `selector_out_of_scope`.
- **Upstream:** `UpstreamRequest("GET", "/rest/api/3/issue/" + entry.issue_id + "?fields=" + encode_query_value(csv), "application/json", None, b"")`. It always uses the manifest's numeric ID.

**`jira.search`**
- **Query:** `request.query == ()`, else `query_rejected`.
- **Body parse:**
  - `parse_json(request.body, max_bytes=262_144, numbers="integer")`. Any `JSONPolicyError`, including for an empty body, gives `body_rejected`.
  - The root must be a `dict` whose keys are a subset of `{"jql", "maxResults", "fields"}`, with `jql` required, else `body_rejected`.
  - JSON whitespace (space, tab, LF, CR) around or inside the body is accepted and yields the identical `request_digest`.
- **`jql`:** must be a `str`.
  - For each template `t`, `prefix, suffix = t.split("{label}")`. The candidate is `jql[len(prefix):len(jql) - len(suffix)]` when `jql` starts with `prefix`, ends with `suffix`, and is at least `len(prefix) + len(suffix)` long.
  - Zero `(template, manifest label)` matches gives `selector_out_of_scope`.
  - Two or more matches give `selector_ambiguous`. For example, `x "{label}" y "z"` and `x "a" y "{label}"` both render `x "a" y "z"`.
- **`maxResults`:** exact `int`, 1..`policy.search_max_results`, else `body_rejected`. Absent means `policy.search_max_results`.
- **`fields`:** absent, or a tuple of unique `str` whose set equals `set(policy.search_fields)`, else `body_rejected`.
- **Upstream:** `UpstreamRequest("POST", "/rest/api/3/search/jql", "application/json", "application/json", canonical_json({"fields": list(policy.search_fields), "jql": rendered, "maxResults": n}))`.
  - The body is always rebuilt.
  - The canonical length is checked against 262_144 after final encoding. The check cannot fail; if it ever did, the result would be `upstream_unbuildable`.

**`encode_query_value(value: str) -> str`**
- `value` must be printable ASCII, else `RouteConfigError("digest_input_invalid")`.
- `A-Z a-z 0-9 - . _ ~` pass through; every other byte becomes `%XX` in uppercase hex. Space is `%20`.

**Result types**
- `UpstreamRequest` is frozen: `method`, `target` (repr=False), `accept`, `content_type`, `body` (repr=False).
- `RouteSelection` is frozen: `issue_id`, `issue_key`, `search_label`, `max_results`.
- `RoutedRequest` is frozen with `eq=False`:
  - `route_id` and `service`;
  - `scope_digest`, equal to the cached `manifest.digest` and never taken from a caller;
  - `policy_digest` and `request_digest`;
  - `requires_permit`, which is `False`;
  - `upstream` (repr=False) and `selection` (repr=False).
- `ResponseVerdict` is frozen:
  - `route_id`;
  - `receipt_reason`, which is `"ok"` or `"response_policy_rejected"`;
  - `detail`, drawn from `RESPONSE_DETAILS`; it is diagnostic only and never stored.

### Request digest

**Signature.** `request_digest(*, service, route_id, policy_digest, scope_digest, upstream: UpstreamRequest) -> str`.

**Formula.** `tagged_digest(REQUEST_DIGEST_TAG, descriptor)` with descriptor `{"v": 1, "service", "route_id", "policy_digest", "scope_digest", "method", "target", "accept", "content_type": str | None, "body_bytes": len(body), "body_sha256": hex | None}`. For bodyless requests, `content_type` and `body_sha256` are `None`.

**Input checks.** Any failure raises `RouteConfigError("digest_input_invalid")`.
- `service` is in `SERVICE_PROFILES`.
- `route_id` matches the grammar.
- Both digests are 64 lowercase hex.
- `method` is `GET`, `POST` or `PUT`.
- `target` is printable ASCII with no space, starts with `/`, has no `#`, and is at most 2_048 bytes.
- `body` is at most 262_144 bytes.
- `GET` implies an empty body and `content_type is None`.
- `content_type is None` if and only if the body is empty.

**Excluded by design:**
- sentinel, Authorization, Host/origin, User-Agent and caller header spellings;
- raw caller path, query and body;
- `lease_id`.

The receipt carries the lease and attempt. The manifest's `run_id`/`attempt_id` enter through `scope_digest`.

**Rule v2 (origin binding).** A v1 digest binds no upstream origin, Host or service configuration, so it cannot tell two upstream sites apart.
- **No v1 request digest may ever satisfy an AuthorizeDispatch permit.** Both routes here have `requires_permit=False`.
- The serializer unit must bump `REQUEST_DIGEST_TAG` and `v` to 2 and add the service-config/origin digest.
- It must also test that every non-credential byte it emits, Host included, is a pure function of the v2 descriptor fields.

**Result.** 64 lowercase hex: exactly what `ReceiptLedger.reserve(request_digest=...)` requires (spec L204-210).

**Confidentiality.** `request_digest` is correlation and binding data, not a secret.
- Its inputs are enumerable by anyone who holds the manifest: at most 256 issues or labels, plus nonsecret digests.
- A receipt consumer must therefore treat it as revealing which manifest entry was selected.
- The spec rule that receipts exclude URLs beyond the route ID (L207-208) holds for raw URLs; it does not hold for this correlation.

**Denial digest.** `denied_request_digest(service, route_id) -> str` = `tagged_digest(DENIED_DIGEST_TAG, {"v": 1, "service": service, "route_id": route_id})`.
- `route_id` must be `UNMATCHED_ROUTE_ID` or a catalog ID of that service; otherwise `digest_input_invalid`. That error is reachable only by direct calls, because `route` check 1 guarantees a valid service.
- It is constant per `(service, route_id)`: no caller-controlled input is hashed, and the sentinel is never an input.
- `RoutePolicyError.request_digest` carries it. There is no "unparsed request" digest.

### Response policy: `check_response(routed, response) -> ResponseVerdict`

`check_response` validates or rejects; it never projects or rewrites. Wrong argument types raise `TypeError`. Every content problem yields a rejected verdict, never an exception.

1. `routed` must be an object this instance issued (WeakSet identity). A `dataclasses.replace` copy or another instance's object gives `routed_unknown`.
2. `serialize_response(response)` must succeed, else `response_invalid`.
3. **Only status 200 can be `ok`.** Every other status gives `status_not_allowed`, which becomes `response_policy_rejected` and the fixed 502 `forwarder_response_rejected`. This covers 201, 202, 204, 205 and every 4xx or 5xx.
   - The installed swagger declares no response content for the 400/401/404 responses of `getIssue` or `searchAndReconsileIssuesUsingJqlPost`, and the spec's result is "otherwise incomplete read".
   - Error bodies can name accounts or site details, so they are never forwarded.
   - The ledger still records `http_status_class` (`4xx`/`5xx`) and `response_digest` from the upstream response, so the status class is not lost.
   - The Run cannot tell not-found from an upstream error. That is a listed limitation.
   - 3xx never arrives, because the codec rejects it.
4. For status 200:
   - `parse_json(body, max_bytes=1_048_576, numbers="finite")` runs, and any `JSONPolicyError` gives `json_invalid`;
   - then the route validator runs. Shape failures give `schema_invalid`, and value failures give `scope_mismatch`.

**`jira.issue.get` validator** (installed `IssueBean`)
- **Shape:**
  - top-level keys are a subset of `{"expand", "id", "key", "self", "fields"}`, and `id`, `key` and `fields` are required;
  - `self` and `expand` are `str` if present;
  - `fields` is a `dict` whose keys are a subset of `policy.issue_fields`;
  - `fields.project` and `fields.issuetype` are `dict`s.
- **Values** (these also fail a moved or renamed issue closed):
  - `id == selection.issue_id` and `key == selection.issue_key`;
  - `fields.project.id == policy.project_id` and `fields.project.key == policy.project_key`;
  - `fields.issuetype.id == policy.issue_type_id`.

**`jira.search` validator** (installed `SearchAndReconcileResults`)
- **Top level:**
  - keys are a subset of `{"issues", "isLast", "nextPageToken", "warnings"}`;
  - `warnings`, if present, is a tuple;
  - `issues` is a required tuple; more than `selection.max_results` items gives `count_exceeded`;
  - `isLast` is a `bool` and `nextPageToken` a `str` if present.
- **Each issue:**
  - has the issue.get top-level shape;
  - has an `id` matching `[1-9][0-9]{0,17}`, unique within the page;
  - has `key` equal to `policy.project_key + "-"` followed by `[1-9][0-9]{0,17}`;
  - has `fields` keys that are a subset of `policy.search_fields`;
  - has project and type values as for issue.get;
  - has `fields.labels` as a tuple of `str` that contains `selection.search_label`;
  - has `fields.status.statusCategory.key` in `policy.open_status_category_keys`.
- **Not checked:**
  - `fields.created`: the module has no clock, and ticket 14 uses Jira's clock, so the 30-minute window is enforced only by the digest-pinned template;
  - completeness: a negative result is not proof of absence (spec L269).

**Receipt mapping.** `finalize(reservation, dispatch_state="TRANSPORT_CONFIRMED", reason=verdict.receipt_reason, upstream_response=response)`.
- `ok` sends `serialize_response(response)` byte-exact.
- `response_policy_rejected` sends the fixed 502 (receipts plan L77).
- `ok` always means status 200 for these routes. It still is not completeness or effect confirmation.

### Lease and receipt seam: the documented order for the dispatch unit

The composition tests prove this order. The source here calls none of it except `require_manifest_binding`, `parser_options`, `route` and `check_response`.

1. **Parse.** `opts = policy.parser_options(listener_service)`, then collect or parse with `allowed_query_keys=opts.allowed_query_keys, accept=opts.accept`. A failure means no lease is known and no receipt can exist (reserve requires `lease_id`/`attempt_id`), so the owner closes without response bytes (receipts plan L43-47). This includes undeclared query keys and a non-JSON Accept.
2. **Store lookup.** A trusted store (deferred) maps `(request.service, request.sentinel)` to `StoreEntry(lease_id, attempt_id, generation, manifest)`.
   - An entry is installed only after `require_manifest_binding(manifest, service=grant.service, run_id=grant.run_id, attempt_id=grant.attempt_id, scope_digest=grant.scope_digest)` succeeds, with `lease_id=grant.lease_id`, `attempt_id=grant.attempt_id` and `generation=grant.generation`.
   - **Option (a):** only Jira manifests exist, so no entry can ever be installed for a grafana, kubernetes, confluence or anthropic grant.
   - The Receiver control adapter should refuse Register for a service with no scope type (deferred control rule). Until then, such a lease can exist in `LeaseRegistry` but never has an entry.
   - An unknown entry means close without response bytes.
3. **Lease check.** `lease = registry.check(service=request.service, sentinel=request.sentinel, generation=entry.generation, scope_digest=entry.manifest.digest)`, using the stored generation, not `registry.generation`.
   - Require `lease.authorized is True` **and** `lease.lease_id == entry.lease_id`.
   - Otherwise reserve with `route_id=UNMATCHED_ROUTE_ID` and `request_digest=denied_request_digest(service, UNMATCHED_ROUTE_ID)`, then finalize `NOT_DISPATCHED` with `reason="lease_denied"`, giving a 403.
4. **Route.** `routed = policy.route(request, entry.manifest)`. On `RoutePolicyError e`: reserve with `route_id=e.route_id` and `request_digest=e.request_digest`, finalize `NOT_DISPATCHED` with `reason=e.receipt_reason`, then `local_response_for(receipt)` gives a 400 or 403.
5. **Reserve.** `reserve(lease_id=entry.lease_id, attempt_id=entry.attempt_id, service=request.service, route_id=routed.route_id, request_digest=routed.request_digest, request_bytes=..., deadline=...)`. Here `entry.attempt_id == entry.manifest.attempt_id` by step 2.
6. **Later units:**
   - an atomic final lease check with `scope_digest=routed.scope_digest`;
   - `begin_connect`, `begin_dispatch` and `receive_response`;
   - `check_response`, then `finalize` with the verdict's reason.

**Reserve inputs, named once:**
- **`request_bytes`** is the inbound wire byte count. Composition tests pass `len(raw)` for the complete buffer given to `parse_request`. The parser caps input at 2_048 + 16_384 + 262_144 bytes, which is exactly `MAX_REQUEST_BYTES`. `receive_request` does not expose its count today. The dispatch unit must add that, or document an explicit substitute (Deferred item 1).
- **`deadline`** = `min(handler_start + MAX_HANDLER_SECONDS, grant.expires_at, launch_at + LEASE_SECONDS)`, on the single clock shared by registry and ledger. Tests inject one fake clock into both.
- **Generation.** The ledger is constructed with `generation=registry.generation`, and tests assert `receipt.generation == grant.generation`.

Policy authorization is necessary, never sufficient.

### Golden vectors (synthetic; literal hex in tests; recomputed independently during this revision)

**Policy**
- Inputs:
  - `revision="policy-r1"`, `project_id="90001"`, `project_key="SYN"`, `issue_type_id="90002"`;
  - `issue_fields = search_fields = ("issuetype", "labels", "project", "status", "summary")`;
  - `search_templates=('project = 90001 AND issuetype = 90002 AND labels = "{label}" AND statusCategory != Done AND created >= -30m ORDER BY created ASC',)`;
  - `search_max_results=50`;
  - `open_status_category_keys=("syn-new", "syn-progress")`.
- Canonical bytes (546 B):

```
{"code_revision":"maoi.forwarder.jira-routes.v1","issue_fields":["issuetype","labels","project","status","summary"],"issue_type_id":"90002","open_status_category_keys":["syn-new","syn-progress"],"project_id":"90001","project_key":"SYN","revision":"policy-r1","schema":"maoi.forwarder.jira-policy.v1","search_fields":["issuetype","labels","project","status","summary"],"search_max_results":50,"search_templates":["project = 90001 AND issuetype = 90002 AND labels = \"{label}\" AND statusCategory != Done AND created >= -30m ORDER BY created ASC"]}
```

- `policy_digest` = `3013f6a10469469651028a5ea422849591fae5a8bb4a7e15b92e2b0caf99a156`.

**Manifest**
- Inputs: `run-1`, `attempt-1`, `rehearsal-1`, `scope-r1`; routes `[jira.issue.get, jira.search]`; issues `[{id: 90101, key: SYN-1}]`; labels `[fp-0123456789abcdef]`.
- Canonical bytes (361 B):

```
{"attempt_id":"attempt-1","policy_digest":"3013f6a10469469651028a5ea422849591fae5a8bb4a7e15b92e2b0caf99a156","rehearsal_id":"rehearsal-1","revision":"scope-r1","routes":["jira.issue.get","jira.search"],"run_id":"run-1","schema":"maoi.forwarder.scope.v1","scope":{"issues":[{"id":"90101","key":"SYN-1"}],"search_labels":["fp-0123456789abcdef"]},"service":"jira"}
```

- `scope_digest` = `849028ca20f4b87db84ad25974dadd560b5d06177e17afad6b6a65fb902de47c`.

**`jira.issue.get`**
- Selector `SYN-1` or `90101`, with `fields` absent, in raw-comma form, or in `%2C` form.
- Target: `/rest/api/3/issue/90101?fields=issuetype%2Clabels%2Cproject%2Cstatus%2Csummary`.
- Descriptor: 404 B.
- `request_digest` = `43d8b4787de8e9370f79c719f3dbd5463e259bce78b98cd27daa246c7042b929`.

**`jira.search`**
- Default `maxResults`, upstream body (229 B):

```
{"fields":["issuetype","labels","project","status","summary"],"jql":"project = 90001 AND issuetype = 90002 AND labels = \"fp-0123456789abcdef\" AND statusCategory != Done AND created >= -30m ORDER BY created ASC","maxResults":50}
```

- Body SHA-256: `e95499d5e38bcfa206d332410c2b91b34e92bca4f7bc541f889738f785832070`.
- `request_digest` = `d416cc8619c619fe09b16796d7b87c515503e74ce6624f3a2d75570ce9d0692e`.
- With `maxResults=10`: the body is 229 B, body SHA-256 `c657c4b3bdd53a950d4e320149062a882bd18cd4735b8dc24c88b4ea951628a2`, and `request_digest` = `9ae5873f36dda9412cff5e44f04e62581e9445141008d5dc1319991363701552`.

**Denial digests**

| Service / route ID | Digest |
| --- | --- |
| jira/`unmatched` | `4d70175f274bcfc9b1ac634035192fb5f3152f9aa2cd5a8c1baefc06f7db0703` |
| jira/`jira.issue.get` | `d25b40c66fc9a150a6337bf0aeb2f8bf783b8b2196511a76577a23a2aa0c14ae` |
| jira/`jira.search` | `e527abd1fe362e9aa4c829160caca2b2894b3fcc152db53a153e375abfa0c7fd` |
| confluence/`unmatched` | `e8781cb247a2d68303e7886341ffca985c73ac6100fdc95279956cf796fc0d39` |
| grafana/`unmatched` | `4d8832246e0e81a323e2e21602285d617a6b0592e97eb4d54308ae2f3a4c0dca` |
| kubernetes/`unmatched` | `e1993eb15d7ca65b407a4d1fc3c61e1ef63c6da4faa8e0ee1eeca67506732d2d` |
| anthropic/`unmatched` | `1d1782c3413ce7472e58ae146c850f3795a0a4ef8fd2f4457c7e1dfa589488c7` |

## Critic issues resolved (revision 2)

| # | Issue | Resolution |
| --- | --- | --- |
| 1 (high) | `from None` leaves `__context__`, which holds `.doc` or `.object` with the full input | "Error discipline": handlers only record a code, a fresh error is raised after the `try` statement, nothing is re-raised, and regex (not exceptions) detects surrogates and U+0000. An AST check forbids `raise` inside `except`. Tester C walks the full chain for every code. The Module 1 text now says `from None` is not enough. Traceback frame locals and caller-handler context are stated non-claims. |
| 2 | Non-Jira native forms cannot yield `route_unknown` under the stated order | The matrix is split: Jira listener gives `route_unknown`/`unmatched`; the other four listeners give `service_unavailable` with their `unmatched` denial digest; undeclared query keys or `text/event-stream` fail at parse (no route call, no receipt). The check order is unchanged. |
| 3 | `RouteConfigError` could escape `route()` through lazy size checks | Canonical bytes, size caps and digest are computed eagerly in `__post_init__` and cached. Helper failures inside `route` are unreachable and would become `upstream_unbuildable`. `route` raises only `RoutePolicyError` or check-1 `TypeError`/`ValueError`, proven by a property test plus a 256-issue construction failure. |
| 4 | Manifest-to-grant binding unchecked; generation branch unreachable | `require_manifest_binding` checks service, run, attempt and digest. The store holds `(lease_id, attempt_id, generation, manifest)`. `check` uses the stored generation, `reserve` uses the stored attempt (equal to the manifest's), and ledger generation equals registry generation. Composition tests cover each mismatch and `generation_mismatch`. |
| 5 | Non-Jira seam cannot be built | Option (a): no non-Jira scope type, so no store entry, so requests close without response bytes. `service_unavailable` is reachable only with `jira=None` or in unit tests. The `parser_options` text is corrected. |
| 6 | `customfield_*` breaks the privacy claim | Custom fields are rejected; only the nine system fields are allowed. `tenant_field_ids` is added to both partial routes. A test rejects `customfield_10085`. |
| 7 | 4xx/5xx pass-through rests on an undeclared shape | Every non-200 gives `status_not_allowed` and a fixed 502. The receipt keeps `http_status_class`. The ErrorCollection validator, `MAX_ERROR_BODY_BYTES` and `error_body_invalid` are removed. |
| 8 | v1 digest does not bind origin | Rule v2: the serializer bumps the tag and `v` and adds the service-config/origin digest, and no v1 digest can ever satisfy a permit. |
| 9 | `ok` pass-through exposes site origin (`self`, `avatarUrls`, `iconUrl`) | Added to "Not qualified" and to the projection deferral. |
| 10 | 30-minute window not verified on return | Stated as a non-claim: the template alone enforces it. |
| 11 | `request_bytes` and `deadline` unspecified | Named under "Reserve inputs". |
| 12 | Whitespace conflict; "enabled" ambiguity | Whitespace is accepted with an identical digest. `ENABLED_ROUTE_IDS` is renamed `MATCHABLE_ROUTE_IDS`; no route is `enabled`, and the test asserts `partial` for exactly those two. |
| 13 | Unspecified edge behaviors | Unknown service raises `ValueError`, a non-str raises `TypeError`, `RoutePolicy(jira=<wrong>)` raises `TypeError`, `parser_options("jira")` with `jira=None` returns empty options, and a `ParsedRequest` with an invalid service raises `ValueError` at check 1. |
| 14 | AST check vs `forwarder_http`; "policy documents" | Exact-name allowlists per module, with relative imports allowlisted by name. "Policy documents" is removed from the integer-mode list and deferred. |
| 15 | Confidentiality rationale inconsistent | `request_digest` is stated to be correlation data that reveals the selected manifest entry. The denial digest stays constant because no caller input is hashed. |
| 16 | Lowercase label grammar unsettled | Recorded as a local constraint, a non-qualification and an open input. |

## Judge findings resolved (carried from revision 1, updated)

| Finding | Resolution |
| --- | --- |
| comment.get/comments.list pass-through of author/visibility data | Both are unavailable (`response_projection`). The closed system-field allowlist, with no custom fields, means no comment or user-identity field can be named. |
| comments.list `INCOMPLETE` has no enforcer | Unavailable (`report_history_scope`, `continuation_tracking`). |
| Response JSON limits looser than spec | One limit set for requests and responses. Only finite decimals are allowed, and only in responses. |
| Integers-only responses vs float ADF attributes | `finite` mode, which never converts to float. |
| Route-ID grammar required a dot | Dotless IDs admitted. |
| Learned identities widen scope | None; `effect_identity_binding` deferred. |
| Code-owned JQL template | Operator policy pinned by digest. |
| ADF/mutations/receipts import | No ADF or mutation. Source does not import `forwarder_receipts`. |
| Scope omitted run/attempt/rehearsal/revision; 64 KiB scope | All are bound; 16 KiB cap; now also a grant binding check. |
| "25 spec route IDs" | 24 spec plus 1 local. |
| Prescan misreads `"\\"` | Escape state machine plus known-answer test. |
| `JSONPolicyError` masked by a `ValueError` catch | Handler order kept; now records codes and raises fresh errors. |
| Field grammar admits `comment`/`reporter` | Closed system allowlist only. |
| `manifest_invalid` from `route()` | `manifest_mismatch`; config errors never escape `route`. |
| Unparsed/denied digests without a lease | No unparsed constant; parse failure and unknown sentinel close without bytes. |
| Denied digest hashed caller path | Constant per `(service, route_id)`. |
| Policy digest covered prose | Operator fields plus the code revision only. |
| Continuations | None; `nextPageToken` bodies rejected. |
| Search on an unresolved template | `partial`; readiness False. |
| No ledger composition; "pure" module holds a WeakSet | Composition tests; module described accurately. |
| AuthorizedRequest identity | `eq=False` plus WeakSet. |
| Invented bounds | Spec bounds; local ones labeled; error bodies never forwarded. |
| statusCategory vocabulary | Operator policy. |
| Codec rejects `;charset=UTF-8` | Non-qualification; separate unit. |
| Origin and wire format | Deferred; rule v2. |

## Ownership and validation

**Implementer A** owns `forwarder_json.py` and `tests/test_forwarder_json.py`. The tests cover:
- the 72-byte known answer, the U+0001-U+001F escape table, and `/`, U+007F and U+2028 emitted literally;
- U+0000 rejection on decode and encode;
- UTF-16 key order (`"B" < "a"`; U+1F600 before U+FF5E);
- integers: ±(2^53-1) accepted, ±2^53 rejected, 17-digit and 33-character lexemes rejected, and `-0` giving 0;
- integer mode rejects `1.0`, `1e2`, `1E-2` and `-0.0`;
- finite mode: `1.5` and `1e2` become `JSONDecimal`, while `1e400`, `-1e400` and a 2^53 lexeme are rejected;
- NaN, Infinity and -Infinity rejected in both modes;
- duplicate keys (`a`/`a`, `/`/`\/`, nested);
- depth 16 accepted and 17 rejected for arrays, objects and mixed nesting, including the escaped-backslash prescan vector;
- 1 MiB of `[` gives `json_depth` with no `RecursionError`;
- arrays of 256 and 257 items;
- strings of 16_384 and 16_385 bytes built as `5_461 x "€" + "a"` (plus one more `a`), for keys and values;
- a surrogate pair gives `F0 9F 98 80`, and lone or reversed surrogates are rejected;
- invalid UTF-8 (`C0 AF`, `ED A0 80`, `F4 90 80 80`, truncated `E2 82`) and a BOM are rejected;
- syntax and whitespace rejections;
- `max_bytes` boundaries and argument types;
- `ascii_only`;
- `canonical_json` type rejections, tuple/list equivalence and a rejected cycle;
- `é` counts as 2 canonical bytes;
- a seeded fixed-point corpus;
- the tag grammar and the tagged-digest vector;
- `str(e) == code` and `args == (code,)`.

**Implementer B** owns `forwarder_routes.py` and `tests/test_forwarder_routes.py`. The tests cover:
- **golden vectors:** every one above, as literal hex, including all seven denial digests;
- **policy validation:**
  - every field rule, and excluded fields (`comment`, `reporter`, `*all`, `-description`, `description`, `customfield_10085`);
  - template placeholder, quoting and brace rules;
  - `search_max_results` values 0, 101 and `True`;
  - eight maximum-size templates fail at construction with `policy_too_large`;
  - `canonical_bytes()`/`digest` never raise on a constructed policy;
- **manifests:**
  - manifest validation;
  - 256 maximum-length issues fail at construction with `manifest_too_large`;
  - canonical-only `parse_scope_manifest`: whitespace, reordering, an escaped `a`, extra or missing keys and non-ASCII all rejected; the round trip is equal;
  - `require_manifest_binding` accepts the golden binding and rejects each field mismatch;
- **catalog:**
  - 25 entries: 24 spec plus 1 local;
  - IDs unique and matching the grammar;
  - missing inputs non-empty and drawn from the closed set;
  - state `partial` for exactly `MATCHABLE_ROUTE_IDS`, and no `enabled` route;
- **readiness:** readiness facts plus `classify_readiness`;
- **`RoutePolicy` API:** `parser_options` and `policy_digest` for every service, with `jira=None`, an unknown service and a non-str argument; `RoutePolicy` type errors;
- **happy paths and equivalences:**
  - ID vs key selector;
  - `fields` absent, raw or `%2C`;
  - body whitespace padding, member order and `\u` escapes all give the identical digest;
  - `fields` reordered, and `maxResults` omitted vs 50;
- **sensitivity:** issue, label, `maxResults`, a policy field and the manifest revision each change the digest;
- **rejection matrix:** each case asserts code, `receipt_reason`, `route_id` and denial digest; `upstream_unbuildable` via a monkeypatched helper;
- **response details:**
  - 404, 500, 204 and 201 each give `status_not_allowed`/`response_policy_rejected`;
  - an extra top-level key and an unconfigured field;
  - a `JSONDecimal` tolerated inside `fields`;
  - `1e400`, a duplicate key and depth 17;
  - project, type, id and key mismatches;
  - a missing label and a closed status-category key;
  - a count over `maxResults`, duplicate issue IDs and `isLast: "true"`;
- **types:** `repr` excludes target, body and selection; result types are frozen; every error code has a non-`None` reason.

**Tester C** owns `tests/test_forwarder_json_adversarial.py` and `tests/test_forwarder_routes_adversarial.py`.

*JSON adversarial:*
- hostile nesting, number and Unicode inputs;
- **exception-chain walk.** For every JSON error code (including `json_encoding` and `json_syntax`), invoke outside any handler with input containing a planted marker. Recursively walk `str`, `repr`, `args`, every instance attribute, `__cause__` and `__context__`, plus `.doc`, `.object` and `.args` on any chained exception. Assert that `__cause__ is None`, that `__context__ is None`, and that the marker (as str or bytes) appears nowhere.

*Routes adversarial:*
- **exception-chain walk** for every `RoutePolicyError` code (including `body_rejected` from JSON syntax and encoding failures) and every `RouteConfigError` code (including `manifest_invalid` from `parse_scope_manifest`), with the same assertions;
- **AST checks:**
  - no `ast.Raise` inside any `ast.ExceptHandler` body in either module;
  - exact-name import allowlists per module (absolute stdlib names compared as full dotted names; relative imports compared by module name at level 1; no `__import__` or `importlib`).
- **sentinel isolation:** raw-bytes composition with `parse_request` and a Basic `run:<sentinel>` header. The sentinel appears in no target, body or descriptor, and requests that differ only in sentinel give identical digests.
- **native-form matrix, split by listener:**
  - *Jira listener, query-less or `fields`-only native forms of unavailable routes*, each giving `route_unknown`/`unmatched`/jira-`unmatched` digest:
    - POST `/rest/api/3/issue`;
    - PUT and DELETE (with JSON framing) `/rest/api/3/issue/SYN-1`;
    - GET and POST `.../issue/SYN-1/comment`;
    - GET `.../comment/10001`;
    - POST `.../transitions`;
    - GET `/rest/api/3/search/jql`;
    - POST `/rest/api/3/search`.
  - *Jira listener with `jira=None`:* `service_unavailable`.
  - *Confluence, Grafana, Kubernetes and Anthropic listeners, query-less JSON forms*, each giving `service_unavailable` with that service's `unmatched` digest:
    - `/wiki/api/v2/pages/123`;
    - `/api/v1/namespaces/ns/pods`;
    - `/api/v1/namespaces/ns/events`;
    - `/apis/discovery.k8s.io/v1/namespaces/ns/endpointslices`;
    - `/api/datasources/proxy/uid/x/api/v1/query`;
    - `/loki/api/v1/query_range`;
    - `/api/search`;
    - POST `/v1/messages`.
  - *Parse failures* (`HTTPBoundaryError`, no `route` call, no receipt) for the same forms carrying `labelSelector`, `limit`, `fieldSelector`, `query`, `start`, `q`, `startAt` or `expand`, and for Anthropic with `Accept: text/event-stream`.
- **smuggling:**
  - selectors and paths: `SYN-1%3B`, `SYN-1;x`, a trailing slash, `/Issue/`;
  - `fields`: subset, superset, empty, the `+` form, and `fields` sent to search;
  - search bodies: duplicate `jql`, an escaped-equal duplicate key, `nextPageToken`, `expand`, `properties`, `reconcileIssues`, an array root, a `null` root, and `\f`/`\v`/U+00A0 used as whitespace;
  - `maxResults` values: `true`, `1.0`, `1e1`, `"50"`, 0, 101 and -1;
  - JQL: an appended ` OR project != SYN`, a trailing space, fullwidth or NFD lookalike labels, and the template-collision ambiguity.
- **seeded request property:** every generated request either raises `RoutePolicyError` with a closed reason and a 64-hex digest, or its upstream, rebuilt into raw bytes, re-parses and re-routes to the identical `request_digest`. No other exception escapes.
- **`LeaseRegistry` composition** (one shared fake clock):
  - handshake, then `register(scope_digest=manifest.digest)`, then activate;
  - `require_manifest_binding` against the grant succeeds, and the store entry holds the grant's `lease_id`, `attempt_id` and `generation`;
  - `check` with the stored generation is authorized, with a matching `lease_id`;
  - a manifest differing in exactly one of revision, label, routes, `attempt_id` or `policy_digest` gives `scope_mismatch`;
  - store installation refuses a manifest whose `run_id`, `attempt_id`, service or digest differs from the grant; in particular, a grafana grant can never be installed;
  - a stale stored generation gives `generation_mismatch`, which leads to `lease_denied`;
  - a changed policy with an old manifest gives `manifest_mismatch`;
  - a revoked or expired lease is denied even though routing succeeds.
- **`ReceiptLedger` composition** (after the receipts commit):
  - the ledger uses `generation=registry.generation`;
  - reserve inputs are `request_bytes=len(raw)` and the clipped deadline;
  - denials reserve with `e.route_id` and `e.request_digest` and give 400 or 403 via `local_response_for`;
  - `lease_denied` with the `unmatched` digest gives 403;
  - authorized reserve, then `TRANSPORT_CONFIRMED` with a synthetic `ParsedResponse`: for `ok` the client digest equals `response_digest(upstream)`; a 404 gives `response_policy_rejected`, a 502, and a receipt with `http_status_class == "4xx"`.
- **identity:** forged, replaced and foreign `RoutedRequest` objects give `routed_unknown`.
- **purity:** `socket.socket` and `time.monotonic` are monkeypatched to raise.
- **grammar compatibility:** the local safe-ID and route-ID grammars stay compatible with the lease and receipts grammars.

No real-TLS test: no transport code is added.

**Root** owns:
- this plan file;
- a new "Request route policy" section in `docs/forwarder-control.md`: what exists, the non-claims below, and the four new test files appended to the focused command;
- validation:
  1. `pytest -q tests/test_forwarder_json.py tests/test_forwarder_json_adversarial.py tests/test_forwarder_routes.py tests/test_forwarder_routes_adversarial.py`;
  2. the existing focused forwarder command, unchanged and green;
  3. full `pytest -q`;
  4. `ruff check` on changed files;
  5. `git diff --check`;
  6. the four protected dirty files' hashes unchanged, and ticket-19 C2 untouched;
  7. independent reviewers bind final file hashes;
  8. explicit-path staging and one local commit, with no push.

## Deferred

1. **Dispatch coupling:**
   - the sentinel store, installed at Register after `require_manifest_binding`;
   - the atomic final lease check coordinated with revocation;
   - ledger transitions;
   - upstream TLS connect and `receive_response`;
   - an inbound wire byte count from `receive_request` for `request_bytes`.
2. **Control-adapter rule:** refuse Register for any service without a scope type. Also manifest delivery over control: frames above 8 KiB, an install command, and the digest check against the grant.
3. **Upstream serializer:** operator origin and Host under a service-config digest, rule v2 (tag and `v` bump), managed credential, `Content-Length`/`Connection: close`, and the pure-function test.
4. **Codec tolerance** for `Content-Type` parameters such as `charset`, before any real Jira acceptance.
5. **A receipt path for requests with no resolvable lease** (a receipts extension), if wanted.
6. **Continuation tracking:** search `nextPageToken`, comments.list, Kubernetes pages.
7. **Effect and candidate identity binding.**
8. **Projection seam**, a receipt field for projected client bytes. It unlocks:
   - comments.list, comment.get, Confluence reads and Kubernetes routes;
   - `description` and custom fields;
   - removal of origin-bearing URL fields (`self`, `avatarUrls`, `iconUrl`);
   - a status-only local response that could tell the Run "not found" apart from an upstream error.
9. **Mutation routes:** ADF profile, Report budgets, AuthorizeDispatch, ticket-37 intent and read-back.
10. **Other scope and policy types:** scope v2 with the rehearsal window; Eyes, Kubernetes, Confluence and Anthropic policies; operation counters.
11. **Readiness wiring:** `Ready(service)` carrying `policy_digest`, and admission use of `policy_readiness_facts`.
12. **Venue preflight tooling:** a real `JiraVenuePolicy` (tenant IDs, status keys, templates, attested custom-field types) under separate authorization, plus operator file loading in `integer` mode.
13. **Native client compatibility** and a Skill revision.

## Not qualified by this unit

This unit does not qualify:
- lease, permit or dispatch coupling;
- upstream serialization, origin binding or credentials;
- real Jira response compatibility: content-type parameters, key sets, statusCategory vocabulary, eventual consistency;
- the returned 30-minute window, which only the template enforces;
- completeness of search results;
- error-status visibility: every non-200 is a fixed 502;
- origin privacy: `ok` responses pass through `self`, `avatarUrls` and `iconUrl` values that carry the site origin, unmodified until a projection seam exists;
- custom fields;
- cascade labels outside the local lowercase grammar;
- confidentiality of `request_digest`;
- traceback frame locals;
- native client request shapes;
- any tenant ID or template;
- readiness or admission;
- mutation, projection or continuation;
- SSE;
- any non-Jira route;
- deployment;
- any external effect.

Synthetic golden vectors prove the encoding contract, not venue behavior.