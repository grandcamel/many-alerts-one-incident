# 19d worker supervision boundary

Status: proposed local source design, 2026-09-25. Fixed point: `e376ec1`.
Authority: ADR 0012, ticket 37, the pure 19c deadline policy, and ticket 23's
fixed synthetic process fixture. This design starts no Run and grants no
reservation, sentinel or dispatch authority.

## Handoff into supervision

A future guarded launcher owns creation. The supervisor receives one created
but not yet released process handle, an expected same-boot launch time, its
exact process-group identity and an opaque attempt identity from a verified
launch claim. The launcher needs an inherited startup barrier that prevents
child code and any external action until the parent verifies session/group
leadership, revocable lease scope and supervisor attachment. Failed
attestation requires closed containment and no child release. Plain
`Popen(start_new_session=True)` has no such barrier; the legacy spawner and
fixed fixture cannot satisfy this production ordering. The repository has no
permit or guarded startup path, so a production caller is deferred. A local
unit may exercise a closed synthetic Python fixture through a test-only
adapter, with no native client, provider or OPS route.
Never pass a caller-selected shell command, environment, endpoint or process
group into a production supervisor API.

Do not infer safe group identity from the parent's exit code. A numeric PGID
and `killpg(..., 0)` do not distinguish the original group from a recycled
identity after root reap. Production confirmation needs an independently
verifiable stable containment identity across root exit; otherwise group
absence remains unknown and dispatch held. A missing, recycled, escaped or
unverifiable group is a containment gap. A parent reaped while descendants
retain stdout/stderr is still a live/incomplete worker until group absence and
pipe EOF are independently observed. An EOF caused by locally closing a pipe
is not observed child EOF. A permission error querying the group is unknown,
not absent. OS group membership is not a hostile-process confinement proof;
venue isolation remains an acceptance gate.

## Ordered bounded actions

Use 19c with one sampled monotonic boot. Poll timers independently of output;
silence and new output neither pause nor reset deadlines. At the earlier of a
stop request and launch+270 seconds, request Forwarder sentinel revocation
before SIGINT to the verified group. On clean early completion, failed spawn,
failed startup attestation or any exception, retire any installed lease before
successful closeout. Every exit path records whether revocation was confirmed.
Revocation must have an observable acknowledgment or a closed
`revocation_unknown` hold. The supervisor may still
signal for containment if revocation fails; it must not claim that any new
upstream dispatch was fenced. At the 19c flush boundary, send SIGKILL to a
still-live verified group and begin bounded reap. At the hard boundary, stop
waiting, retain the actual root/group/pipe observations and mark containment
unconfirmed if any are missing. No timer or journal failure extends authority.

Every signal request, syscall result, root exit/reap observation, group probe,
pipe EOF and closeout failure is distinct sanitized evidence. `killpg` success
means only that the signal request was accepted; it does not prove descendants
are gone. Signal/probe errors are fixed codes and cannot be converted to a
clean exit. Once an action is attempted, repeat sampling may observe state but
must not repeatedly issue the same signal. Revocation and signal callbacks
must be bounded; a blocking callback cannot consume the 300-second budget
without a hold. Recovery after supervisor death has no process-absence proof
from an absent local handle and must hold until a separate orphan inspection.

Revocation acknowledgment is not Forwarder quiescence. Capture the gated
Forwarder's `closeout_state`, lease state, pending/in-flight/overdue/uncertain
counts, drain deadline and fixed error/unknown reason separately. A `draining`
lease remains an unresolved closeout; overdue, inconsistent or unknown
closeout holds even when revocation was acknowledged. After EOF or control
replacement, poll `closeout` through a new current session before claiming
quiescence. The future Receiver records these observations in the durable
handoff and does not relax a Run or effect hold on a stale/replaced session's
answer. No local process or policy test can establish Forwarder closeout.

Stream capture must be nonblocking and bounded in memory, per stream and in
total. Preserve byte counts, digest, truncation/loss markers and actual EOF
separately; never treat a truncated terminal prefix as a valid terminal
record. Do not log raw output or stderr by default. Capture/audit custody is
ticket 39's separate private bound, not this supervisor's ordinary telemetry
buffer. A malformed stream or capture failure holds outcome evidence but does
not skip containment cleanup.

## Result and acceptance

Return a frozen observation containing launch/stop/action timestamps,
root exit and reap status, group-absence observation, pipe EOF flags,
capture completeness, revocation/Forwarder closeout state and fixed gaps.
It is input to `run_outcome`, not an
execution verdict by itself. The future Receiver must durably append the
sanitized observation before relaxing any Run hold. Failed journal append
leaves dispatch held and cannot turn local process observations into a durable
success. No effect confirmation or billing settlement follows from process
containment.

Local acceptance needs fixed synthetic success, nonzero exit, early stop,
silent worker, ignored SIGINT, parent exit with descendants retaining pipes,
capture overflow, revocation failure, signal/probe failure and cleanup-gap
cases. Include early successful and failed-start paths with installed leases;
both must retire the lease before any clean closeout. Exercise draining,
overdue and unknown Forwarder closeout separately from revocation. Verify
root/group/pipe distinctions and no action after hard deadline.
These are local process tests, not native-client, provider, tenant or intended
venue acceptance. The 19c pure policy remains the timing source; do not add
a second drifting deadline formula.
