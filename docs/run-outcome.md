# Local Run execution assessment

`grafana_jsm_sandbox.run_outcome.assess_execution` is a pure classifier for
bounded, sanitized Receiver observations. It applies ADR 0012's precedence:
unconfirmed containment, then Receiver cancellation/deadline, then reported or
observed failure, then incomplete evidence. A clean exit and one valid success
terminal with confirmed containment are required for `succeeded`.

The input is `ProcessFacts` plus a tuple of `TerminalFacts`. Invalid process
facts raise the fixed `process_invalid` code. An invalid, missing or duplicate
terminal makes execution incomplete unless an earlier Receiver observation
already determines the result. Missing usage remains `unknown`, never zero;
malformed usage is incomplete evidence. A trusted pre-process spawn failure
sets `never_started`, while an unknown spawn gap never does.
Any nonempty reason on a claimed success is conflicting terminal evidence;
the classifier does not parse free-form reason text into an error category.

This module does not parse the native client's Transcript or authenticate
who supplied the facts. It returns no effect confirmation, budget settlement,
reservation, retry or launch permit. No application caller uses it yet. A
future Receiver/journal unit must bind each observation to verified local
evidence, and a separate effect unit must verify Forwarder correlation and
OPS read-back before claiming an external write. The legacy spawner and
admission-only front door are unchanged. Provider, model, tenant and intended
venue behavior remain untested.

`run_supervision_policy.assess_supervision` separately computes the due
270-second work, 20-second interrupt/flush and 10-second kill/reap boundaries
on one caller-supplied monotonic boot. An earlier observed stop shortens both
cleanup windows and never extends the original 300-second bound. Its booleans
say which actions are due; they do not prove a sentinel was revoked, a signal
was delivered, or a process group was reaped. Cross-boot or malformed times
raise fixed errors for a future caller to hold. There is no process caller or
dispatch decision in this local policy.
