# Synthetic fixed-origin Jira upstream connector, request digest v2 and canonical upstream wire (unit 13b)

2026-09-23, revision 2 (critic pass). This is the second half of the thirteenth separately authorized local application unit under the [approval record](../native-runtime-source-implementation-approval.json). The 13a plan specifies the dispatch gate and the one-request exchange; this plan specifies its Deferred item 1.

**How this plan was made.** It synthesizes three designs (contract-first, wire-first and trust-first) and two judge panels, then one critic pass.
- The base is `contract-first`, which both panels chose.
- The judges' grafts are applied. "Judge findings resolved" maps every judge error to its resolution.
- "Critic issues resolved (revision 2)" maps all 15 critic issues. None is rejected. Two are resolved differently from the critic's suggested fix, and the table says why.

**How the numbers were checked.**
- Every golden value was recomputed during synthesis from the committed unit-12 goldens, using the committed `forwarder_json.tagged_digest` and an independent `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True)` encoder. Revision 2 changes no byte format, so every golden is unchanged. The new credential fields `service` and `profile` do not enter any document.
- The two golden upstream response bodies were checked against the committed `RoutePolicy.check_response`; both return `ok`.
- CPython 3.13.7 behavior was read from its `ssl.py` source: `SSLSocket.shutdown` sets `_sslobj = None` before shutting the fd, and `SSLSocket.send` then falls back to `socket.send` in plaintext.
- The linked library is OpenSSL 3.0.16. The CLI on PATH is `/usr/local/bin/openssl` 3.6.3; `/usr/bin/openssl` is LibreSSL.
- **Revision 2 re-checks** (read-only, 2026-09-23):
  - The committed `forwarder_tls._validate_ca_pem` checks exact `str`, then non-empty and `len <= 128 KiB`, then ASCII, then fullmatch, then the block count, and it has no duplicate check.
  - The committed `forwarder_tls._close_quietly` catches `BaseException` and nests a `try` inside a handler.
  - `forwarder_routes.py` is 1,044 lines against its 750-line target.
  - `forwarder_routes._valid_target` accepts targets up to 2,048 bytes, and neither `UpstreamRequest` nor `RoutedRequest` has a `__post_init__`.
  - Python 3.13.7's `ssl` exposes no `OP_ALLOW_UNSAFE_LEGACY_RENEGOTIATION`. `/usr/local/include/openssl/ssl.h` defines it as `SSL_OP_BIT(18)` (`0x0004_0000`). The neighboring bits `ssl` does expose (`OP_NO_COMPRESSION = 0x20000`, `OP_NO_TICKET = 0x4000`, `OP_ENABLE_MIDDLEBOX_COMPAT = 0x100000`) sit at the same positions in the linked 3.0.16. A default client context has that bit clear.
  - The untracked working-tree `forwarder_exchange.py` (515 lines, 13a in progress) was checked:
    - it defines `UpstreamError`, `UPSTREAM_ERROR_CODES` and both protocols with the signatures below;
    - E10 calls `connect(..., deadline=admission.connect_deadline)`, maps only `upstream_tls_failed` to its own reason and everything else to `connect_failed`;
    - E13 and E14 map by `code == "deadline"`;
    - E7c denies with `route_denied` on any `prepare` exception or on a digest equal to `routed.request_digest`.

**Baseline.** 13b starts only after the reviewed local commit of 13a. It consumes these names exactly as the 13a plan defines them:
- **`forwarder_dispatch`:** `Admission`, a frozen `eq=False` dataclass without slots. It is therefore identity-hashable and weak-referenceable (verified in the working tree on 2026-09-23). Its fields are `receipt_id`, `lease_id`, `service`, `route_id`, `admitted_at`, `deadline`, `exchange_deadline` and `connect_deadline`. Also `CONNECT_SECONDS = 5.0`, `WRITE_SECONDS = 10.0` and `READ_INACTIVITY_SECONDS = 20.0`.
- **`forwarder_exchange`:** `UpstreamError`, with `args == (code,)` and `.code` in `UPSTREAM_ERROR_CODES = {connect_failed, upstream_tls_failed, write_failed, receive_failed, deadline}`. Also `serve_request`, `serve_one`, and the `UpstreamConnector` and `UpstreamChannel` protocols.
- **Unit 12:**
  - `RoutedRequest` (frozen, `eq=False`) and `UpstreamRequest` (`method`, `target`, `accept`, `content_type`, `body`);
  - `request_digest`, which is v1;
  - `ROUTE_CATALOG`, `MATCHABLE_ROUTE_IDS`, `JIRA_READABLE_SYSTEM_FIELDS`, `MAX_REQUEST_JSON_BYTES`, `RouteConfigError` and `policy_readiness_facts`.
- **Units 9 and 10:** `receive_response`, `ResponseReceiveError` and `ParsedResponse`.

If the committed 13a code differs from any of these, root reconciles this plan before implementation starts.

Root reconciliation, 2026-09-23, against 13a commit `c1869a2`: the committed modules export every name above with the listed fields, flags (`Admission` frozen, `eq=False`, no slots, weak-referenceable), constants (5.0, 10.0, 20.0), `UPSTREAM_ERROR_CODES` and protocol signatures, and `serve_request` maps E10, E13 and E14 as stated.

**Protected state.**
- The four protected dirty files keep their hashes: issue 19, `planning-frontier-2026-09-18.md`, and the two ticket-19 `c2-ingestion-*` files.
- Ticket 19 C2 is out of scope.

**Out of bounds.**
- No push or deployment. No provider, tenant or native call.
- No real credential, tenant origin, CA or address.
- No DNS, proxy, environment, file or mount read in source.
- No credential loading: the approval record excludes "Credential read/change".
- No paid experiment.

**Rules.** These are carried from units 12 and 13a.
- Every existing source module and every existing test file stays byte-identical.
- In the new module, every `ExceptHandler` body contains only `Assign`, `AnnAssign`, `Pass` or `Return` statements (AST-checked). This rules out `raise`, nested `try` and calls in statement position.
  - A fresh error is raised after the `try` statement, with `from None`.
  - Nothing is re-raised.
  - Every error raised outside a caller's handler has `args == (code,)`, `__cause__ is None` and `__context__ is None`.
- Imports use an exact-name allowlist, which is AST-checked.
- Run the full suite before the one local commit. Stage by explicit path, and do not push.
- Root saves this plan as `.scratch/many-alerts-one-incident/reviews/forwarder-upstream/implementation-plan.md`.

## Why this unit

13a composes admission (L1), the write fence (L2) and the receipt-gated exchange. Its connector contract is trust-based ("Upstream contract in 13a"): 13a's fakes assert it but do not prove it. 13a Deferred item 1 assigns the real connector to this unit.

Unit 12's rule v2 requires the serializer unit to do four things:
- bump the digest tag and `v` to 2;
- bind a service-config/origin digest;
- never let a v1 digest satisfy a permit;
- test that every non-credential byte, Host included, is a pure function of the v2 descriptor.

The specification and ADRs set these requirements for the upstream side:
- a fixed origin and allowed base per listener, with a Jira-only credential (spec L38; ADR 0011 L9);
- 5 s connect, 10 s write and 20 s first-byte/read-inactivity limits, clipped to the lease (L175-176);
- the Forwarder reconstructs canonical `Host`, credential, `Content-Length`, `Accept` and `Content-Type`, and it never forwards caller credential or header values (L199-201; ADR 0002; ADR 0011 L25);
- it rejects 3xx and never exposes `Location` (L201-203);
- it never reissues a request (L212-217);
- receipts exclude credentials (L204-209);
- verification is never bypassed (ADR 0011 L11).

Spec L167-168's "single request per connection" governs the inbound listeners. The upstream `Connection: close` comes from routes Deferred item 3 (see "Wire profile").

The spec leaves the service origins and the TLS issuer unresolved: "A missing choice disables only its route" (L441-448). 13b therefore delivers a trusted operator configuration **shape** and proves every connector obligation against a synthetic local TLS upstream, while every production route stays unavailable.

## Production stays unavailable

There are four independent locks. Each has a test.

1. **No production caller** (AST and text, checked by test).
   - No Python file in the repository, other than `forwarder_upstream.py` itself and files under `tests/`, does any of these:
     - imports `forwarder_upstream`;
     - names `JiraUpstreamConnector`, `UpstreamEndpoint` or `BasicCredential`;
     - holds a string constant containing any of those four names. This catches `importlib.import_module("...forwarder_upstream")` and `getattr(module, "...")`.
   - Scope: a filesystem walk from the repository root, so untracked files count. It includes `grafana_jsm_sandbox/` (including `__main__.py` and the legacy `forwarder.py`), `prototype/`, `docker/` and `.scratch/`. It skips `tests/`, `.git/`, virtualenv directories (any directory containing `pyvenv.cfg`) and `__pycache__/`.
   - Also: no `*.toml`, `*.cfg`, `*.ini`, `*.sh`, `*.yaml`, `*.yml` or `Dockerfile*` outside `tests/`, `docs/`, `.scratch/` and `.git/` contains `forwarder_upstream`. This covers entry points and launch commands.
   - Every production `serve_request` or `serve_one` caller therefore keeps `upstream=None`, and 13a E7b returns 403 `route_denied` with digest `d25b40c6...` or `e527abd1...`.
   - The check guards against accidental wiring. It does not stop deliberately computed names such as `"forwarder_" + "upstream"` (see "Not qualified").
2. **Closed synthetic origin policy.** `ENDPOINT_POLICY = "synthetic-only.v1"` names the only acceptance predicate in source.
   - The host's last label must be exactly `invalid` (RFC 6761).
   - The address must lie in an RFC 5737 documentation network.
   - Anything else raises `endpoint_unqualified`. No branch accepts any other origin.
   - The policy string is bound into the endpoint digest, so every v2 digest records the gate it was made under.
   - Widening it requires a separately reviewed unit that records the origin and issuer decisions and defines a new policy value.
3. **No loader.** There is no configuration or credential loader. `UpstreamEndpoint` and `BasicCredential` are filled only in memory, by tests, with synthetic values.
4. **Catalog unchanged.** `ROUTE_CATALOG` keeps both Jira routes `partial`, and `policy_readiness_facts()` stays all `False`. Both are asserted.

**What the gate is not.** RFC 5737 addresses are reserved for documentation, but they are not guaranteed to be unroutable on every local network. The gate is therefore not a network control. The real guarantee against a stray connection is the asserting test adapter plus lock 1. The gate is a fail-closed source rule, not a boundary against in-process code.

## Module: `grafana_jsm_sandbox/forwarder_upstream.py`

This module is the trusted `UpstreamConnector` for `jira.issue.get` and `jira.search`.
- It validates an operator endpoint shape and adopts one redacted Basic credential bound to `jira`/`basic`.
- It computes the endpoint digest and the rule-v2 request digest as pure functions, and it renders the credential-free parts of the canonical request as a pure function. A successful `prepare` implies a successful render.
- It opens one fresh, strictly verified TLS connection per request to an operator-pinned IPv4 literal. There is no DNS, and connect writes zero application bytes.
- The channel writes the request exactly once, after the 13a fence. It reads only through `receive_response`, and it aborts and closes thread-safely.
- It never retries, never follows or exposes a redirect, never logs, and holds no lock across I/O.
- **Target: about 950 lines.**
  - The module carries nine ordered endpoint rules with PEM, DER and context probing; a credential class with about ten refusal dunders; the descriptor, the render and the context builder; an eight-step connect; and a locked channel state machine with deferred close. The committed precedent is `forwarder_routes.py`: 1,044 lines against a 750-line target.
  - Exceeding the target triggers review, not a split. The unit stays one module.

### Imports (AST-checked by exact name)

- **stdlib:** `__future__` (`annotations`), `base64`, `hashlib`, `hmac`, `ipaddress`, `math`, `re`, `socket`, `ssl`, `threading`, `time`, `weakref`, `dataclasses` (`dataclass`, `field`), `types` (`MappingProxyType`).
- **relative:**
  - `.forwarder_dispatch` (`Admission`, `CONNECT_SECONDS`, `WRITE_SECONDS`);
  - `.forwarder_exchange` (`UpstreamError`);
  - `.forwarder_http_response` (`ParsedResponse`);
  - `.forwarder_json` (`tagged_digest`);
  - `.forwarder_response_receive` (`ResponseReceiveError`, `receive_response`);
  - `.forwarder_routes` (`JIRA_READABLE_SYSTEM_FIELDS`, `MAX_REQUEST_JSON_BYTES`, `ROUTE_CATALOG`, `RouteConfigError`, `RoutedRequest`, `UpstreamRequest`, and `request_digest` imported as `_v1_request_digest`).
- `receive_response`, `ROUTE_CATALOG`, `_PEM_BUNDLE`, `_CHANNEL_SOCKET_TYPE` and `_shutdown_fd` are read from module globals at call time, so tests can monkeypatch them.

**Forbidden anywhere in the module** (AST):
- **modules and builtins:** `os`, `pathlib`, `subprocess`, `importlib`, `__import__`, `open`, `environ`, `getenv`, `eval`, `exec`, `print`, `logging`, `pickle`, `copyreg`, `json`, `urllib`, `http`, `select`, `forwarder_tls`;
- **resolvers:** `getaddrinfo`, `gethostbyname`, `gethostbyname_ex`, `gethostbyaddr`, `getfqdn`, `getnameinfo`, `create_connection`;
- **TLS weakening:** `create_default_context`, `_create_unverified_context`, `load_default_certs`, `set_default_verify_paths`, `load_cert_chain`, `sni_callback`, `set_servername_callback`, `cafile`, `capath`, `CERT_NONE`, `CERT_OPTIONAL`, `VERIFY_X509_PARTIAL_CHAIN`, `OP_IGNORE_UNEXPECTED_EOF` (outside the one read-back assertion), `OP_LEGACY_SERVER_CONNECT` (likewise);
- **stores:**
  - no `Store` to `keylog_filename`;
  - the only assignments to `check_hostname`, `verify_mode`, `hostname_checks_common_name`, `minimum_version`, `verify_flags` and `options` are the exact ones in "TLS context".

### Constants

