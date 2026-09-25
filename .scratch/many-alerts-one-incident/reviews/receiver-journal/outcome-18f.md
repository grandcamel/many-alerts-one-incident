# Unit 18f accounting candidate syntax outcome

Status: reviewed and locally verified, 2026-09-25. Baseline: `2a901d2`.

The [plan](implementation-plan-18f-candidate-syntax.md) adds a pure parser
for the private version-1 accounting evidence-candidate envelope. It checks
bounded canonical bytes, exact field types, claimed UTC interval syntax and
fixed identifiers. A bounded batch distinguishes exact replay from changed
bytes under one candidate ID. Omitted optional claims remain absent. The
source reads neither payload nor provider and stores no persistent index.

Independent [Standards and Spec reviews](review-18f-source.md) pass. Focused
tests: **31 passed**. Ruff and whitespace checks pass. The [full local
suite](full-suite-18f.txt) passed **5322**, skipped **39**, in 380.55 seconds.
The [validation record](validation-18f.json) binds source, tests, docs and
the suite log after protected-artifact read-back.

This is untrusted metadata syntax only. No profile, source authentication,
payload verification, provider charge identity, opening history, billing
coverage/lag, liability U, archive, continuity witness, reservation writer,
permit or Run caller exists. Provider, native, tenant, venue, paid and
power-loss evidence remain NOT RUN. Ticket 38 stays open.
