# One Incident per Fault, and the Match is the Run's judgment

Status: accepted, 2026-09-15, while charting the many-alerts-one-incident map. Partially supersedes ADR 0004.

Chapter one keyed Incidents by one Alert's Fingerprint, so one Alert was one Incident and the Match was an exact label lookup (ADR 0004). This effort's demo is the opposite motion: many Alerts from one Fault become the one Incident a responder acts on, with a suggested root cause. We decided that an Incident represents one Fault's lifetime and carries the Fingerprint of every Alert it explains, and that the Match is a judgment the Run makes against the open Incidents rather than a lookup. The alternative, one Incident per Alert as before plus one Problem linking them, keeps ADR 0004 intact but puts a whole Cascade of Incidents in the queue, which is the alert fatigue the demo argues against, and moves the reduction out of the model, which is the demo's claim.

## Consequences

- A Run can be wrong: an Alert filed under the wrong Incident, or a second Incident opened for a Fault that already has one. The map's ticket "Many-to-one under a Cascade" decides the rule a Run judges by, what it reads to judge, and what happens when it judges wrong. Until then this ADR records the shape, not the mechanics.
- An Incident now spans several Runs. Its Report grows as later Alerts of the same Cascade land; the first Run's Report is a partial one by design.
- The Fingerprint label stays, one per Alert explained, so that an Incident can still be found from any of its Alerts and chapter one's search-by-label keeps working on the Alerts it covers.
- Problem stays reserved for recurrence, as chapter one left it.