| Name | Value | Source |
| --- | --- | --- |
| `ENDPOINT_SCHEMA` | `"maoi.forwarder.upstream-endpoint.v1"` | also the endpoint digest tag |
| `ENDPOINT_POLICY` | `"synthetic-only.v1"` | closed origin gate (spec L441-448); bound into the endpoint digest |
| `REQUEST_DIGEST_V2_TAG` | `"maoi.forwarder.request.v2"` | routes rule v2; distinct from unit 12's `maoi.forwarder.request.v1`, which is untouched |
| `TLS_PROFILE` | `"maoi.forwarder.upstream-tls.v1"` | bound into the endpoint digest |
| `WIRE_PROFILE` | `"maoi.forwarder.upstream-wire.v1"` | bound into the endpoint digest; any byte-level wire change needs a new value |
| `UPSTREAM_BASE_PATH` | `"/rest/api/3/"` | spec L38 allowed base; bound into the endpoint digest |
| `CREDENTIAL_PROFILES` | `MappingProxyType({"jira": "basic"})` | spec L38; ADR 0011 L9 |
| `DISPATCHABLE_SHAPES` | `MappingProxyType` of two `RequestShape` values (below) | equals `MATCHABLE_ROUTE_IDS` |
| `SYNTHETIC_NETWORKS` | `IPv4Network` 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24 | RFC 5737 |
| `DENIED_NETWORKS` | `IPv4Network` 0.0.0.0/8, 127.0.0.0/8, 169.254.0.0/16, 224.0.0.0/4, 240.0.0.0/4 | the 13a sketch categories: unspecified or this network, loopback, link-local (including 169.254.169.254 metadata), multicast, reserved and broadcast |
| `MAX_TRUST_PEM_BYTES` | `131_072` | equals `forwarder_tls._MAX_CA_PEM_BYTES` (parity test) |
| `MAX_TRUST_CERTIFICATES` | `16` | equals `forwarder_tls._MAX_CA_CERTIFICATES` (parity test) |
| `MAX_REQUEST_LINE_BYTES` | `2_048` | spec L168-169, applied outbound |
| `MAX_REQUEST_HEAD_BYTES` | `16_384` | spec L168, applied outbound |
| `MAX_REQUEST_BODY_BYTES` | `262_144` | equals `MAX_REQUEST_JSON_BYTES` |
| `MAX_WRITE_CHUNK_BYTES` | `16_384` | equals `forwarder_response_send._MAX_CHUNK_BYTES` |
| `MAX_AUTHORIZATION_BYTES` | `2_048` | local bound on the Authorization value |
| `CHANNEL_STATES` | `("open", "sending", "sent", "receiving", "received", "failed", "aborted", "closed")` | |

**Private constants:**
- `_OP_ALLOW_UNSAFE_LEGACY_RENEGOTIATION = 0x0004_0000`. This is OpenSSL's `SSL_OP_BIT(18)`, which Python 3.13 does not expose. It is used only in a read-back assertion, and a test pins it.
- `_CHANNEL_SOCKET_TYPE = ssl.SSLSocket` (see the channel constructor).
- `_CHANNEL_TOKEN = object()`.
- `_CLAIM_LOCK = threading.Lock()`.

`RequestShape(method: str, target_pattern: str, content_type: str | None)` is a frozen dataclass. `DISPATCHABLE_SHAPES` has exactly two entries:
- `"jira.issue.get"`: `RequestShape("GET", r"/rest/api/3/issue/[1-9][0-9]{0,17}\?fields=[a-z]+(?:%2C[a-z]+)*", None)`;
- `"jira.search"`: `RequestShape("POST", r"/rest/api/3/search/jql", "application/json")`.

### Closed codes and errors

- `UPSTREAM_CONFIG_CODES = frozenset({"endpoint_invalid", "trust_invalid", "endpoint_unqualified", "credential_invalid", "credential_mismatch", "credential_claimed"})`.
- `UPSTREAM_PREPARE_CODES = frozenset({"shape_unavailable", "request_inconsistent", "request_unbuildable"})`.
- `UpstreamConfigError(ValueError)` and `UpstreamPrepareError(ValueError)` each carry only `.code`, with `args == (code,)` and `str(e) == code`. No configured value, credential, target or body ever appears in an error.
- **Transport:** only `forwarder_exchange.UpstreamError(code)`.
  - `connect` raises only `connect_failed`, `upstream_tls_failed` or `deadline`.
  - `send` raises only `write_failed` or `deadline`.
  - `receive` raises only `receive_failed` or `deadline`.
  - `abort` and `close` never raise an `Exception`.
- **`TypeError`** is raised only for wrong exact types passed to `JiraUpstreamConnector(...)`, `request_descriptor`, `render_parts` and the private channel constructor. Configuration objects report their own wrong-type fields with their own codes, following the routes-plan precedent.

### Types and signatures

**`@dataclass(frozen=True, kw_only=True) class UpstreamEndpoint`.**
- Fields: `service: str`, `revision: str`, `host: str`, `address: str`, `port: int`, `ca_pem: str = field(repr=False)`, `credential_id: str`. These are exactly the fields of the 13a sketch.
- `__post_init__` validates in the order given under "Endpoint shape". It then eagerly caches the trust digests, document, canonical bytes and digest in `field(init=False, repr=False, compare=False)` slots, so no accessor ever raises.
- Accessors:
  - `trust_sha256 -> tuple[str, ...]`;
  - `authority -> str`: `host` when `port == 443`, else `f"{host}:{port}"`;
  - `digest -> str`;
  - `document() -> dict`, a fresh copy;
  - `canonical_bytes() -> bytes`.
- `dataclasses.replace` revalidates.

**`endpoint_document(*, service, revision, host, address, port, trust_sha256: tuple[str, ...], credential_id) -> dict`.**
- It is pure.
- It runs the same field checks as the endpoint. It requires `trust_sha256` to be 1..16 unique, strictly ascending, 64-lowercase-hex strings (else `trust_invalid`). It then applies the synthetic gate.
- `UpstreamEndpoint` calls it, so the two cannot disagree. Tests use it for goldens without a CA.

**`class BasicCredential`.**
- `__init__(self, *, service: str, profile: str, credential_id: str, user: str, token: str) -> None`. The public properties are `service`, `profile` and `credential_id`; none is secret.
- `__slots__ = ("_service", "_profile", "_credential_id", "_authorization", "_claimed")`, so it has no `__dict__`.
- `__setattr__` and `__delattr__` raise `AttributeError` after construction. Internal writes use `object.__setattr__` with string slot names.
- `__init_subclass__` raises `TypeError`.
- Equality and hash are by identity (inherited from `object`).
- `__repr__`, `__str__` and `format` return `"BasicCredential(service='jira', profile='basic', credential_id='<id>', <redacted>)"`.
- `__reduce__`, `__reduce_ex__`, `__getstate__`, `__copy__` and `__deepcopy__` raise `TypeError("credential_not_copyable")`.

**`@dataclass(frozen=True) class UpstreamDescriptor`.**
- Fields: `service`, `route_id`, `policy_digest`, `scope_digest`, `endpoint_digest`, `method`, `target = field(repr=False)`, `authority`, `accept`, `content_type: str | None`, `body_bytes: int`, `body_sha256: str | None`, `body: bytes = field(repr=False)`.
- `__post_init__` checks grammar, consistency and the wire bounds, else `UpstreamPrepareError("request_unbuildable")`:
  - `service` is in `CREDENTIAL_PROFILES`, and `route_id` is in `DISPATCHABLE_SHAPES`;
  - the three digests are 64 lowercase hex;
  - `target` is printable ASCII starting with `/`, with no space, `#`, CR or LF;
  - `authority` fullmatches the authority grammar (see "Request digest rule v2", step 5);
  - `accept` and `content_type` are printable ASCII with no space, CR or LF;
  - `len(body) == body_bytes`; `body_sha256` equals `sha256(body)`, or is `None` exactly when the body is empty;
  - `content_type is None` exactly when the body is empty;
  - **the three wire bounds** from `_wire_lengths(method, target, authority, accept, content_type, body_bytes)`, a pure length function shared with `render_parts` (see "Wire profile"). Every constructed descriptor therefore renders.
- `document() -> dict` returns the v2 document, which excludes `body`. `digest -> str` is cached.

**`request_descriptor(routed: RoutedRequest, *, endpoint_digest: str, authority: str) -> UpstreamDescriptor`.** Pure; see "Request digest rule v2". It is the whole of `prepare`'s logic.

**`@dataclass(frozen=True) class RequestParts(prefix: bytes = field(repr=False), suffix: bytes = field(repr=False))`.** The complete wire is `prefix + b"Authorization: " + <credential value> + b"\r\n" + suffix`, assembled only inside the channel's `send`.

**`render_parts(descriptor: UpstreamDescriptor) -> RequestParts`.** Pure and credential-free; see "Wire profile". For any `UpstreamDescriptor` it cannot fail on bounds. It asserts that its rendered lengths equal `_wire_lengths`, and a mismatch raises `request_unbuildable` as a local fault.

**`class JiraUpstreamConnector`.**
- `__slots__ = ("_endpoint", "_credential", "_lock", "_connected")`, where `_connected` is a `weakref.WeakSet` of `Admission`.
- `__init__(self, *, endpoint: UpstreamEndpoint, credential: BasicCredential) -> None`:
  1. exact types, else `TypeError`;
  2. `credential.service == endpoint.service`, `credential.profile == CREDENTIAL_PROFILES[endpoint.service]`, and `hmac.compare_digest(endpoint.credential_id, credential.credential_id)`, else `credential_mismatch`. Both IDs are validated ASCII, so `compare_digest` cannot raise;
  3. last, under `_CLAIM_LOCK`: if the credential is already claimed, raise `credential_claimed`; otherwise set `_claimed`. A refused construction therefore claims nothing, and one credential serves one connector for its lifetime.
- Properties: `service -> "jira"` and `endpoint_digest -> str`.
- `prepare(self, routed: RoutedRequest) -> str`, returning 64 lowercase hex.
- `connect(self, admission: Admission, routed: RoutedRequest, *, request_digest: str, deadline: float) -> _UpstreamChannel`.
- `repr` shows only `service` and `endpoint_digest`. Pickling and copying raise `TypeError`, and subclassing is refused.

**`class _UpstreamChannel`** (private; constructed only by `connect`).
- The constructor is `__init__(self, token, *, sock, parts, credential, exchange_deadline)`. It raises `TypeError` unless all of these hold:
  - `token is _CHANNEL_TOKEN`;
  - `type(sock) is _CHANNEL_SOCKET_TYPE`;
  - `type(parts) is RequestParts`;
  - `type(credential) is BasicCredential`;
  - `exchange_deadline` is an exact finite `int` or `float`, not `bool`.
- `_CHANNEL_SOCKET_TYPE` is `ssl.SSLSocket` and is read at call time. **The one documented white-box path:** unit tests monkeypatch it to `FakeTLSSocket` and pass the token deliberately. Production code never reassigns it (AST: no `Store` to it outside its definition).
- Methods: `send(self, *, deadline: float) -> None`, `receive(self, *, deadline: float) -> ParsedResponse`, `abort(self) -> None` and `close(self) -> None`.
- Properties:
  - `state -> str`: `closed` if closed, else `aborted` if aborted, else the phase;
  - `bytes_accepted -> int`: the progress count, recorded for a future PARTIAL. 13b never reports it.
- `__slots__`, a redacted `repr` showing `state` only, and pickling and copying refused.

`__all__` lists exactly the public names above: the constants, the two error classes, `RequestShape`, `UpstreamEndpoint`, `endpoint_document`, `BasicCredential`, `UpstreamDescriptor`, `request_descriptor`, `RequestParts`, `render_parts` and `JiraUpstreamConnector`.

## Trust rules

### Trusted inputs

- The connector is trusted code.
- `UpstreamEndpoint` and `BasicCredential` are trusted operator configuration. In 13b only tests construct them.
- `RoutedRequest` is trusted because `RoutePolicy.route` issued it from manifest and policy values. The connector still re-verifies its shape, its bounds and its v1 consistency.
- `Admission` is trusted because `DispatchGate.admit` issued it.
- Caller bytes reach the connector only through `routed.upstream`. The sentinel, caller `Host`, `Authorization`, `User-Agent`, header spellings, raw path, query and body never do.
- Upstream bytes are untrusted. Only the committed codec collects them, and 13a E14 and E15 judge them.

### Endpoint shape

`UpstreamEndpoint.__post_init__` checks these in order; the first failure raises `UpstreamConfigError`.
1. **Types.** `service`, `revision`, `host`, `address`, `ca_pem` and `credential_id` are exact `str`, and `port` is an exact `int` (not `bool`). Else `endpoint_invalid`.
2. **Service.** `service` is in `CREDENTIAL_PROFILES`, which holds only `jira`. Else `endpoint_invalid`.
   - The Confluence, Grafana, Kubernetes and Anthropic profiles do not exist.
   - ADR 0011 L9 keeps Jira and Confluence configuration separate even on one site.
3. **IDs.** `revision` and `credential_id` fullmatch `[A-Za-z0-9._-]{1,128}`, else `endpoint_invalid`. The grammar excludes `@`, so a `credential_id` cannot carry an email address.
4. **Host.**
   - It must fullmatch `(?=.{4,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?`. That means lowercase LDH, ASCII only, at least two labels and no trailing dot. The final label starts with a letter, so the host is never an IP literal.
   - It must not be `localhost`, end in `.localhost`, or end in `.local`. The last rule covers the Forwarder's own `*.maoi.local` listener names (spec L46-47).
   - Else `endpoint_invalid`.
5. **Address.**
   - It must fullmatch the canonical dotted quad `((25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])`, and `str(ipaddress.IPv4Address(address)) == address` must hold. The parse runs inside `try`, and a `ValueError` is recorded.
   - This rejects leading zeros, `127.1`, hex, integer and IPv4-mapped forms, whitespace, ports, brackets and every IPv6 form. IPv6 remains an unresolved choice.
   - It must not lie in `DENIED_NETWORKS`. As a second check, `is_loopback`, `is_link_local`, `is_multicast`, `is_reserved` and `is_unspecified` must all be `False`.
   - Else `endpoint_invalid`.
   - The shape does not permanently deny private and shared ranges. They fall to the gate in step 8, because future cluster origins are undecided.
6. **Port.** `1 <= port <= 65535`, else `endpoint_invalid`. The port is operator-supplied, as in the sketch.
7. **Trust bundle** (`trust_invalid` on any failure). The checks run in this order, so the regex never scans an unbounded string:
   1. `ca_pem` is non-empty and `len(ca_pem) <= MAX_TRUST_PEM_BYTES`. The exact `str` type was checked in step 1.
   2. It fullmatches `_PEM_BUNDLE`, a pattern whose source string is byte-identical to `forwarder_tls._PEM_BUNDLE.pattern`. The pattern is ASCII-only, so non-ASCII input fails without an encode.
   3. It holds 1..`MAX_TRUST_CERTIFICATES` certificate blocks.
   4. Each block converts with `ssl.PEM_cert_to_DER_cert`. `trust_sha256` is the sorted tuple of the per-block DER SHA-256 hex digests, and the digests must be unique.
   5. `_build_context(ca_pem, trust_sha256)` (see "TLS context") must succeed. That proves the bundle loads, every certificate is a CA, and exactly these anchors are loaded.

   **Deliberate differences from `forwarder_tls`:** it accepts a duplicated block (OpenSSL ignores it), while this module rejects it; the per-DER digest and anchor read-back checks exist only here.
