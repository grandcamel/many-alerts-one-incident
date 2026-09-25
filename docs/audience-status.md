# Operator audience status policy

`audience_status.py` implements three pure ticket-44 decisions over already
validated, sanitized inputs. It has no source reader, redactor, snapshot store,
network route, UI, operator authentication or Run-visible interface.

`section_freshness` uses caller-supplied controlled monotonic nanoseconds. A
section is stale only after more than 30 seconds without a successful refresh;
missing, malformed or discontinuous clock values, including a changed clock
epoch, are unknown. The caller must supply stable, validated clock epoch IDs
from its controlled clock. Source observation
and verification times are separate and cannot be advanced by a cache refresh.
Callers must also show source failures and last verified time independently.

`qualified_count` displays a number, including zero, only when the source
explicitly confirms a complete count. All other states retain a reason and an
unknown value. It makes no quality or diagnosis claim.

`pinned_reference_status` preserves the captured historical approval label but
requires a separately verified current overlay with matching source identity,
version and body digest for current approval. Revocation, withdrawal, expiry,
correction, missing or unverified overlays cannot restore approval from a pin.
The caller must obtain the overlay from the authoritative reference owner and
must prevent revoked material from being served to a Run.

These synthetic policy checks are not acceptance of source joins, source
authorization, privacy redaction, rendering, access isolation or presenter
behavior. Ticket 44 remains open.
