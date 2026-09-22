# Bounded TLS response receive independent review

## Early contract review

The response head parser must be the exact structural source for both full
parsing and collection. It needs to return only status and canonical declared
body length, so maximum-length declarations do not allocate a body. Preserve
the response codec's headerless-204 path and the separate 205 framing state;
any independent status/header/Connection grammar in the collector risks a
transport/full-parser disagreement.

Collection should publish the permanent socket claim before any read, validate
the client-side TLS state/configuration before using the socket, and never
confuse those local checks with proof of fixed-origin identity, route success,
lease state, receipt, or effect. The trusted caller still owns origin/trust
attestation and eventual close/uncertain-effect handling.

Use the one caller deadline through every bounded read: status/header reads are
at most 4096 and region-cap-plus-one, body reads at most 65536 and
remaining-plus-one. Retain coalesced body bytes, reject captured excess before a
new read, parse a completed head before waiting for body, and never probe for
EOF/extra bytes after exact completion. The documented later-record limitation
must remain explicit.

Timeout restoration must happen before return and be part of deadline
observation. A restore failure after success rejects; one after an existing
parser/I/O/interruption failure cannot replace that failure. The collector must
not send, shutdown, close, reconnect, or retry an SSL WANT/error.

Final source/test hash-bound review is pending. No source/test edit, full-suite,
network/provider/native, credential, C2, commit, or push activity was performed
by this reviewer.

## Final hash-bound source and test review

Reviewed shared response-codec SHA-256
`8f88b84438563fb14e019a999377008a5a65413e20add61564814e2095420bb9`,
collector SHA-256
`e9c5e7da25ae061ece41c2e3e0d72ddb811c57923591922476f3733f00c217ae`,
deterministic-test SHA-256
`3eb451cf3378d034348d0a41501600af1e5962cb6f45657cfb275a762fce2065`,
adversarial-test SHA-256
`751c0e416bc1a1a09bd0e92e625f9983c44e3d39191f796e899a0611dc88f009`,
and real-TLS integration SHA-256
`8457bd786115a81679584600039c9e3826fc466a766c9aad90234394a1e02ab0`.

Verdict: **PASS (source and test review)**.

The pure codec has one shared `parse_response_head` path for head and complete
parsing. It preserves the headerless-204 and exact-205 states, derives a
bounded body length without allocation, and makes full parsing enforce the
opaque body's exact declared length. The collector validates an established
client-side TLS transport and permanently claims it before reading, without
mistaking that local configuration check for fixed-origin identity, upstream
success, receipt, lease, or route authority.

Every status/header and body read is bounded by its region/body cap plus one and
by the original deadline. Per-read timeout is clipped to the lower of 20
seconds and remaining deadline; post-read inactivity, pre/post-read deadline,
pre-restore, and post-restore monotonic observations fail closed. The code keeps
coalesced body bytes, rejects captured excess before another read, has no EOF
probe after exact completion, and preserves primary parser/I/O/interruption
errors if timeout restoration also fails. It never sends, closes, shuts down,
reconnects, retries, or releases the consumed socket marker.

The inspected tests cover shared-head equivalence, headerless 204 across every
fragment boundary, 205, maximum declarations/body, header/status caps,
fragmentation/coalescing, opaque bytes, EOF/oversize/extra capture, 20-second
late completion, absolute deadline slow drips/regression, client TLS-state
matrix and ALPN, permanent/concurrent claims, restore-error precedence and
post-restore clock checks, then real local-TLS success and rejection cases.
The root reported 39 deterministic and 15 real-TLS tests passing; its combined
focused/full-suite execution is separate and was not rerun here.

The intended limitation remains: late bytes outside the captured TLS reads or
in later unread records cannot be detected. The socket remains consumed and
caller-owned; a later owner must close it and determine receipt/effect state
from dispatch context. This code is not response transport, receipt-before-send,
route policy, native compatibility, or external-effect acceptance. No
source/test edit, full-suite, network/provider/native, credential, C2, commit,
or push activity was performed by this reviewer.