8. **Synthetic gate** (`ENDPOINT_POLICY`). `host.endswith(".invalid")`, and the address lies in `SYNTHETIC_NETWORKS`, else `endpoint_unqualified`. It runs last, so shape errors stay distinguishable. Examples that reach it: `jira.example.com`, `10.0.0.5`, `100.64.0.1`, `192.168.1.1`, `8.8.8.8`, `198.18.0.1` and `192.0.0.8`.
9. **Cache.** Cache the document, canonical bytes and digest.

The endpoint has no base-path field: `UPSTREAM_BASE_PATH` is a code constant bound into the digest.

### TLS context

`_build_context(ca_pem, trust_sha256) -> ssl.SSLContext` is the module's only `ssl.SSLContext(...)` call site (AST-checked). Endpoint validation calls it once as a probe. `connect` calls it again on every call, so every connect gets a fresh context with no shared session cache and no cross-lease resumption.

The settings, in order:
- `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)`;
- `minimum_version = ssl.TLSVersion.TLSv1_2`, `verify_mode = ssl.CERT_REQUIRED`, `check_hostname = True` and `hostname_checks_common_name = False`;
- `verify_flags = ssl.VERIFY_X509_STRICT | ssl.VERIFY_X509_TRUSTED_FIRST`, exactly. There is no partial chain and no CRL flag, so every chain must end at a self-signed anchor in the bundle;
- `options |= ssl.OP_NO_COMPRESSION | ssl.OP_NO_RENEGOTIATION | ssl.OP_NO_TICKET`;
- `set_alpn_protocols(["http/1.1"])`;
- `load_verify_locations(cadata=ca_pem)`, with exactly the one keyword `cadata`. This is the only trust source.

**Runtime read-back after construction.** Any failure is a local fault: `trust_invalid` during endpoint validation, `connect_failed` in `connect`.
- `ssl.HAS_SNI` and `ssl.HAS_ALPN`;
- `protocol == ssl.PROTOCOL_TLS_CLIENT`, `verify_mode == ssl.CERT_REQUIRED`, `check_hostname is True` and `hostname_checks_common_name is False`;
- `minimum_version == ssl.TLSVersion.TLSv1_2`, and `maximum_version` in `{MAXIMUM_SUPPORTED, TLSv1_2, TLSv1_3}`;
- `verify_flags` equals the exact value above;
- `options` contains `OP_NO_COMPRESSION`, `OP_NO_RENEGOTIATION` and `OP_NO_TICKET`, and contains none of `OP_IGNORE_UNEXPECTED_EOF`, `OP_LEGACY_SERVER_CONNECT` or `_OP_ALLOW_UNSAFE_LEGACY_RENEGOTIATION`;
- `cert_store_stats()` gives `x509 == x509_ca == len(trust_sha256)`;
- the sorted SHA-256 of `get_ca_certs(binary_form=True)` equals `trust_sha256`;
- `keylog_filename is None`;
- `post_handshake_auth is False`.

Source never consults system roots, `SSL_CERT_FILE`, `SSL_CERT_DIR` or `SSLKEYLOGFILE`. The plain constructor does not read them, and every default-trust API is AST-banned.

**Process-level OpenSSL configuration** is outside source control. `OPENSSL_CONF` or the default `openssl.cnf` `system_default` section is read by the library at init and can change defaults for every new `SSL_CTX`. The read-back above catches changes to trust, verification, versions and the listed options. It does not cover cipher suites, groups or signature algorithms; see "Not qualified".

**Handshake.** `wrap_socket(raw, server_hostname=endpoint.host, do_handshake_on_connect=False)` is followed by exactly one `do_handshake()`. `endpoint.host` provides both SNI and OpenSSL's RFC 6125 hostname verification. The `Host` header uses `endpoint.authority`.

**Post-handshake checks.** Any failure gives `upstream_tls_failed`.
- `version()` is in `{"TLSv1.2", "TLSv1.3"}`;
- `selected_alpn_protocol()` is in `{None, "http/1.1"}`, matching unit 10's claim check;
- `compression() is None`;
- `session_reused is False`;
- `getpeercert(binary_form=True)` is non-empty `bytes`.

**How the upstream policy differs from the inbound listener.**
- It does not apply `forwarder_tls`'s exact-two-SAN, 24-hour leaf rule, because hosted origins present wildcard, multi-SAN, long-lived certificates.
- The trust anchors are the pinned bundle, `VERIFY_X509_STRICT`, OpenSSL's default server-purpose (EKU) check, and hostname verification with the common-name fallback disabled.
- A wildcard leaf is accepted, because the Python API cannot disable wildcard matching. This is documented and tested.
- The issuer choice stays unresolved (spec L445).

### Credential custody

**Validation** (spec L37-38; L25-27, a Run never receives an upstream credential; ADR 0002; ADR 0011 L15).
- All checks run first, on the parameters themselves, before any encode or derived value exists. Each check result is reduced to a `bool` immediately. A `re.Match` object, which references its input string, is never bound to a name.
  1. All five arguments are exact `str`. A `str` subclass is refused before any of its methods runs.
  2. `service` is in `CREDENTIAL_PROFILES`, and `profile == CREDENTIAL_PROFILES[service]`.
  3. `credential_id` fullmatches the safe-ID grammar.
  4. `user` fullmatches `[\x21-\x39\x3b-\x7e]{1,256}`: printable ASCII with no `:` (the RFC 7617 user-id).
  5. `token` fullmatches `[\x21-\x7e]{1,1024}`.
  6. **Arithmetic bound:** `6 + 4 * ((len(user) + 1 + len(token) + 2) // 3) <= MAX_AUTHORIZATION_BYTES`. At most 1,714 is possible, so this check cannot fail on the failure path, and it is computed without building the value.
- On any failure, `__init__` executes `del user, token` and then raises `credential_invalid` at its single raise site, outside any handler, with no value in the error. The raised traceback's `__init__` frame therefore holds only `self`, which has no slot set, the non-secret `service`, `profile` and `credential_id`, and the code.
- Only after every check passes, `__init__` sets `_authorization` directly from the expression `b"Basic " + base64.b64encode((user + ":" + token).encode("ascii"))` (standard alphabet, padded). It never binds the joined string or the value to a name, then deletes `user` and `token`.
- The `user` and `token` strings are not retained. The user may be an email address, which is personal identity (spec L427-429), so it appears in no repr, digest, receipt or diagnostic.

**Where the secret lives.**
- Only `credential_id` and `credential_profile: "basic"` enter the endpoint digest. The secret, the user and the header value never enter any digest, descriptor, parts, receipt, snapshot, exception or repr.
- The `_authorization` attribute is loaded in exactly two places, both in `_UpstreamChannel.send` (AST-checked):
  - as the right-hand side of the one slice assignment into the wire buffer;
  - as the argument of the one `len()` that sizes it.

  It is never assigned to a name and never passed to any other call.
- `send` assembles the wire into a preallocated `bytearray` of exact length by slice assignment of the prefix, `b"Authorization: "`, the slot value, `b"\r\n"` and the suffix. No intermediate `bytes` containing the value exists.
- `send`'s `finally` does all of the following before any error is raised:
  - releases every memoryview and sets `chunk = None`;
  - overwrites the buffer with zeros in place;
  - sets its local `credential = None`;
  - has `_finish_io` set the channel's `_credential` to `None` under the lock.

  `abort` and `close` also drop the channel's reference.

**Non-claims.**
- The header value lives in the credential's slot for the connector's lifetime. The caller's `user` and `token` strings live as long as the caller keeps them, and a caller's own frame holds them. A future loader's custody of what it reads is Deferred item 3.
- OpenSSL record buffers and freed memory may hold copies.
- Python cannot zero memory, and in-process code with object access can read the slot.
- Redaction defends against accidental disclosure through repr, str, format, pickle, copy, exceptions, snapshots, and the traceback frame locals of this module's frames. It does not defend against in-process adversaries.
- The Run never executes in the sidecar process.
- These are deferred: custody by sidecar UID 10002 with a mode-0400 mount, rotation, and readiness that requires readability only by the Forwarder (spec L402-404).

### Caller isolation and credential replacement

- Every emitted byte other than the single `Authorization` value is a pure function of the v2 descriptor. The `Authorization` value is the managed credential.
- These can never reach the upstream wire: the caller `Host` (`forwarder-jira.maoi.local:17441`), `Authorization`, `User-Agent` and `Proxy-*` headers, and the sentinel. Tests check the sentinel in raw form, as `run:<sentinel>`, and in base64.
- The connector has no response-header parsing and no redirect or retry path. The codec rejects every 1xx and 3xx status and discards all headers, including `Location` (spec L201-203; ADR 0011 L25).

## Byte formats and request digest rule v2

### Endpoint document and digest

The document:

```
{"address", "base_path": "/rest/api/3/", "credential_id", "credential_profile": "basic",
 "endpoint_policy": "synthetic-only.v1", "host", "port", "revision",
 "schema": "maoi.forwarder.upstream-endpoint.v1", "service",
 "tls_profile": "maoi.forwarder.upstream-tls.v1", "trust_sha256": [sorted DER sha256 hex],
 "wire_profile": "maoi.forwarder.upstream-wire.v1"}
```

The digest is `endpoint.digest = tagged_digest(ENDPOINT_SCHEMA, document)`.
- It binds the origin host, pinned address, port, base path, exact trust anchors, credential identity and profile, gate policy, and the TLS and wire profiles.
- Any change to any of them changes every v2 digest.
- DER fingerprints make the digest insensitive to cosmetic PEM re-encoding: CRLF line endings, block order and a trailing newline.

### Request digest rule v2

`request_descriptor(routed, *, endpoint_digest, authority)` is pure: no clock, socket, `ssl`, credential or I/O. It reads the module global `ROUTE_CATALOG`. It checks, in this order, short-circuiting:
1. `type(routed) is RoutedRequest` and `type(routed.upstream) is UpstreamRequest`, else `TypeError`.
2. **Availability**, else `shape_unavailable`, in this order:
   1. `routed.service == "jira"`;
   2. `routed.route_id in DISPATCHABLE_SHAPES`;
   3. `entry = ROUTE_CATALOG.get(routed.route_id)`, inside `try`. An exception, a missing entry, or an entry whose `state` is not in `{"partial", "enabled"}` counts as unavailable. There is never a `KeyError`;
   4. `routed.requires_permit is False`.
3. **Shape**, else `shape_unavailable`:
   - the method and `content_type` equal the shape's;
   - `accept == "application/json"`;
   - the target fullmatches `target_pattern` and starts with `UPSTREAM_BASE_PATH`;
   - for `jira.issue.get`, the body is `b""`, and every `%2C`-separated field name is in `JIRA_READABLE_SYSTEM_FIELDS`;
   - for `jira.search`, `1 <= len(body) <= MAX_REQUEST_JSON_BYTES`;
   - JQL, label and selection semantics stay with `RoutePolicy`. The connector does not re-parse the search body.
4. **v1 consistency.**
   - `routed.request_digest` must be 64 lowercase hex. This is checked before `compare_digest`, which raises `TypeError` on non-ASCII input.
   - `_v1_request_digest(service=..., route_id=..., policy_digest=..., scope_digest=..., upstream=routed.upstream)` is recomputed; a `RouteConfigError` is recorded.
   - The result must `compare_digest`-equal `routed.request_digest`, else `request_inconsistent`. This refuses a `replace()`d `RoutedRequest` whose upstream no longer matches its v1 digest.
5. **Binding inputs**, else `request_unbuildable`:
   - `endpoint_digest` is 64 lowercase hex;
   - `authority` fullmatches `<host>(?::(?P<port>[1-9][0-9]{0,4}))?`, where `<host>` is the endpoint host grammar with the same `localhost` and `.local` exclusions;
   - the port, if present, is at most 65535 and is never `443`. This matches `UpstreamEndpoint.authority`, so `:0`, `:0443`, `:443` and `:65536` are refused.
6. **Construct** the `UpstreamDescriptor`. Its `__post_init__` enforces grammar, consistency and the three wire bounds, else `request_unbuildable`.
   - A successful `request_descriptor`, and therefore a successful `prepare`, implies that `render_parts` succeeds.
   - A request that can never be built is refused at E7c (403 `route_denied`), before reserve, admission or any future permit consumption.
   - **The one bound that can bite:** unit 12's `_valid_target` accepts up to 2,048 bytes, but a GET request line is `len(target) + 15` bytes. A `jira.issue.get` target of 2,034 to 2,048 bytes is therefore v1-valid but unbuildable.

The descriptor document and digest:

```
{"v": 2, "service", "route_id", "policy_digest", "scope_digest", "endpoint_digest", "method",
 "target", "authority", "accept", "content_type": str | null, "body_bytes": int,
 "body_sha256": hex | null}
```

`digest = tagged_digest(REQUEST_DIGEST_V2_TAG, document)`.
- `authority` is explicit, so "Host included" holds literally.
- `prepare(routed) = request_descriptor(routed, endpoint_digest=endpoint.digest, authority=endpoint.authority).digest`.
- The tag differs from v1, so `prepare` never returns a v1 digest, and 13a E7c also refuses equality. No v1 digest can ever satisfy a permit.
- **Excluded:** the credential secret, the user, the sentinel, caller headers and `lease_id`.
- **Confidentiality:** like v1, the v2 digest is correlation data, not a secret. It reveals the selected manifest entry and the configured endpoint identity.

### Wire profile (`WIRE_PROFILE`)

`render_parts(descriptor)` is pure and ASCII, with CRLF line endings. It emits exactly:

```
prefix = method SP target SP "HTTP/1.1" CRLF
         "Host: " authority CRLF
(send-time only) "Authorization: " <credential value> CRLF
suffix = "Accept: " accept CRLF
         "Accept-Encoding: identity" CRLF
         [ "Content-Type: " content_type CRLF "Content-Length: " decimal(body_bytes) CRLF ]   iff body_bytes > 0
         "Connection: close" CRLF
         CRLF
         body
```

Header names use exactly this case and order, with one space after each colon. The profile never emits:
- `User-Agent`, `Expect`, `Transfer-Encoding`, or any keep-alive, cookie, proxy or forwarding header;
- any caller header.

A bodyless GET carries neither `Content-Length` nor `Content-Type` (spec L188-189).

