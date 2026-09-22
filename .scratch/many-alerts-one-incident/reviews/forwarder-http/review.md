# HTTP boundary independent review

## Early contract review

The proposed boundary is appropriately narrow: it consumes exactly one bounded
complete buffer and does not claim transport completeness, route authorization,
lease authority, or dispatch capability. A future transport must close after a
single request; this parser cannot defend against bytes that arrive after the
captured buffer.

Implementation and adversarial coverage must preserve these contract details:

- Compare header names case-insensitively before duplicate detection. Apply the
  narrow allowlist after that normalization, while retaining no raw headers.
- Split framing only on CRLF and reject bare LF/CR, folded lines, missing final
  blank line, additional header delimiters, mismatched length, and every byte
  after the declared body. Check total input length before any decode or copy.
- Treat target validation as a canonicalization boundary. Do not use URL parser
  normalization; preserve an allowed percent escape in the returned path, deny
  escaped unreserved characters and structural aliases, and reject a decoded
  query-key collision before constructing the tuple.
- Basic and Bearer schemes must have exact spelling and one separator. Decode
  only a bounded canonical representation, re-encode byte-for-byte, and ensure
  all parser errors suppress both exception chaining and credential text.
- Validate trusted configuration even for a request without a query: exact
  `frozenset`, bounded count/name length, only unreserved names; expected Accept
  must be the service-compatible fixed profile. Keep complete-buffer memory and
  query-pair/value work bounded by the stated global limits.

## Final hash-bound source and test review

Reviewed source SHA-256
`8ea326995573a737c25f2766479fc5854cd327c72ce12fc88e1367f0632d0b24`,
unit-test SHA-256
`60d5be41ee276816a36d46936e138f523ea34f985ce9a7116809fbfa3e8dee1f`,
and root adversarial-test SHA-256
`183cd34452cb1d14ef0fb566302e02e76f5041aa7391f575c00446b777830ff5`.

Verdict: **PASS (source and test review)**.

The implementation follows the narrow profile. It bounds input before decode,
enforces a single CRLF-framed request with exactly bounded header/body regions,
normalizes header names only for duplicate/allowlist checks, and never retains
raw headers. It validates body framing against canonical Content-Length and
therefore rejects trailing/pipelined bytes in the complete buffer.

Target and query handling avoids a URL normalizer: it preserves only permitted
path escapes, rejects structural/unreserved aliases, uses exact unreserved keys,
and percent-decodes only query values under pair/global bounds. Credential
schemes, Basic re-encoding, Bearer spelling, token length, and base64url pad-bit
canonicality are all checked before the sentinel is returned. Errors have one
fixed nonsecret code/message and suppress exception chaining.

The inspected adversarial coverage includes all truncated prefixes, canonical
pad-bit variants, framing suffixes, header controls, path/query aliases,
credential/result redaction, and a lease composition check that confirms parser
success does not grant authorization. The final test revision also covers
forbidden transport/credential headers, noncanonical Content-Length forms,
all accepted body methods, exact query-pair limits, a pretty-printed JSON body,
and query values containing slash sequences. It deliberately does not turn this
complete-buffer parser into a transport implementation.

Static checks run by this reviewer (`python -m py_compile`, `ruff check`, and
`git diff --check`) passed for the reviewed files. The root reported 104
focused public/adversarial tests passing in 0.49 seconds; that execution is
root-owned and was not rerun here. No HTTP server, network/native/provider,
credential, C2, full-suite, commit, or push action was taken by this reviewer.
