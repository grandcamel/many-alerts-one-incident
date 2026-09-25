# Run worker supervision reducer

`run_supervision_reducer.py` is a pure decision layer for ticket 37. It takes
caller-supplied action history and sanitized worker observations. It uses
`assess_supervision` for the 270-second work, 20-second flush and 300-second
hard boundaries. It emits at most one due action per step: lease revocation,
then SIGINT, then SIGKILL for a still-present verified group. It never repeats
an attempted action or emits a new one at or after the hard boundary.

An early root exit or failed-before-process observation calls for lease
revocation. If descendants may remain after an early parent exit, the decision
also returns `early_stop_to_record_us`. The caller must retain that exact
observed timestamp in action history with the revocation attempt. A subsequent
step that omits it is rejected. The existing 19c flush and hard deadlines then
apply from the pinned early stop.
Failed or unknown revocation does not fence Forwarder dispatch, though a
verified group may still be signaled for containment.

Closeout keeps root reap, stable group identity and absence, actual stdout and
stderr EOF, capture completeness, revocation acknowledgment and Forwarder
closed state separate. Missing facts produce fixed gaps. `claimed_complete`
means only that the supplied observations are structurally complete. The
future Receiver must authenticate them and durably append them before any Run
hold can be relaxed. Physical startup barrier, stable group handle, bounded
callbacks, nonblocking capture and current Forwarder closeout are separate
integration work.

The module starts no process, executes no signal, reads no credential and
creates no dispatch permit. The synthetic tests are local policy evidence;
native-client, provider, tenant, venue and power-loss acceptance remain open.