**Two upstream-only additions beyond spec L199-200.** That line lists the headers the Forwarder reconstructs: Host, credential, Content-Length, Accept and Content-Type. The profile adds two more, both code constants covered by `WIRE_PROFILE` and the goldens, and both listed as open questions:
- **`Connection: close`** makes each upstream connection carry one request, matching the connector's one-connection-per-request transport. Routes Deferred item 3 anticipated it ("`Content-Length`/`Connection: close`"). Spec L167-168 governs the inbound listeners, not upstream requests, so it is not the source.
- **`Accept-Encoding: identity`**. The committed codec rejects `Content-Encoding` (`forwarder_http_response._FORBIDDEN_HEADERS`). Without `Accept-Encoding`, an RFC 9110 §12.5.3 server may choose any coding.

**Bounds.** `_wire_lengths` computes them, and `UpstreamDescriptor.__post_init__` enforces them at prepare time, else `request_unbuildable`:
- the request line, including CRLF, is at most 2,048 bytes;
- the head after the request line, counting a worst-case `Authorization` line of `17 + MAX_AUTHORIZATION_BYTES` bytes, is at most 16,384 bytes;
- the body is at most 262,144 bytes.

The total therefore never exceeds `forwarder_receipts.MAX_REQUEST_BYTES`.

**Pure-function property** (routes rule v2). For a captured upstream wire `W`:
- `W` has exactly one `Authorization` line, at line index 2.
- Replacing its value with `<redacted>` gives `prefix + b"Authorization: <redacted>\r\n" + suffix` for the descriptor that `prepare` produced.
- The parts read only `method`, `target`, `authority`, `accept`, `content_type`, `body_bytes` and `body`, with `sha256(body) == body_sha256`.
- Equal v2 digests imply identical redacted bytes.
- The digest is strictly finer than the wire. `policy_digest`, `scope_digest`, `endpoint_digest` (address, trust, `credential_id`, revision) and `route_id` change the digest but not the bytes.
- Two credentials differ only inside the `Authorization` value.

### Golden vectors

Revision 2 leaves every value unchanged. Inputs are the unit-12 goldens: `policy-r1` (`3013f6a1...`) and the `scope-r1` manifest (`849028ca...`).
- **v1 values:**
  - `jira.issue.get` for `SYN-1` with default fields is `43d8b4787de8e9370f79c719f3dbd5463e259bce78b98cd27daa246c7042b929`, with target `/rest/api/3/issue/90101?fields=issuetype%2Clabels%2Cproject%2Cstatus%2Csummary`.
  - `jira.search` with default `maxResults` is `d416cc8619c619fe09b16796d7b87c515503e74ce6624f3a2d75570ce9d0692e`, with a 229-byte body whose SHA-256 is `e95499d5...`.
- **Synthetic endpoint:** service `jira`, revision `upstream-r1`, host `jira-upstream.synthetic.invalid`, address `192.0.2.10`, port 443, and `credential_id` `jira-basic-synthetic-1`.
- **Stand-in trust list:** `[sha256(b"maoi-synthetic-upstream-ca-v1")] = ["5c8b39e14dbaa86a0d3aa5655bc6f88015319f5603cd7463ba3820887887b60f"]`.

**Endpoint.** Tests pin these as literals via `endpoint_document` plus `tagged_digest`, and recompute them independently.
- Canonical bytes, 480 B:

```
{"address":"192.0.2.10","base_path":"/rest/api/3/","credential_id":"jira-basic-synthetic-1","credential_profile":"basic","endpoint_policy":"synthetic-only.v1","host":"jira-upstream.synthetic.invalid","port":443,"revision":"upstream-r1","schema":"maoi.forwarder.upstream-endpoint.v1","service":"jira","tls_profile":"maoi.forwarder.upstream-tls.v1","trust_sha256":["5c8b39e14dbaa86a0d3aa5655bc6f88015319f5603cd7463ba3820887887b60f"],"wire_profile":"maoi.forwarder.upstream-wire.v1"}
```

- `endpoint_digest` = `70b8b3d344d69be09c88244ad87b83d3928fae456b0f8ee7c52bb52c788eba21`.
- The port-8443 variant is 481 B, with `endpoint_digest` = `0360f89d6dd4f5c633bfa490d76129e4a1643746a65503d8ef589803b54b3d69`.

**v2 digests:**
- `jira.issue.get`: descriptor 535 B, v2 = `0eaa6e61bb60d9a8663ef2807ac777beb41963a1e01d22cbd2d4731f82fd8dce`.
- `jira.search`: descriptor 555 B, v2 = `37f859dd0e55320f14709ab86ffb94d6ae2bb9277a954f3c264708c6988c4127`.
- `jira.issue.get` via the 8443 endpoint, with authority `jira-upstream.synthetic.invalid:8443`: descriptor 540 B, v2 = `f11826c2e26046e477e09ad0b987329b5977a8f5b237d50441f7e515e6d4880a`.

**Parts and wire.** The synthetic credential is service `jira`, profile `basic`, user `synthetic-user@example.invalid` and token `synthetic-token-0001`. Its value is `Basic c3ludGhldGljLXVzZXJAZXhhbXBsZS5pbnZhbGlkOnN5bnRoZXRpYy10b2tlbi0wMDAx` (74 B).
- **`jira.issue.get`:**
  - prefix 132 B and suffix 74 B, with `sha256(prefix + suffix)` = `cf30dfb64565e085862a12d6862a2631bca68c163eebbb311a05f7f49bc3a736`;
  - full wire 297 B, sha256 `5d7e615700e1420b602aa1d6fc879370ffd850ad80c6cffb8a7d71f7b371d28f`:
    `b'GET /rest/api/3/issue/90101?fields=issuetype%2Clabels%2Cproject%2Cstatus%2Csummary HTTP/1.1\r\nHost: jira-upstream.synthetic.invalid\r\nAuthorization: Basic c3ludGhldGljLXVzZXJAZXhhbXBsZS5pbnZhbGlkOnN5bnRoZXRpYy10b2tlbi0wMDAx\r\nAccept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n'`;
  - redacted wire 233 B, sha256 `d8b34b81b9c17dd08b0076106e4cfea12be03fdff7260d86bbd79e9c71ef65fd`.
- **`jira.search`:**
  - prefix 77 B and suffix 356 B, with `sha256(prefix + suffix)` = `5a627070263090033b4d7c43ee008adbba4d5d6da5fb5af4eedfa4974f7659d6`;
  - full wire 524 B, sha256 `bc63a733582b41ca053957012f0990586c299a043fb996e2ad779ed35391a826`. The suffix adds `Content-Type: application/json\r\nContent-Length: 229\r\n` before `Connection`;
  - redacted wire 460 B, sha256 `096952c097451757b13e1a4c5aaac147aa6ba04ea6e96b60f875fb8719a99c27`.
- **8443 `jira.issue.get`:**
  - full wire 302 B, sha256 `1aebec6abb6ab933e24225554278826f7012f9468011849c245a3cdcdf6e40f1`;
  - redacted wire 238 B, sha256 `881a86f8c1e35260a712316ec1df4442349bec5d213de579ff000aea84feeeb3`.

The wire contains no endpoint digest. Integration captures must therefore equal these literals exactly, even though the fixture CA, and with it the integration v2 digest, is random per session. Integration receipts are checked against an independent recomputation from the DER digests of the fixture PEM.

**Golden upstream responses.** Both are accepted by `check_response` as `ok`, which was verified during synthesis.
- IssueBean (204 B): `{"fields":{"issuetype":{"id":"90002"},"labels":["fp-0123456789abcdef"],"project":{"id":"90001","key":"SYN"},"status":{"statusCategory":{"key":"syn-new"}},"summary":"synthetic"},"id":"90101","key":"SYN-1"}`.
- Search result (231 B): `{"isLast":true,"issues":[<IssueBean>]}`.

## Transport: connect, channel, abort and close

### `connect(admission, routed, *, request_digest, deadline)`

13a E10 calls this outside `G`, after an `Admission`. Steps, in order:
1. **Pre-socket checks.** Each failure gives `connect_failed`, and no socket exists yet.
   - **Types.** `type(admission) is Admission` and `type(routed) is RoutedRequest`. `request_digest` is an exact `str` matching `[0-9a-f]{64}`. `deadline` is an exact finite `int` or `float`, not `bool`.
   - **One connect per Admission.** Under `self._lock`, an admission already in `_connected` is refused; otherwise it is added. The first call consumes the admission, whatever its outcome.
   - **Bindings.** `admission.service == routed.service == "jira"` and `admission.route_id == routed.route_id`.
   - **Digest.** `descriptor = request_descriptor(...)` with this endpoint (errors are recorded), then `hmac.compare_digest(descriptor.digest, request_digest)`. This refuses the v1 digest, another route's digest and another endpoint's digest.
   - **Parts.** `parts = render_parts(descriptor)`. It cannot fail for a descriptor that passed `prepare`; any error is recorded as a local fault.
   - **Deadline cap.** `deadline <= admission.connect_deadline`.
2. **Clock.** `t0 = time.monotonic()`; a fault or a non-finite value gives `connect_failed`. If `deadline <= t0`, raise `deadline`. `limit = min(deadline, t0 + CONNECT_SECONDS)`, which enforces spec L175's 5 s.
3. **Context.** `context = _build_context(endpoint.ca_pem, endpoint.trust_sha256)`, including the runtime read-back. A failure gives `connect_failed`.
4. **TCP.** One attempt, with no retry, no alternate address and no proxy.
   - `raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)`, then `raw.set_inheritable(False)`, `raw.settimeout(remaining)` and `raw.connect((endpoint.address, endpoint.port))`. This is the module's only `connect` call site.
   - The destination is a validated canonical IPv4 literal, so CPython's numeric path never invokes a resolver.
   - An `OSError` or a timeout gives `connect_failed`.
5. **Recheck.** If no time remains, raise `deadline`.
6. **TLS.**
   - `secured = context.wrap_socket(raw, server_hostname=endpoint.host, do_handshake_on_connect=False)`, then `secured.set_inheritable(False)`, `settimeout(remaining)` and `do_handshake()`.
   - Then the post-handshake checks.
   - Any `OSError`, `ssl.SSLError`, `ValueError` or `TypeError` in this phase gives `upstream_tls_failed`. That includes a handshake timeout and a failed check.
7. **Final recheck.** If no time remains, raise `deadline`.
8. **Return** `_UpstreamChannel(_CHANNEL_TOKEN, sock=secured, parts=parts, credential=self._credential, exchange_deadline=admission.exchange_deadline)`.

A `finally` closes the owned raw or secured socket with `_close_quietly` unless the channel was returned.

**`_close_quietly(sock)`** follows the handler rule, so it is flag-based. It catches `Exception`, not `BaseException`:

```
failed = False
try: sock.close()
except Exception: failed = True
if not failed: return
descriptor = -1
try: descriptor = sock.detach()
except Exception: descriptor = -1
if type(descriptor) is int and descriptor >= 0:
    try: socket.close(descriptor)
    except Exception: pass
```

Unlike `forwarder_tls._close_quietly`, it does not swallow `KeyboardInterrupt` or `SystemExit`. An interrupt during cleanup means the process is ending, the kernel reclaims the descriptor, and hiding the interrupt would be worse.

**No application bytes.** `connect`, `_build_context` and the TLS helper contain no `send`, `sendall` or `write` call (AST-checked). TLS handshake bytes are not application bytes, so a `FAILED` receipt truthfully means zero application bytes (13a A3).

### Channel state and locking

- One non-reentrant `threading.Lock` guards all channel state:
  - `_phase`: one of `open`, `sending`, `sent`, `receiving`, `received` or `failed`;
  - the flags `_aborted`, `_closed`, `_io_active` and `_close_pending`;
  - `_sock` and `_credential`.
- The lock is never held across I/O. The only syscall ever made under it is `abort`'s non-blocking `shutdown(2)`.
- Under 13a, `send`, `receive` and `close` run on the owning serve thread (E13, then E14, then the E10 `finally`). `abort` may run on any thread: the gate's overdue tick or `shutdown`.
- `_finish_io(phase)` runs under the lock when I/O ends. It clears `_io_active`, sets the phase and sets `_credential` to `None`. If `_close_pending` is set and the channel is not yet closed, it sets `_closed`, takes the socket, and closes it outside the lock.

### `send(*, deadline)`

This is 13a E13, called only after `write_admitted`. It enforces spec L175 (10 s) and L212-217 (no reissue).
1. **Under the lock.** The result is `write_failed` and nothing is written if any of these hold: the channel is closed or aborted, `_phase != "open"`, or `_sock` or `_credential` is `None`. A second send, a send after abort, and a send after close therefore all write zero bytes. Otherwise it captures the local references `sock = self._sock` and `credential = self._credential`, then sets `sending` and `_io_active`. Later steps use only these locals, so a concurrent abort or close cannot make assembly dereference `None`.
2. **Outside the lock,** inside `try/finally`:
   - `deadline` must be an exact finite number with `deadline <= exchange_deadline`, else `write_failed` before any I/O. The clock is read; a fault gives `write_failed`, and `deadline <= now` gives `deadline`. `limit = min(deadline, now + WRITE_SECONDS)`.
   - **Assemble** the buffer as described under "Credential custody". Any `Exception` during assembly gives `write_failed`, with nothing written.
   - **Loop** over `memoryview` chunks of at most `MAX_WRITE_CHUNK_BYTES`:
     - under the lock, with no I/O: if `_aborted` or `_close_pending` is set, stop with `write_failed`. An abort that lands between chunks therefore stops further bytes deterministically, without relying on `EPIPE`;
     - read the clock; a fault or regression gives `write_failed`, and `remaining <= 0` gives `deadline`;
     - `settimeout(min(WRITE_SECONDS, remaining))`;
     - `count = sock.send(chunk)`. This is the module's only `.send(` call site;
     - an exception gives `write_failed`;
     - `count` must be an exact `int` with `0 < count <= len(chunk)`, else `write_failed`;
     - a partial count continues with the remainder;
     - a chunk that took 10 s or more gives `write_failed`;
     - `_bytes_accepted` records the progress.
   - `finally`: release the views and set `chunk = None`, zero the buffer in place, set `credential = None`, then `_finish_io("sent")` or `_finish_io("failed")`.
3. **Raise** after the `try` statement.

There is no half-close, and nothing is written after the request.

### `receive(*, deadline) -> ParsedResponse`

