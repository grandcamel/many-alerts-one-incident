# Common HTTP request boundary outcome

2026-09-22. PASS for the separately authorized local application unit, baseline
4e1b206. This unit is local only; no push or planning-ticket closure.

`parse_request` validates one complete, bounded HTTP/1.1 request buffer and
returns immutable request structure with a parsed service sentinel. It rejects
ambiguous framing, unsafe path aliases, unknown/duplicate headers, mismatched
fixed Host or Accept, noncanonical Basic/Bearer tokens and unapproved query keys.
The body remains opaque bytes for later route validation. The result excludes
path, query, body and sentinel from repr and retains no raw headers.

Two Terra workers implemented source and unit tests. A separate Terra worker
provided [independent source/test review](review.md); root reviewed the module
and added adversarial tests plus composition with the existing lease registry.
Root tests caught and corrected a real early defect: newline validation scanned
the body and rejected pretty-printed JSON. Validation now stops at the header
boundary. Duplicate slash rejection is path-only, preserving URL-valued query
text, and Content-Length is bounded before numeric conversion. A pre-fix
adversarial run reported 1 failure and 51 passes; all final validation below
includes the correction and expanded coverage.

Validation on frozen hashes recorded in [validation.json](validation.json):

- [Focused suite](focused-tests.txt): **104 passed in 0.27s**, exit 0.
- [Full suite](full-suite.txt): **1190 passed, 36 skipped in 145.25s**, exit 0.
- Ruff, compile and whitespace checks passed; independent review PASS.
- Exact line/header/body caps, each service grammar, base64 pad-bit variants,
  every truncated request prefix, forbidden headers, noncanonical lengths,
  structural control bytes, captured pipelining and path/query alias cases.
- Local lease composition confirms parsing does not activate a registered
  lease, broaden service/scope, survive a generation change or restore a
  revoked lease. A lease check remains an observation, not atomic dispatch.

This is a deliberately narrow complete-buffer profile, not a general HTTP
server or verified native ClientProfile. No sockets are opened by the parser.
Future transport must cap collection, enforce TLS/deadlines, close after one
request and prevent later bytes becoming another request. Route policy must
select trusted parser settings, validate body/query semantics and coordinate
lease checks with dispatch. Native clients, fixed server binding, protected
credential custody, deployment and human Report acceptance remain unqualified.

The four protected dirty artifacts remain unchanged and outside this commit.
No C2 retry, provider/tenant request, paid experiment, actual credential access,
native client execution or deployment occurred. Ticket 36 retains its separate
planning scope. No additional user approval is needed for the next local unit.

Next implementation: fixed server TLS and bounded receipt, request-specific
policies and dispatch checks, followed by durable Receiver/recovery/accounting.
