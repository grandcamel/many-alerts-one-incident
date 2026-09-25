# Ticket 44a local audience status policy plan

Status: source plan, 2026-09-25. Baseline: `af1988b`.

Authority: ADR 0018 and ticket 44's accepted operator-audience contract. This
unit consumes already validated, sanitized status inputs. It cannot authenticate
a source, redact arbitrary text, authorize a user, render a dashboard, or publish
an approved reference.

1. Add a pure module for section freshness from caller-supplied controlled
   monotonic samples. More than 30 seconds since a successful refresh is stale;
   missing or discontinuous clocks, including changed epochs, are unknown.
   Never advance source observed
   or verified times from a cache refresh.
2. Add count qualification: only an explicitly confirmed complete source count
   may display an integer, including zero. Missing, failed, truncated or
   unverified sources show unknown with a stable gap reason.
3. Add a pinned-reference policy: a historical pin retains its captured state,
   while a separately supplied current overlay controls current use. Missing,
   mismatched, unverified, changed-version, revoked, withdrawn, expired or
   correction-required overlays cannot show current approval. Exact verified
   current approval can show approved status without mutating the pin.
4. Test threshold edges, clock failure, source-verification independence,
   zero/missing/truncation, revocation after pinning, changed identity/version,
   and immutable results. Update ticket 44 and a short module contract.
5. Run focused tests, Ruff, independent Standards and Spec reviews, protected
   dirty-file read-back, and the full suite before a local code commit. Stage
   only named ticket-44a files.

The future actual projection/parser, operator access isolation, redaction,
snapshot store, source joins, UI/accessibility and presenter acceptance remain
separate work. Synthetic policy tests are not source or tenant acceptance.