This is 13a E14; spec L169-176.
1. **Under the lock.** It requires `_phase == "sent"`, not aborted, not closed, and `_sock` not `None`, else `receive_failed` without touching the socket. A receive before send, a second receive, and a receive after abort therefore read nothing. Otherwise it captures `sock = self._sock` and sets `receiving` and `_io_active`.
2. `deadline` must be an exact finite number with `deadline <= exchange_deadline`, else `receive_failed`. A clock fault gives `receive_failed`, and `deadline <= now` gives `deadline`.
3. `response = receive_response(sock, deadline=deadline)`, through the module global. This is the only read path: the AST finds no `recv`, `recv_into`, `read`, `makefile` or `unwrap` call. Unit 10 supplies:
   - the per-read inactivity limit `min(20 s, remaining)`, including for the first byte;
   - the 2 KiB status-line, 16 KiB head and 1 MiB body caps;
   - canonical `Content-Length` with exactly `application/json`;
   - rejection of 1xx and 3xx, chunked or encoded bodies, extra bytes, truncation and EOF;
   - rejection of a deadline more than 40 s away.
4. **Mapping.**
   - A `ResponseReceiveError` with code `deadline_expired` gives `deadline`.
   - Every other code gives `receive_failed`: `invalid_deadline`, `receive_failed`, `invalid_connection`, `connection_claimed`, `clock_fault` and `timeout_restore_failed`.
   - Any other `Exception`, or a result that is not exactly a `ParsedResponse`, also gives `receive_failed`.
   - A recv stall therefore gives `receive_failed`, as in 13a U2 and U3.
5. `finally`: `_finish_io("received")` or `_finish_io("failed")`.

### `abort()`

Idempotent, thread-safe and non-blocking. It never raises an `Exception`.
- **Under the lock:** return if the channel is closed or already aborted. Otherwise set `_aborted`, drop the credential reference, and call `_shutdown_fd(sock)`.
- **`_shutdown_fd(sock)`** is `super(ssl.SSLSocket, sock).shutdown(socket.SHUT_RDWR)`. Every `Exception` is recorded only, including the `TypeError` that a non-`SSLSocket` raises. It is the module's only `shutdown` call (AST-checked).
- **Two barriers against plaintext after abort.**
  1. **The kernel.** After `shutdown(SHUT_RDWR)`, any later write on the fd fails with `EPIPE`, whichever `shutdown` was called.
  2. **The base-class call.** CPython 3.13 `SSLSocket.shutdown` sets `_sslobj = None`, after which `SSLSocket.send` and `recv` take the plaintext `socket` path. The base-class call keeps `_sslobj`, so no code path ever takes the plaintext branch. `version()` and the other TLS accessors stay valid, a later write fails as a TLS write, and a blocked reader wakes with EOF (`receive_failed`).

  The second barrier is defense in depth. Integration evidence covers both, including a control that pins the CPython behavior.
- Because the shutdown runs under the lock, and `close` marks `_closed` under the same lock before releasing the fd, `abort` can never shut down a descriptor number the OS has reused. That makes it safe before, during, after and concurrently with `close` (13a critic issue 16).

### `close()`

Idempotent. It never raises an `Exception`.
- Under the lock: return if already closed.
- If `_io_active`: set `_close_pending`, and if not yet aborted, set `_aborted` and call `_shutdown_fd` to wake the I/O. Then return; `_finish_io` completes the close.
- Otherwise set `_closed`, take `_sock`, set `_sock` and `_credential` to `None`, and call `_close_quietly(sock)` outside the lock.
- No `close_notify` or `unwrap` is sent, because `unwrap` can block.
- Under 13a's wiring the deferred branch is unreachable, because E10's `finally` runs after I/O has returned. The branch exists so that the "safe from any thread" property is proven rather than assumed.

**Per request** there is exactly one `prepare`, one `connect` (one TCP connection and one handshake), one `send` and one `receive_response`. There is no pooling, keep-alive, retry, redirect-follow or replay.

## Deadlines

| Phase | Caller argument (13a) | Channel requirement | Effective limit |
| --- | --- | --- | --- |
| connect | `admission.connect_deadline = min(admitted_at + 5, exchange_deadline)` | `now < deadline <= admission.connect_deadline`, else `deadline` or `connect_failed` | `min(deadline, t0 + 5)` |
| send | `fence.write_deadline = min(fence + 10, exchange_deadline)` | `now < deadline <= exchange_deadline`, else `deadline` or `write_failed` | `min(deadline, t0 + 10)`; each chunk `min(10, remaining)`; a chunk of 10 s or more fails |
| receive | `admission.exchange_deadline = dispatch_deadline - 1` | `now < deadline <= exchange_deadline`, else `deadline` or `receive_failed` | `receive_response`: 20 s per-read inactivity, at most 40 s |

- All phases use `time.monotonic`, the domain 13a E1 requires (`gate.system_clock`).
- The channel only enforces and clips deadlines. No argument can widen them.

## Error and receipt mapping to 13a

| Connector outcome | Code | 13a step | Receipt | Client |
| --- | --- | --- | --- | --- |
| `prepare` error: shape, catalog, permit, v1 inconsistency, authority, or a wire bound (for example a 2,034-byte GET target) | `UpstreamPrepareError` | E7c | `NOT_DISPATCHED`/`route_denied`, digest `d25b40c6...` or `e527abd1...` | 403 |
| connect pre-socket refusal, including a second connect for an Admission, a wrong digest, an over-wide deadline or a context read-back fault | `connect_failed` | E10 | `FAILED`/`connect_failed` | 502 `forwarder_upstream_failed` |
| connect deadline passed | `deadline` | E10 | `FAILED`/`connect_failed` (nothing written) | 502 |
| TCP refused or timed out | `connect_failed` | E10 | `FAILED`/`connect_failed` | 502 |
| handshake, verification or post-handshake check | `upstream_tls_failed` | E10 | `FAILED`/`upstream_tls_failed` | 502 |
| lease revoked during the handshake (SNI callback), shutdown or time | none; fence denial | E12 | `FAILED`/`connect_failed`, zero application bytes | 502 |
| send refused before I/O, including abort between fence and send, or an assembly fault | `write_failed` | E13 | `DISPATCHED_UNKNOWN`/`write_failed`, conservative: zero bytes, but the ledger is already `dispatched` | 502 `forwarder_dispatch_unknown` |
| between-chunk deadline | `deadline` | E13 | `DISPATCHED_UNKNOWN`/`deadline` | 504 |
| write error, chunk stall, between-chunk abort, or `EPIPE` after abort | `write_failed` | E13 | `DISPATCHED_UNKNOWN`/`write_failed` | 502 |
| stall, 3xx with `Location`, chunked, `charset`, `gzip`, over 1 MiB, truncation, EOF or abort | `receive_failed` | E14 | `DISPATCHED_UNKNOWN`/`receive_failed` | 502 |
| `deadline_expired` between reads | `deadline` | E14 | `DISPATCHED_UNKNOWN`/`deadline` | 504 |
| codec-valid response | `ParsedResponse` | E14, E15 | `TRANSPORT_CONFIRMED`/`ok` (byte-exact 200), or `response_policy_rejected` (4xx/5xx) | 200, or 502 `forwarder_response_rejected` |

The receipts reason table already contains every reason used, so `forwarder_receipts.py` is unchanged.

## Connector obligations and evidence

| # | 13a obligation ("Upstream contract in 13a") | How 13b meets it | Evidence |
| --- | --- | --- | --- |
| O1 | `prepare` is pure and never v1 | pure recomputation under a distinct tag; bounds enforced at prepare | A: goldens, tripwires, property, boundary at N and N+1; C: AST |
| O2 | `connect` writes no application bytes, refuses a digest it did not prepare, and runs at most once per Admission | no send in connect (AST); recompute and compare; `WeakSet` | B: `captured == b""`, each paired with a positive control, plus TLS-record framing of all raw bytes; A: socket tripwire |
| O3 | `send` is the first write, exactly once, only after `write_admitted` | phase lock; references captured under the lock; one send site; per-chunk abort check | A: fakes; B: second send; composition: the first-byte observer sees the ledger `dispatched` |
| O4 | `receive` enforces 20 s inactivity and returns only codec-parsed responses | one read path; closed mapping | A: spy; B: inactivity timing and codec variants |
| O5 | `abort` is idempotent, thread-safe and non-blocking, and safe with `close` | lock plus base-class shutdown; closed check | A: fake races; B: real races, abort during a real blocked `SSL_write`, a direct send after `_shutdown_fd`, fd reuse (deterministic and concurrent) |
| O6 | `close` is idempotent and always runs | lock; deferred close | A and B |

**Evidence discipline.** Every "zero application bytes" or "nothing written" assertion is paired with a positive control: the same fixture configuration capturing the exact golden bytes, which shows the fixture is not blind.

## Existing-module changes

- **No source module changes.**
  - `forwarder_tls.py` stays byte-identical. The upstream module builds its own context, and it duplicates the PEM grammar and bounds, pinned by a parity test.
  - Also unchanged:
    - `forwarder_routes.py`, whose `REQUEST_DIGEST_TAG` stays `maoi.forwarder.request.v1`, with every unit-12 golden intact;
    - 13a's `forwarder_dispatch.py` and `forwarder_exchange.py`;
    - `forwarder_json.py`, `forwarder_receipts.py`, `forwarder_response_receive.py`, `forwarder_http_response.py` and `forwarder_response_send.py`;
    - `forwarder_services.py`, `forwarder_leases.py`, `forwarder_server_tls.py`, `forwarder_http*.py` and `forwarder_supervisor.py`.
  - Every existing test file stays byte-identical and green.
- **`docs/forwarder-control.md`** (root) gains a section "Synthetic fixed-origin upstream connector". It covers:
  - the endpoint shape, the `synthetic-only.v1` gate, and the spec L441-448 decisions that must precede any widening;
  - the no-DNS rule: a canonical IPv4 literal, the numeric path and the AST ban;
  - the strict per-connect context, the runtime read-back, the post-handshake checks, and the deliberate differences from the listener policy, including wildcard acceptance;
  - the process-level OpenSSL configuration non-claim;
  - the credential type, its `service`/`profile` binding, its claim, and the custody non-claims;
  - the endpoint digest, rule v2 (including prepare-time wire bounds), and the exact wire profile. It names both upstream-only header additions, `Connection: close` (routes Deferred item 3) and `Accept-Encoding: identity`;
  - deadlines and the error-to-receipt mapping;
  - abort and close semantics: the two plaintext barriers and the deferred close;
  - that there is no production caller, and the non-claims.

  Append the three new test files to the focused pytest command.

## Ownership and validation

**Implementer A** owns `forwarder_upstream.py` and `tests/test_forwarder_upstream.py`. These tests are deterministic and open no sockets. Real CA PEM comes from `prototype.mediated_client.certificates.create_certificates` in a module-scoped temporary directory.

1. **Constants:**
   - `ENDPOINT_POLICY`, the tags and the profiles are pinned;
   - `CREDENTIAL_PROFILES == {"jira": "basic"}`, and `set(DISPATCHABLE_SHAPES) == MATCHABLE_ROUTE_IDS`;
   - the network tuples are pinned;
   - `_OP_ALLOW_UNSAFE_LEGACY_RENEGOTIATION == 0x0004_0000`, and `_CHANNEL_SOCKET_TYPE is ssl.SSLSocket`;
   - `CONNECT_SECONDS == 5.0` and `WRITE_SECONDS == 10.0`, imported from 13a;
   - `forwarder_response_receive._INACTIVITY_LIMIT == forwarder_dispatch.READ_INACTIVITY_SECONDS == 20.0`;
   - `MAX_WRITE_CHUNK_BYTES == forwarder_response_send._MAX_CHUNK_BYTES`;
   - the trust bounds equal `forwarder_tls`'s private bounds.
2. **Endpoint:**
   - each ordered rule gives its code, and a value that fails several rules gives the earliest one;
   - a bad PEM on a non-synthetic host gives `trust_invalid`; a valid PEM on `jira.example.com` gives `endpoint_unqualified`, with `socket.socket` patched to raise;
   - **trust order:** with `_PEM_BUNDLE` monkeypatched to a recorder, an oversize (131,073-character) or empty `ca_pem` gives `trust_invalid` with zero `fullmatch` calls;
   - the golden 480 B document and both endpoint digests are pinned as literals and recomputed with the reference encoder;
   - the live `endpoint.digest` equals `tagged_digest(ENDPOINT_SCHEMA, endpoint_document(..., trust_sha256 = sorted DER sha256 of the fixture PEM))`;
   - the same CA re-encoded (CRLF line endings, reordered blocks, trailing newline) gives the same digest;
   - every field change changes the digest;
   - authority rendering for 443 and 8443;
   - `trust_invalid` for a leaf-only PEM, a private-key block, 17 certificates, more than 128 KiB, non-ASCII input, an empty string and a duplicated block;
   - **parity:**
     - the pattern source string equals `forwarder_tls._PEM_BUNDLE.pattern`, and the size and count bounds are equal;
     - a shared corpus of grammar, size and count cases is accepted or rejected identically by `forwarder_tls._validate_ca_pem` and the upstream grammar stage (steps 7.1-7.3, white-box `_check_trust_grammar`). The corpus contains no duplicates and no leaf-only bundles;
     - the **deliberate differences** are asserted separately: a duplicated block passes `forwarder_tls._validate_ca_pem` and `_strict_context` but gives `trust_invalid` here;
   - `dataclasses.replace` revalidates.
3. **Context** (white-box `_build_context`):
   - `PROTOCOL_TLS_CLIENT`, `CERT_REQUIRED`, `check_hostname`, no common-name fallback, a TLS 1.2 minimum, and `maximum_version` in the allowed set;
   - `verify_flags` equals exactly `VERIFY_X509_STRICT | VERIFY_X509_TRUSTED_FIRST`;
   - the three options are present, and `OP_IGNORE_UNEXPECTED_EOF`, `OP_LEGACY_SERVER_CONNECT` and bit 18 are absent;
   - `keylog_filename is None`, and `post_handshake_auth is False`;
   - the DER set of `get_ca_certs(binary_form=True)` equals `trust_sha256`;
   - two calls return distinct objects;
   - **read-back is live:** `ssl.SSLContext` is monkeypatched to a subclass whose `options` read-back adds `OP_LEGACY_SERVER_CONNECT`, or drops `OP_NO_TICKET`, or whose `minimum_version` reads back `TLSv1`. In each case endpoint construction gives `trust_invalid`, and `connect` on an already-built endpoint gives `connect_failed` with no socket created;
   - with `SSLKEYLOGFILE`, `SSL_CERT_FILE` and `SSL_CERT_DIR` monkeypatched to a temporary keylog path and the wrong CA, the attributes and CA set are unchanged, and the keylog file is never created.
