# 16a outcome: pure ADF byte preflight

Status: reviewed local source and synthetic verification, 2026-09-25.
The [design](design-16a-adf-preflight.md) pins the intentionally narrow ADF
subset drawn from ticket 16's synthetic example. The new pure codec accepts
only a version-1 document containing heading-level-2 or paragraph blocks,
each with one text node. It returns canonical UTF-8 bytes, measured byte count
and external SHA-256 digest; 2,048-byte text and 8,192-byte document limits
are enforced before any Jira request is formed. Noncanonical input,
unsupported nodes/marks and malformed JSON fail closed.

Independent Spec and Standards source reviews pass. A Standards finding on
hostile Python values and pre-serialization bounds was fixed and re-reviewed.
The first full suite exposed the existing parser architecture gate that
reserves `max_string_bytes` for journal ingress; 16a now enforces its own
text bound. The focused ADF and architecture tests passed **41 tests**;
Ruff and `git diff --check` passed. The final full local suite passed
**5,644 tests, 39 skipped in 400.49s**.

The proposal's literal ADF example is parsed as strict JSON, canonicalized,
then decoded; its original key order is correctly rejected by the canonical
decoder. A local file/stdin-equivalent fixture verifies exact bytes and hash.
This is a serialization fixture, not a Report builder, revision store,
citation validator, Jira body adapter, delivery, effect receipt or human
grade. Native, provider, tenant, paid, venue and human acceptance are
**NOT RUN**. Ticket 16 remains open.
