# Bounded TLS HTTP receive independent review

## Early contract review

The refactor must make `parse_request_head` the only structural head parser
used by both the collector and `parse_request`. Duplicating request-line,
header, configuration, authorization, target, or query logic risks accepting a
head in transport that the complete-buffer parser rejects. The head parser must
take exactly CRLFCRLF-terminated bytes, derive canonical body length without a
body allocation, and leave opaque body bytes untouched until final parsing.

The collector needs distinct bounds for request line, header region, total
head/body capture, and each `recv` request. It should calculate each next size
as the minimum of the stated chunk limit and remaining-cap-plus-one; retain a
coalesced body prefix; and reject bytes already beyond declared length. It must
not turn a successful exact-length body into a blocking extra-byte probe, since
that would require client half-close and violates the stated protocol boundary.

The original absolute deadline must be checked before and after every receive,
with each temporary socket timeout clipped to remaining time. Validate deadline
and already-handshaken server TLS state before socket claim/read. The permanent
claim marker needs a module-level lock and must remain consumed through every
failure and timeout-restore error; no caller-facing retry can receive later
bytes from that connection.

Timeout restoration needs a three-way outcome: success only after restoration;
a restoration failure after an otherwise successful read must reject with a
fixed error; and restoration failure after an existing parser/I/O/interruption
failure must preserve the original failure without exposing restore details.
The receiver must never send, shutdown, close, or use a raw socket fallback.

## Final hash-bound source and test review

Reviewed shared-parser SHA-256
`8ffb9d8c691833c26a9bedaf47f9b14b43d1550ec8f526a28f42c825b5f8348a`,
collector SHA-256
`fdeedb4400b9bfd0460161c73a29740f93f6c187dd4bcd8a9ae91bf912671a84`,
collector-unit SHA-256
`23c27765217e0430c3e3c7b3e72cf7903581cf8db95cb3821cbe07026e6cdab3`,
head-contract SHA-256
`96190abe59021f81de88562a05a7160ce32b06b9de7309cd10e4051dcc1f7666`,
and root real-TLS integration SHA-256
`7fbfd41a858f23273f58bd99f938451997d72782eea46f2d282a43039640681b`.

Verdict: **PASS (source and test review)**.

`parse_request_head` is the shared structural path: complete parsing obtains a
validated head through it, then enforces opaque body length exactly. The head
result carries only a declared body length, so a maximum declaration does not
allocate a dummy body. Request line and header limits are independently checked
and all configuration, header, target/query, and credential grammar remains
the same parsing logic.

The collector claims an exact already-handshaken server-side TLS socket before
reads, never closes/sends/shuts it down, and permanently consumes the marker on
failure. It calculates every header/body `recv` size from the applicable cap
plus one, preserves a coalesced body prefix, rejects captured excess before a
further read, and does not probe for a later byte after exact completion. Every
read shares the caller absolute deadline with pre/post clock checks and timeout
clipping. The final deadline check runs after timeout restoration; restoration
cannot produce a false success or mask a prior receive/interruption failure.

The inspected tests cover fragmented/coalesced and opaque bodies, line/header/
body exact limits, EOF, oversized receive return, invalid heads before body
reads, absolute deadline slow drips and regression, concurrent and permanent
claims, restore-failure precedence, final post-restore timing, real-TLS
fragmentation, captured pipelining, malformed/stalled input, and EOF. The
remaining documented limit is intentional: it cannot detect bytes arriving
after a successful exact-length collection or in a later unread TLS record;
the consumed marker and required caller close prevent reinterpreting them.

Static checks run by this reviewer (`python -m py_compile`, `ruff check`, and
`git diff --check`) passed for the reviewed files. The root reported 157 focused
tests passing in 2.52 seconds (104 existing parser, 12 head, 29 collector unit,
and 12 real TLS); that runtime evidence is root-owned and was not rerun here.
Full-suite evidence remains root-owned. No source/test edit, network/native/
provider, credential, C2, commit, or push activity was performed by this
reviewer.

## Server-TLS Darwin handshake corrective review

Reviewed correction source SHA-256
`91efea3ccbafbe5ecb2a86fcfe7f52c25f4c2d2ebe235f6b727f8ade4d0cc5f8`
and unit-test SHA-256
`3cb3b42f19289fd65cbc637aee5c67613a1e6d3c7a6cb968572d705e71661010`.

Verdict: **PASS (source and test review)**.

The correction turns each handshake attempt nonblocking, polls only the
readiness direction requested by `SSLWantReadError` or `SSLWantWriteError`, and
runs `select` outside the state lock. A concurrent close can therefore acquire
the lock, close the retained in-flight descriptor, and make the next handshake
loop observation fail closed. The same original accept deadline is checked
before every attempt and readiness wait; waits are clipped to 100 ms and the
remaining budget. A fatal SSL error does not enter the readiness poll or retry
loop.

The added unit tests cover WANT-read/WANT-write directions, no state-lock hold
across readiness polling, deadline clipping, fatal no-retry behavior, and a
close during a blocked readiness wait with eventual cleanup. Static
`py_compile`, Ruff, and baseline diff checks passed. The earlier full-suite
failure is documented as the pre-fix Darwin blocking-handshake observation;
focused and full-suite execution of this correction remain root-owned and were
not rerun here.