4. **Credential:**
   - **Validation matrix**, each giving `credential_invalid`:
     - `:` in the user; a space, CR or LF; non-ASCII user or token; empty values; lengths of 257 and 1,025;
     - a wrong `service` (`confluence`) or `profile` (`bearer`);
     - a `str` subclass passed for `user` or `token`. The subclass overrides `encode`, `__add__`, `__radd__`, `__len__`, `__iter__` and `__getitem__` to record calls, and the test asserts that none was called;
   - for every failure, `__cause__` and `__context__` are `None`, so no `UnicodeEncodeError` exists;
   - **frame locals** (critic issue 1): for every failure, walking `e.__traceback__` to the `BasicCredential.__init__` frame shows no `user` or `token` key in its `f_locals`, and no marker (as str, bytes, base64 or `user:token`) in any value reachable from that frame's locals;
   - the header literal (`Basic c3ludGhl...MDAx`);
   - repr, str, f-strings, `%r` and `format` are redacted, show `service='jira', profile='basic'`, and never show the user;
   - `vars()`, `pickle.dumps`, `copy.copy` and `copy.deepcopy` raise `TypeError`;
   - setattr, delattr and subclassing are refused, and equality is identity;
   - **the connector:**
     - a mismatched `credential_id`, `service` or `profile` gives `credential_mismatch`;
     - a second connector gives `credential_claimed`;
     - wrong types give `TypeError`;
     - a refused construction leaves the credential unclaimed, so a later valid connector succeeds.
5. **O1, prepare and descriptor:**
   - the v2 literals `0eaa6e61...` (535 B), `37f859dd...` (555 B) and the 8443 `f11826c2...` (540 B), through `request_descriptor` with the literal endpoint digest and authority;
   - independent reference recomputation;
   - v2 differs from v1 for both goldens;
   - `prepare` returns the literal-equivalent value identically across 100 calls, with `socket.socket`, `ssl.SSLContext`, `time.monotonic` and `socket.getaddrinfo` monkeypatched to raise `AssertionError`;
   - **request-line boundary through `prepare`:**
     - `jira.issue.get` routed requests are built by `dataclasses.replace`, with a `fields=` list of readable names padded to a target of exactly 2,033 bytes (request line 2,048) and 2,034 bytes (2,049), and a v1 digest recomputed with `forwarder_routes.request_digest`;
     - both are v1-valid. 2,033 prepares, and its `render_parts` request line is exactly 2,048 bytes. 2,034 raises `UpstreamPrepareError("request_unbuildable")` before any socket, clock or context use;
   - **refusals:**
     - `shape_unavailable`:
       - `replace(route_id="jira.issue.create")`, a changed service, or `requires_permit=True`;
       - a catalog monkeypatched to `unavailable`, a catalog missing the route key (no `KeyError`), or a catalog object whose `.get` raises;
       - a target outside the base, or an issue target naming `comment`;
     - `request_inconsistent`: `replace(request_digest=<other hex>)`, a replaced upstream target or body without recomputing v1, and a non-ASCII `request_digest`;
     - `request_unbuildable`: a malformed `endpoint_digest`, and the authorities `host:0`, `host:0443`, `host:443`, `host:65536`, `HOST`, `x.local` and `192.0.2.10`. `host:8443` is accepted;
   - **seeded property** over 500 policy-routed requests (selector form, `fields` spelling, `maxResults` 1..50, body whitespace, manifests of 1..256 entries):
     - v2 is 64 hex and never equals v1 or any unit-12 denial digest;
     - equal upstreams give equal v2;
     - changing a binding-only field changes v2.
6. **Wire:**
   - the golden parts, full wires and redacted wires are byte-exact literals;
   - request-line, head and body bounds at N and N+1, both on direct `UpstreamDescriptor` construction and via `_wire_lengths`;
   - CR, LF or space in target, authority, `accept` or `content_type` gives `request_unbuildable`;
   - a property against an independent test-local `reference_render(document, body, value)`: head lines exactly as specified, `Host == authority`, `Content-Length == body_bytes`, and two credentials differ only inside the `Authorization` value;
   - two inbound requests that differ only in the sentinel give identical descriptors and parts.
7. **O2, pre-socket.** With `socket.socket` patched to raise, each of these raises `UpstreamError` and creates no socket: the v1 digest, another route's v2, a v2 from the 8443 connector, a second connect for the same Admission, a mismatched `admission.route_id` or service, wrong types, a non-hex digest, a deadline beyond `admission.connect_deadline`, and a faulting clock. Each gives `connect_failed`, except a passed deadline, which gives `deadline`.
8. **Channel,** with `FakeTLSSocket` via the documented white-box path (`_CHANNEL_SOCKET_TYPE` monkeypatched, `_CHANNEL_TOKEN` passed).
   - **The fake** records `settimeout`, `send`, `shutdown` and `close` calls in order, with scriptable partial counts, blocking, exceptions and per-call callbacks. On each `send` it retains `chunk.obj` (the underlying `bytearray`) and a `bytes(chunk)` copy. `_shutdown_fd` is monkeypatched to record calls and release a blocked fake.
   - **Constructor:** a wrong token, a plain `socket.socket` or a `FakeTLSSocket` without the monkeypatch, wrong `parts` or `credential` types, and a `bool` or `nan` `exchange_deadline` each raise `TypeError`.
   - **O3:**
     - one send writes the golden bytes once;
     - a second send, a send after abort, and a send after close each give `write_failed` with zero `send` calls;
     - a deadline past `exchange_deadline` gives `write_failed` before any I/O.
   - **Chunking:**
     - a white-box `RequestParts` with a 40 KiB body sends chunks of 16,384, 16,384 and the remainder;
     - 7-byte partial counts continue;
     - every `settimeout` is at most 10 and at most the remaining time;
     - a between-chunk deadline gives `deadline`, and clock regression gives `write_failed`.
   - **Per-chunk abort check:** the fake's first-`send` callback calls `channel.abort()`. The result is `write_failed` with exactly one `send` call and no second chunk.
   - **Abort between step 1 and assembly** (critic issue 5): `forwarder_upstream.time` is replaced with a stub whose first `monotonic()` call runs `channel.abort()` and then returns a valid time. Assembly succeeds from the captured locals with no `AttributeError`. The per-chunk check then gives `write_failed` with zero `send` calls. The buffer is zeroed, and `_credential is None`.
   - **Custody:**
     - after a successful send, every retained `chunk.obj` is the same `bytearray`, and it is all zeros after `send` returns;
     - after a failed send, the `buffer` local of the `send` frame in the caught traceback is all zeros, and that frame's `credential` local is `None`;
     - in both cases the channel's `_credential` is `None`.
   - **O4:**
     - receive before send gives `receive_failed`, and the `receive_response` spy is never called;
     - receive calls the spy exactly once, with the identical socket and deadline;
     - the mapping table: every `ResponseReceiveError` code, a `RuntimeError`, and a result that is not a `ParsedResponse`;
     - a second receive gives `receive_failed`.
   - **O5:**
     - abort is idempotent, with one `_shutdown_fd` call;
     - abort during a blocked fake send returns in under 0.1 s, and the send ends `write_failed`;
     - abort after close makes no call;
     - `OSError` is swallowed;
     - the unpatched `_shutdown_fd` on a `FakeTLSSocket` raises `TypeError` internally, which is swallowed, and `abort` returns normally.
   - **O6:**
     - two closes give one `sock.close`;
     - close exceptions are swallowed;
     - close during an active send logs `[shutdown, send returns, close]`, and `sock.close` never runs while `_io_active`.
   - **Races:**
     - a reused pool of 8 persistent worker threads, synchronized per iteration by one `threading.Barrier`, runs 200 iterations of a seeded (`random.Random(20260923)`) abort/close/send/receive assignment on a fresh fake channel;
     - no exception escapes, `sock.close` runs exactly once per channel, and every abort returns in under 0.1 s;
     - the pool is joined with a 4 s bound.
9. **Error discipline.** Every code in both closed sets, and every `UpstreamError` the module raises, has `args == (code,)`, with `__cause__` and `__context__` equal to `None`.

**Tester B** owns `tests/test_forwarder_upstream_integration.py`. It uses real local TLS on an ephemeral `127.0.0.1` port, and every network case runs behind the asserting adapter.

- **Fixture `upstream_tls_material`** (module scope; `tmp_path_factory`):
  - It follows the `tls_material` openssl pattern: `PATH=os.defpath`, `LC_ALL=C`, `OPENSSL_CONF=os.devnull`, umask 077, a 10 s timeout, and `openssl ca` with `-startdate` and `-enddate`.
  - It asserts that the CLI reports `OpenSSL 3.` and otherwise fails loudly.
  - **CAs** (RSA 2048), each with an explicit `subjectKeyIdentifier=hash`:
    - `upstream-ca`: critical `basicConstraints CA:TRUE` and critical `keyUsage keyCertSign,cRLSign`;
    - `other-ca`: the same;
    - `lax-ca`: `basicConstraints CA:TRUE`, not critical.
  - **Leaves** have critical `basicConstraints CA:FALSE`, critical `keyUsage`, EKU `serverAuth`, SKI `hash` and AKI `keyid:always`, unless the variant says otherwise:
    - `good`: `DNS:jira-upstream.synthetic.invalid`, 23 h;
    - `wildcard`: `DNS:*.synthetic.invalid`;
    - `wrong-name`: `DNS:other.synthetic.invalid`;
    - `cn-only`: no SAN;
    - `ip-only`: `IP:192.0.2.10`;
    - `expired`;
    - `not-yet-valid`, starting in 1 h;
    - `client-eku-only`: EKU `clientAuth`;
    - `no-aki`: `authorityKeyIdentifier=none`, signed by `upstream-ca`;
    - `lax-signed`, signed by `lax-ca`;
    - `other-signed`, signed by `other-ca`;
    - `listener-ca-upstream-name`: SAN `DNS:jira-upstream.synthetic.invalid`, issued by the Forwarder listener CA. It uses the `ca.cnf`, `ca.key` and `service.csr` in B's own module-scoped `material_fixtures.tls_material` directory, with one appended extension section.
- **Context manager `synthetic_upstream(material, leaf="good", *, script, max_tls=None, rcvbuf=None, allow_reset=False, on_sni=None, on_first_byte=None, on_request=None)`:**
  - It binds `("127.0.0.1", 0)` with `_ORIGINAL_SOCKET = socket.socket`, captured at test-module import. This is required because `ephemeral_listener`'s `FixtureSocket.bind` asserts the fixed profile address. `rcvbuf` sets `SO_RCVBUF` on the listening socket before `listen`.
  - **Server-side TLS runs over `ssl.MemoryBIO`** (`SSLContext.wrap_bio`), so the fixture sees every wire byte:
    - `.raw_in` holds every byte received from TCP;
    - `assert_tls_records(raw_in)` parses it as TLS records. Each complete record has content type 20-23, legacy version `0x0301` or `0x0303`, and length at most 16,640. Only a final truncated record is allowed, as a prefix of a well-formed record;
    - plaintext such as `GET ` or `POST` fails the parse.
  - Its server context is `PROTOCOL_TLS_SERVER`, a TLS 1.2 minimum, `num_tickets = 0` (so a client close is a FIN, not an RST), and ALPN `h2` and `http/1.1`.
  - It **never sends `close_notify` and never unwraps.** After responding, it waits for client EOF, then closes.
  - It accepts one connection and records:
    - `.address`, `.accepts`, `.sni`, `.alpn` (the selected protocol) and `.version`;
    - `.captured`: every decrypted post-handshake application byte, read until the request is framed and then until EOF;
    - `.raw_in`;
    - `.eof_kind`: `fin` for `b""` or `SSLEOFError`, or `reset_after_request` for `ECONNRESET` after a fully framed request. `reset_after_request` is accepted only when the case passes `allow_reset=True` (success and response-delivered cases). Every other case requires `fin`, and any other reset is a fixture error;
    - `.tls_errors`, `.events` and fixture errors.
  - `script` is one of: `respond(bytes)`, `stall_until(event)` (reads nothing after the handshake until the event), `head_then_stall`, `close_after_request`, `stall_handshake` or `plaintext`.
  - On exit it joins its worker with a 4 s bound and asserts that the worker left no errors.
- **Context manager `asserting_upstream_adapter(monkeypatch, endpoint, fixture_address, *, client_sndbuf=None)`:**
  - It subclasses the current `socket.socket`, so it layers over `tls_fixtures.ephemeral_listener`.
  - `connect(dest)` behaves as follows:
    - `(endpoint.address, endpoint.port)` is recorded and redirected. With `client_sndbuf`, it first sets `SO_SNDBUF`;
    - `("127.0.0.1", 17441)` passes through to the listener adapter;
    - anything else raises `AssertionError`.
  - `bind` raises `AssertionError`.
  - `socket.getaddrinfo`, `gethostbyname`, `gethostbyname_ex`, `getfqdn` and `create_connection` are replaced with tripwires that record the call and raise. On exit, it asserts that no tripwire fired.
  - It yields `.attempts`.
- **Helpers:**
  - `synthetic_endpoint(material, *, port=443, ca="upstream-ca")`;
  - `synthetic_credential()`, which returns service `jira`, profile `basic` and the golden user and token;
  - `exchange_harness(...)`:
    - builds a real `LeaseRegistry`, `ReceiptLedger` and `DispatchGate` on `time.monotonic`;
    - runs handshake, register, activate and `install_scope` with the unit-12 golden manifest;
    - wires `RoutePolicy(jira=golden_policy())`;
    - reuses `tls_fixtures.ephemeral_listener` and `material_fixtures.tls_material`;
  - `whitebox_tls(material, endpoint)`: a real `ssl.SSLSocket` made with white-box `_build_context` and `wrap_socket(server_hostname=endpoint.host)` through the adapter;
  - `AssertingConnector(real, gate)`, which wraps the real connector and its channel and counts calls:
    - at `connect` entry it asserts that the ledger entry is `connecting`, `gate.is_admitted(admission)` is true, and `G` is free (a helper thread's `gate.snapshot()` returns within 0.5 s);
    - at `send` entry it asserts that the entry is `dispatched`.

**Connector cases**, with a directly built `Admission` and 0.3-2 s deadlines. Every case asserts `assert_tls_records(raw_in)`.
1. **Golden `jira.issue.get`:**
   - `captured` equals the 297 B literal;
   - `sni == ["jira-upstream.synthetic.invalid"]`; ALPN is `http/1.1` although the fixture offers `h2`; TLS is 1.2 or 1.3;
   - `accepts == 1`, and `attempts == [("192.0.2.10", 443)]`;
   - it returns `ParsedResponse(200, IssueBean)`.

   Also: golden search captures the 524 B literal, the 8443 endpoint captures the 302 B literal, and a TLS-1.2-only fixture succeeds.
2. **Zero bytes, each with its positive control:**
   - connect then close: `captured == b""` and `fin`;
   - connect, abort, send, close: `write_failed` from the state check, `captured == b""`, and `_sslobj` still set after abort. This proves the refusal path only; cases 2b and 2c carry the plaintext evidence;
   - send twice: the second raises, and `captured` is exactly one request through EOF.
3. **2b. Abort during a real blocked `SSL_write`** (critic issue 2a):
   - Setup: fixture `stall_until(event)` with `rcvbuf=4096`, and the adapter with `client_sndbuf=4096`. A white-box channel on `whitebox_tls(...)` gets `RequestParts` holding the golden search prefix and a suffix carrying a 65,536-byte body with a matching `Content-Length`.
   - A thread calls `send(deadline=now+5)`. The test asserts it is still blocked 0.3 s later, then calls `abort()` from the main thread.
   - `abort` returns in under 0.05 s. `send` ends `write_failed` within 0.5 s, `_sslobj` is still set, and `bytes_accepted` is less than the total.
   - The event is then set, and the fixture drains to EOF with `allow_reset=True`.
   - `assert_tls_records(raw_in)` passes, and `raw_in` contains no `POST ` and no `Content-Length:`.
4. **2c. Direct send after `_shutdown_fd`** (critic issue 2b):
   - On `whitebox_tls(...)`, call `forwarder_upstream._shutdown_fd(secured)`, then `secured.send(b"GET ")` directly. It raises `OSError` (an `ssl.SSLError` or `BrokenPipeError`), `secured._sslobj is not None`, and the fixture's `raw_in` is TLS-framed with no `GET `.
   - **Control** on a second connection: `ssl.SSLSocket.shutdown(secured2, socket.SHUT_RDWR)` leaves `secured2._sslobj is None`. This pins the CPython behavior the rule depends on and fails loudly if it changes. `secured2.send(b"GET ")` also raises, and its `raw_in` has no `GET `, which shows the kernel barrier independently.
5. **O4 timing and codec:**
   - `_INACTIVITY_LIMIT` monkeypatched to 0.3 with `head_then_stall` gives `receive_failed` in 0.3-1.5 s while the deadline is 5 s away;
   - unpatched, with a deadline of now+0.5, it gives `receive_failed` in 0.4-1.5 s;
   - each of these gives `receive_failed`: a 302 with `Location`, `Transfer-Encoding: chunked`, `application/json;charset=UTF-8`, `Content-Encoding: gzip`, a body over 1 MiB, and `close_after_request`;
   - a 404 JSON returns `ParsedResponse(404, ...)`.
6. **O5/O6 real races:**
   - abort while receive blocks: abort returns in under 0.05 s, receive raises `receive_failed` within 0.5 s, and the fixture sees `fin`;
   - 8 threads race abort and close while receive blocks. A counting wrapper on `ssl.SSLSocket.close`, filtered by object id, sees exactly one call, and no thread raises;
   - close from another thread while receive blocks gives a deferred close and `receive_failed`;
   - 50 concurrent abort/close pairs end with `fileno() == -1`, and no `ResourceWarning` is raised (warnings are treated as errors).
7. **fd reuse** (critic issue 4). Channels are white-box on TLS-wrapped `socket.socketpair()` ends: the client end is wrapped with `_build_context` and the synthetic host, and the server end with the `good` leaf. The handshake runs on a helper thread; no adapter is needed.
   - **Deterministic (abort after close):** close the channel, then open a new socketpair and assert that one end reuses the old fd number. Otherwise the test fails loudly, since POSIX allocates the lowest free descriptor. `abort()` on the old channel returns early on `_closed`, and the new pair still exchanges one byte each way. This proves the closed check, not a race.
   - **Concurrent:** 200 iterations on a 2-thread pool with a barrier. Thread A calls `close()` and immediately opens a new socketpair; thread B calls `abort()`. After both finish, the new pair exchanges one byte each way, and no call raises. When B's abort ran first, the old channel shows `aborted` before `closed`. This is evidence for the window; the lock ordering is the proof.
8. **Trust matrix** (connect only). Each case is paired with the good-leaf control, and every failure has `captured == b""`, `accepts == 1` and a TLS-framed `raw_in`.
   - `wildcard` is accepted (documented).
   - `wrong-name`, `cn-only`, `ip-only` (an IP SAN never substitutes for the name), `expired`, `not-yet-valid`, `client-eku-only` and `other-signed` give `upstream_tls_failed`.
   - `no-aki` and `lax-signed` give `upstream_tls_failed` under the connector. A control `ssl.SSLContext(PROTOCOL_TLS_CLIENT)` with the same `cadata` and no strict flag completes the handshake. This proves `VERIFY_X509_STRICT` is live on the linked OpenSSL. The test fails loudly and never skips.
   - **Anchor only** (critic issue 11d): an endpoint trusting `upstream-ca`, with the fixture presenting `listener-ca-upstream-name` (correct name, listener-CA issuer), gives `upstream_tls_failed`. The good leaf, with the same name and the `upstream-ca` issuer, passes, so only the issuer differs.
   - **Name only:** an endpoint trusting the Forwarder listener CA, with the fixture presenting the `forwarder-jira.maoi.local` listener leaf, gives `upstream_tls_failed`.
   - A plaintext peer gives `upstream_tls_failed`.
   - A handshake stall with the deadline 0.3 s away gives `upstream_tls_failed` within 1 s.
   - Refused TCP (the adapter redirects to a just-closed port) gives `connect_failed`.
   - With `SSL_CERT_FILE` and `SSL_CERT_DIR` pointing at `other-ca`, an `other-signed` leaf is still refused and the good leaf still passes. A `SSLKEYLOGFILE` path is never created.
   - A `_build_context` spy shows that two connects build two contexts.

**Composition cases.** `serve_one` runs on the ephemeral `FixedTLSListener`, with the real connector wrapped in `AssertingConnector` and the real synthetic upstream. `ephemeral_listener` is entered first, then the adapter.
1. **`jira.issue.get` success:**
   - the client gets a byte-exact 200, and the receipt is `TRANSPORT_CONFIRMED`/`ok`;
   - `receipt.request_digest == connector.prepare(routed)`, which equals an independent recomputation from the fixture PEM's DER digests and is not `43d8b478...`;
   - `request_bytes == len(raw)`;
   - the capture equals the 297 B literal;
   - these are all absent from the capture: the inbound sentinel (raw, as `run:<sentinel>` and in base64), the inbound `Authorization` value, `forwarder-jira.maoi.local:17441`, and an inbound `User-Agent` marker;
   - each wrapper call runs exactly once;
   - `on_first_byte` reads `gate.ledger.snapshot()` and `gate.snapshot()`, and it asserts the entry is `dispatched` and the flight is `writing`.
2. **Search success.** An inbound body with whitespace padding and reordered members captures the identical 524 B literal. Absent `fields`, a raw comma or `%2C` all capture the identical 297 B literal.
3. **SNI-callback revocation.** `on_sni` revokes the lease during the real handshake. Result: `FAILED`/`connect_failed`, 502 `forwarder_upstream_failed`, `captured == b""`, zero sends, abort observed, and closeout `quiescent`.
4. **Revocation after the request.** `on_request` revokes after reading the full request. `TRANSPORT_CONFIRMED`/`ok` is delivered while the registry shows the lease revoked.
5. **Response rejections.**
   - An upstream 404 JSON gives 502 `forwarder_response_rejected` with class `4xx`.
   - An upstream 302 with `Location` gives 502 `DISPATCHED_UNKNOWN`/`receive_failed`, and the client bytes contain no `Location` or URL.
6. **Stall with a lease of now+4** and inactivity 0.5: `DISPATCHED_UNKNOWN`/`receive_failed`, delivered before `dispatch_deadline`.
7. **Shutdown during a stall.** `gate.shutdown()` while the upstream stalls fires the attached abort, which gives `receive_failed` and a 502 within 1 s. The next request gets 403 with zero adapter attempts.
8. **Upstream failures.** A wrong-name leaf gives `FAILED`/`upstream_tls_failed`, and refused TCP gives `FAILED`/`connect_failed`, both with zero application bytes.
9. **Denials and closes with zero adapter attempts and zero fixture accepts** (critic issue 11c):
   - `upstream=None`: 403, `NOT_DISPATCHED`/`route_denied`, digest `d25b40c6...`. This is the unavailability proof;
   - an unknown sentinel: client EOF with no response bytes, `closed_without_response`/`sentinel_unknown`, no ledger entry, zero `prepare` and zero `connect`;
   - `SYN-2`: 403, `NOT_DISPATCHED`/`route_denied` with the `jira.issue.get` denial digest `d25b40c6...`, zero `prepare`;
   - a `fields` subset: 400, `NOT_DISPATCHED`/`request_rejected` with digest `d25b40c6...`, zero `prepare`;
   - a lease with 1.5 s left: one `prepare`, then 504, `NOT_DISPATCHED`/`deadline` with the connector's v2 digest (recomputed independently), delivered before `expires_at`, zero `connect`.
10. **Unbuildable request at E7c** (critic issue 3). `RoutePolicy.route` is monkeypatched on the class to return the 2,034-byte-target `replace()` variant from A5, with its recomputed v1 digest. The result is 403, `NOT_DISPATCHED`/`route_denied`, digest `d25b40c6...`, one `prepare` that raises `UpstreamPrepareError`, and zero `connect`, adapter attempts and fixture accepts.

**Tester C** owns `tests/test_forwarder_upstream_adversarial.py`. It reuses B's fixtures by module import, following the existing `tls_fixtures` pattern.
- **AST:**
  - the exact import allowlist, and the forbidden names and stores;
  - every `ExceptHandler` body contains only `Assign`, `AnnAssign`, `Pass` or `Return`. This covers `_close_quietly` and rules out a `raise`, a nested `try` or a call in statement position inside a handler;
  - `_close_quietly` catches `Exception`, never `BaseException` or a bare `except`;
  - exactly one call site each for `SSLContext(`, `wrap_socket(` (with `do_handshake_on_connect=False`), `do_handshake(`, `.connect(`, `.send(` and `load_verify_locations(cadata=...)`;
  - no `recv`, `recv_into`, `read`, `sendall`, `write`, `makefile` or `unwrap` call;
  - `shutdown` appears only in `_shutdown_fd`, via `super(ssl.SSLSocket, ...)`;
  - `_authorization` is loaded exactly twice, both in `_UpstreamChannel.send`: once as the right-hand side of a slice assignment and once as the sole argument of `len`. It is never the value of an assignment to a `Name`;
  - in `BasicCredential.__init__`: every `ast.Raise` is preceded in the same block by `del user, token`; no `re` match result is bound to a name; and no name is assigned from an expression that references `user` or `token`, except the one `object.__setattr__(self, "_authorization", ...)` call;
  - no `Store` to `_CHANNEL_SOCKET_TYPE` outside its definition;
  - `request_descriptor`, `render_parts`, `_wire_lengths` and `prepare` reference no `_credential`, `_authorization`, `time`, `socket` or `ssl`;
  - `connect` and its helpers contain no send or write call.
- **No production caller:** lock 1's repository walk, covering imports, names, string constants and config files. The `ROUTE_CATALOG` states and `policy_readiness_facts()` are unchanged.
- **Secret walk.** A planted user and token marker, searched as str, bytes, base64 and `user:token`, is checked after success and after every failure path through:
  - the reprs and strs of the credential, connector, endpoint, descriptor, parts and channel;
  - every error's args, attributes, `__cause__` and `__context__`;
  - **traceback frame locals** of every frame whose `f_code.co_filename` is under `grafana_jsm_sandbox/`, including the `BasicCredential.__init__`, `connect`, `send` and 13a `forwarder_exchange` frames;
  - `ServeOutcome`, receipts, and the ledger, gate and registry snapshots;
  - `caplog`;
  - the channel slots after send.

  **Walker rules:**
  - The walker is iterative over `gc.get_referents` and frame `f_locals`. It skips modules, classes, code objects and function `__globals__`.
  - It excludes exactly two things: frames outside `grafana_jsm_sandbox/` (the test's own frames and pytest's, which hold the planted inputs), and the identity of the one `BasicCredential` instance, whose slot is the stated custody location.
  - The marker must appear nowhere else. That includes the connector's other attributes, the channel, the `send` frame (its zeroed buffer and its `None` `credential` local) and the `__init__` frame of a refused credential.
- **Exception-chain walk** with a planted marker, for every code in both closed sets and every `UpstreamError` the module raises.
- **Fixture-captured property.** 24 seeded cases (`random.Random(20260923)`) run over real TLS, each captured through two connector instances. Checks:
  - one `Authorization` line, at index 2;
  - the redacted capture equals `reference_render` of the prepared descriptor;
  - both captures are identical;
  - equal v2 digests give identical redacted bytes;
  - `assert_tls_records(raw_in)` passes.
- **Attack lists.** Each of these gives `endpoint_invalid`, with the socket tripwire armed.
  - **Addresses:** `192.0.2.010`, `" 192.0.2.10"`, `192.0.2.10:443`, `[192.0.2.10]`, `::ffff:192.0.2.10`, `2001:db8::1`, `::1`, `127.1`, `0x7f.0.0.1`, `2130706433`, `127.0.0.1`, `0.0.0.0`, `0.1.2.3`, `169.254.169.254`, `224.0.0.1`, `239.255.255.250`, `240.0.0.1` and `255.255.255.255`.
  - **Hosts:** uppercase, `jira..invalid`, `-a.invalid`, `a-.invalid`, a trailing dot, a 64-character label, 254 characters, a single label, an underscore, `localhost`, `x.localhost`, `x.local`, `forwarder-jira.maoi.local`, `192.0.2.10` and a non-ASCII host.
- **Deadline widening.** A connect deadline beyond `admission.connect_deadline` is refused before any socket. A `settimeout` spy never exceeds the clipped remaining time plus 0.01 in connect, send or receive.

**Root** owns this plan file, the docs section and validation:
1. `pytest -q` on the three new files;
2. the focused forwarder command, with the 13a and 13b files appended;
3. full `pytest -q`;
4. `ruff check` on the changed files;
5. `git diff --check`;
6. the four protected dirty-file hashes are unchanged, and ticket-19 C2 is untouched;
7. independent reviewers bind the final hashes, and a module over about 950 lines is a review item;
8. explicit-path staging and one local commit, with no push.

## Judge findings resolved

| # | Finding | Resolution |
| --- | --- | --- |
| J1 | wire-first: `connect` ignored `admission.connect_deadline`; `send` and `receive` were not bounded by `exchange_deadline` | `connect` requires `deadline <= admission.connect_deadline` and clips to `t0 + 5`. The channel carries `exchange_deadline`, and `send`/`receive` refuse a later deadline before any I/O. Test C covers deadline widening. |
| J2 | wire-first: "the Authorization value exists only in the zeroed buffer" is false (an immutable render copy, and a lifetime slot) | Rendering is credential-free (`RequestParts`). The wire is assembled by slice assignment with no intermediate `bytes`, and it is zeroed in `finally`, where the channel also drops its reference. The lifetime slot, OpenSSL buffers and memory zeroing are stated non-claims. |
| J3 | wire-first: no negative proof that `VERIFY_X509_STRICT` is live; no listener-leaf test | `no-aki` and `lax-signed` are rejected, each paired with a non-strict control that accepts. A listener-CA leaf and a listener-name leaf are refused, each isolated. |
| J4 | trust-first: a leak walk through frame locals reaches the token via the channel | The channel drops the credential in send's `finally` and at abort and close. The walker excludes exactly the one `BasicCredential` identity and non-package frames, and it asserts absence everywhere else. |
| J5 | trust-first: invented inputs (a `policy_digest` field, port fixed at 443, TLS 1.2 ciphers, a secret minimum of 16, extra permanent deny ranges) | The endpoint has exactly the sketch fields, the port is 1..65535, there is no cipher policy, and the token is 1..1024 characters. `DENIED_NETWORKS` holds only the sketch categories; the special-purpose ranges fall to the gate (open question). |
| J6 | trust-first: `invalid_deadline` mapped to `deadline` | Only `deadline_expired` maps to `deadline`; every other code gives `receive_failed`. |
| J7 | trust-first: `no-aki` without a positive control; `Accept-Encoding` unflagged | Paired control (J3). Both upstream-only headers are flagged (K6). |
| J8 | contract-first: edits the committed `forwarder_tls.py` | No source module changes. `_build_context` lives in the new module, and the PEM grammar and bounds are duplicated, with a parity test. |
| J9 | contract-first: a flippable `SYNTHETIC_ENDPOINTS_ONLY` bool not bound into any digest; `ca_sha256` hashed PEM text | The closed `ENDPOINT_POLICY` value is bound into the endpoint digest, and no non-synthetic acceptance branch exists. Per-certificate DER `trust_sha256` is sorted and verified against `get_ca_certs`, with a re-encoding test. |
| J10 | contract-first: the upstream fixture's socket class was unspecified | `_ORIGINAL_SOCKET` is captured at import, and the adapter's `bind` raises. |
| J11 | contract-first: a 450-line target is unrealistic | The target is about 950 lines (K10). |
| J12 | contract-first: no `Accept-Encoding` although the codec forbids `Content-Encoding` | Included in `WIRE_PROFILE` v1, and the `gzip` variant is tested. |
| J13 | contract-first: no second-connect guard; no G-free assertion | A `WeakSet` refuses a second connect per Admission before any I/O. `AssertingConnector` asserts `connecting`, `is_admitted` and `G` free at connect, and `dispatched` at send. |
| J14 | wire-first: `prepare` impure (a prepared registry and `prepared_capacity`) | `prepare` is a pure recomputation, and `connect` recomputes and compares. There is no registry. |
| J15 | trust-first: `compare_digest` before hex validation | Both digest inputs are validated as 64 lowercase hex first. |
| J16 | trust-first: a strict handler-body AST rule conflicts with the `_close_quietly` fallback | The fallback is now flag-based (K12), so the strict rule (assign, `pass` or `return` only) is adopted and AST-checked. |
| J17 | trust-first: goldens unverified | Every golden in this plan was recomputed during synthesis with the committed `tagged_digest` and an independent encoder, and the response bodies with `check_response`. |
| J18 | All: TEST-NET described as non-routable | Reworded: reserved for documentation, not guaranteed unroutable. The adapter and the no-caller lock are the guarantee. |
| J19 | All: `forwarder_exchange.py` is not yet in the tree | It now exists untracked, and its names were checked on 2026-09-23. Root still reconciles against the 13a commit. |

## Critic issues resolved (revision 2)

| # | Severity | Issue | Resolution |
| --- | --- | --- | --- |
| K1 | medium | Traceback frame locals leak `user`/`token` from `BasicCredential.__init__`; `send` could bind the slot value to a name | Adopted in full. Checks run on the parameters, and match objects are never bound. There is an arithmetic length bound, and derived values exist only after every check passes. `del user, token` precedes the single raise site. `send` slice-assigns `credential._authorization` directly, and its `finally` sets `credential = None`. AST rules pin both. The walker includes every package frame and excludes only non-package frames and the one credential instance. A4 adds a frame-locals test for every `credential_invalid` path. The non-claim is narrowed to this module's frames, and caller frames are named. |
| K2 | medium | The "no plaintext after abort" evidence was vacuous | Adopted, with a raw tap. The fixture runs TLS over `MemoryBIO`, and `assert_tls_records(raw_in)` runs in every case. B 2b aborts a real blocked `SSL_write` with shrunken buffers. B 2c sends directly after `_shutdown_fd`, with a control pinning the CPython `_sslobj` behavior. The prose now states honestly that the kernel's `SHUT_WR` is the first barrier and the base-class call is defense in depth. |
| K3 | medium | `prepare` did not enforce the render bounds, so an unbuildable request could be admitted | Adopted. `UpstreamDescriptor.__post_init__` enforces the three bounds via the shared `_wire_lengths`, so a successful `prepare` implies a successful render. A5 tests targets of 2,033 and 2,034 bytes through `prepare`, and composition case 10 shows 403 `route_denied` at E7c with zero connects. |
| K4 | low | `_shutdown_fd` caught too little; the constructor socket type was unspecified; the fd-reuse test was trivial | Adopted. The constructor requires `type(sock) is _CHANNEL_SOCKET_TYPE` (`ssl.SSLSocket`), with one documented white-box monkeypatch. `_shutdown_fd` and `_close_quietly` swallow `Exception`. fd reuse moved to B on TLS-wrapped socketpairs: a deterministic case described truthfully as abort-after-close, plus a concurrent barrier case. |
| K5 | low | `send` did not capture its references under the lock | Adopted. Step 1 captures `sock` and `credential` under the lock and refuses if either is `None`. Assembly faults map to `write_failed`. A per-chunk abort check was added. A8 injects an abort between step 1 and assembly through a stub `time`. |
| K6 | low | The `Accept-Encoding` deviation was misstated; `Connection: close` is also outside spec L199-200 | Adopted. Both are listed as upstream-only additions, with `Connection: close` cited to routes Deferred item 3. The spec L167-168 citation is corrected to inbound listeners, and the docs section and open questions updated. |
| K7 | low | The parity test contradicted duplicate rejection; the regex ran before the length check | Adopted. Parity covers grammar, size and count only, and duplicate rejection and the per-DER checks are asserted as deliberate differences. The order is now exact `str`, then non-empty with `len <= MAX`, then fullmatch, then the block count, with a recorder test. |
| K8 | low | The context was not fully read back at runtime | Adopted, with one substitution. The runtime read-back covers options, versions, protocol, verify mode and hostname settings. Python 3.13.7 exposes no `OP_ALLOW_UNSAFE_LEGACY_RENEGOTIATION`, so the check uses the private constant `0x0004_0000` (OpenSSL `SSL_OP_BIT(18)`, verified in the local headers) and a test pins it. A monkeypatched-subclass test proves the read-back is live, and a process-level OpenSSL configuration non-claim was added. |
| K9 | low | `request_descriptor` ordering (`KeyError`) and a loose authority port | Adopted. Short-circuit order: service, then `DISPATCHABLE_SHAPES`, then `ROUTE_CATALOG.get` inside `try` (missing means unavailable), then the permit check. The authority port is `[1-9][0-9]{0,4}`, at most 65535, and never 443. Tests were added. |
| K10 | low | The 600-line target was unrealistic | Adopted: about 950 lines, citing the `forwarder_routes.py` precedent. Exceeding it triggers review, not a split. |
| K11 | low | Several test specifications could not be implemented as written | Adopted. (a) Exact-type refusal uses a recording `str` subclass, plus non-ASCII and chain checks. (b) The success-path zeroing check uses a fake that retains `chunk.obj`. (c) Composition case 9 gives each outcome, status, receipt and digest. (d) The listener cases are split into anchor-only (a listener-CA leaf carrying the upstream name) and name-only. |
| K12 | low | `_close_quietly` contradicted the handler rule | Adopted. It is flag-based, has only assign, `pass` or `return` in handlers, and catches `Exception`. The plan states why interrupts are not swallowed. The handler rule is AST-checked in its strict form. |
| K13 | low | The credential was not bound to service or profile | Adopted. `BasicCredential` gains non-secret `service` and `profile`, validated against `CREDENTIAL_PROFILES`, checked in the connector's `__init__` (`credential_mismatch`) and shown in the redacted repr. No digest changes. |
| K14 | low | Lock 1 missed string-based imports and callers outside the package | Adopted. A repository-wide filesystem walk covers imports, names and string constants in every non-test Python file, plus launch and config files. Deliberately computed names are a stated non-claim. |
| K15 | low | Fixture resets and race-thread counts risked flakes | Adopted. The fixture never sends `close_notify` or unwraps. `ECONNRESET` after a framed request is EOF only with an explicit `allow_reset=True`. The fake race uses 8 persistent barrier-synchronized workers for 200 iterations. |

## Deferred

1. **Reviewed origin and address decision** (spec L441-448). It replaces `synthetic-only.v1` with a new policy value, and every v2 digest then changes. It covers:
   - the real Jira site host;
   - how the address is obtained and pinned: an operator-supplied address, an address set, or a trusted resolver;
   - address churn and IPv6;
   - the permanent status of special-purpose IPv4 ranges.
2. **TLS issuer and renewal decision** (spec L445):
   - which roots form `ca_pem`;
   - whether an intermediate may be pinned, which needs partial-chain trust (banned today);
   - rotation overlap;
   - revocation (OCSP, CRL or stapling).

   Optional hardening: SPKI pinning, CT checks and wildcard refusal.
3. **Operator configuration and credential loading** from sidecar-only mounts: mode 0400, UID 10002, rotation, and readiness that requires readability only by the Forwarder (spec L402-404). This includes the loader's own custody of the strings it reads. The approval record excludes this, so it needs separate authorization.
4. **Supervisor wiring:**
   - build the connector from reviewed configuration;
   - add an accept loop per listener (13a Deferred item 4);
   - wire `Ready(service)` with `tls_not_after`, `policy_digest` and `endpoint_digest`.
5. **Codec tolerance** for Content-Type parameters (`charset`) and bounded chunked decoding (routes Deferred item 4). This is required before any real Jira acceptance.
6. **PARTIAL** classification from the channel's `bytes_accepted` and a progress-reporting collector (13a Deferred item 5).
7. **AuthorizeDispatch permits** bound to the v2 digest: consume at L1 and re-verify at L2, per the 13a permit rule. Prepare-time bounds (K3) keep unbuildable requests from consuming a permit.
8. **Other services' connectors and credential profiles:**
   - a separate Confluence Basic credential with `service="confluence"`;
   - Grafana and Kubernetes Bearer;
   - the Anthropic key with its pinned `anthropic-version` profile and SSE.
9. **Durable ticket-37 and ticket-38 hand-off** of the v2 digest and endpoint digest, plus restart reconciliation.
10. **Real-venue acceptance** under separate authorization:
    - tenant header compatibility (no `User-Agent`, `Accept-Encoding: identity`, `Connection: close`);
    - native-client endpoint and CA configuration;
    - the observed request count and read-back.

## Not qualified by this unit

- Real Jira compatibility, or any tenant or provider call. The committed codec rejects `application/json;charset=UTF-8` and chunked responses, so a real exchange would end `DISPATCHED_UNKNOWN`/`receive_failed`; 13b asserts that rejection.
- The real origin, address, address stability, IPv6, CA issuer, rotation and revocation checking.
- Credential custody on disk or by UID or mount; zeroing Python memory; OpenSSL record buffers; copies held in caller frames outside `grafana_jsm_sandbox/`.
- Process-level OpenSSL configuration (`OPENSSL_CONF`, the `openssl.cnf` `system_default` section) beyond what the runtime read-back observes: cipher suites, groups and signature algorithms are not read back. No test can change library-init configuration in-process.
- C-level resolver behavior beyond the canonical-IPv4 numeric path. The Python-level tripwires do not observe libc.
- Kernel routing: the adapter proves the destination choice only, not the path.
- The `shutdown(2)` wake of a blocked reader or writer. The B 2b and race cases verify it on darwin only.
- The strict-flag variant evidence on any OpenSSL other than the linked 3.0.16. It was not executed during synthesis, which was read-only.
- Lock 1 against deliberately computed module or class names. It guards against accidental wiring, not in-process adversaries.
- Supervisor wiring, readiness, permits, mutation routes, PARTIAL and SSE.
- Any external effect.

**Residual risks the reviewers must accept:**
- **CPython internals.** The second plaintext barrier depends on `SSLSocket.shutdown` clearing `_sslobj` while the base-class shutdown does not. B 2c's control fails loudly if that changes. The kernel barrier does not depend on it.
- **Single I/O path.** The deferred close assumes all socket I/O goes through the channel methods. The single-read and single-send AST rules enforce this, but a future edit could reopen the fd-reuse race.
- **Wildcard acceptance.** Wildcard and long-lived leaves are accepted. A pinned bundle that includes a broad public root widens the accepted issuers; the 16-certificate and 128 KiB bounds limit the issuer but do not decide it.
- **Churn on endpoint changes.** A change to address, trust, revision or policy changes every v2 digest, which churns any correlation that spans a reconfiguration.
- **Conservative send refusal.** A send refused between the fence and the first byte (an abort race, or a between-chunk abort before any byte) records `DISPATCHED_UNKNOWN` although zero bytes were written.
- **Timing.** Integration timing uses the real monotonic clock. Margins are 0.3-1.5 s, and joins are bounded at 4 s, but a heavily loaded CI host can still flake. B 2b additionally relies on 4 KiB socket buffers making a 64 KiB write block, and it asserts the block before aborting.
- **Tickets.** The fixture sets `num_tickets = 0`. Real TLS 1.3 servers send tickets, so the client's close may produce an RST after a complete response. That is harmless, but it differs from the fixture.
- **Private option bit.** `_OP_ALLOW_UNSAFE_LEGACY_RENEGOTIATION` is a hard-coded OpenSSL 3.x bit. A future OpenSSL renumbering would make that one assertion check the wrong bit, and the constant test would not detect it.
