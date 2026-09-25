"""Pure, descriptive Run execution assessment under ADR 0012.

Inputs must come from a future Receiver-owned sanitized observation path. This
module neither authenticates their origin nor confirms external effects, and
its result cannot authorize launch, retry, a budget release or an OPS write.
"""

from dataclasses import dataclass

_SPAWN_STATES = frozenset({'accepted', 'failed_before_process', 'unknown'})
_CONTAINMENT = frozenset({'confirmed', 'failed', 'unknown'})
_SUBTYPES = frozenset({'success', 'error'})
_USAGE_STATES = frozenset({'known', 'absent', 'malformed'})
_HEX = frozenset('0123456789abcdef')


class OutcomeError(ValueError):
    """A fixed rejection code without observation details."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProcessFacts:
    spawn_state: str
    exit_observed: bool
    exit_code: int | None
    exit_signal: int | None
    timed_out: bool
    cancelled: bool
    containment: str


@dataclass(frozen=True, slots=True)
class TerminalFacts:
    subtype: str
    is_error: bool
    reason: str | None
    usage_state: str
    evidence_digest: str


@dataclass(frozen=True, slots=True)
class ExecutionAssessment:
    state: str
    reasons: tuple[str, ...]
    usage: str
    never_started: bool


def _process_valid(facts: object) -> bool:
    if type(facts) is not ProcessFacts:
        return False
    if (type(facts.spawn_state) is not str or facts.spawn_state not in _SPAWN_STATES or
            type(facts.containment) is not str or facts.containment not in _CONTAINMENT or
            type(facts.exit_observed) is not bool or type(facts.timed_out) is not bool or
            type(facts.cancelled) is not bool):
        return False
    code = facts.exit_code
    signal = facts.exit_signal
    if facts.exit_observed:
        code_valid = type(code) is int and -(2**31) <= code < 2**31 and signal is None
        signal_valid = type(signal) is int and 1 <= signal <= 64 and code is None
        if not (code_valid or signal_valid):
            return False
    elif code is not None or signal is not None:
        return False
    return not (facts.spawn_state == 'failed_before_process' and
                (facts.exit_observed or facts.containment == 'failed'))


def _terminal_valid(facts: object) -> bool:
    if type(facts) is not TerminalFacts:
        return False
    if (type(facts.subtype) is not str or facts.subtype not in _SUBTYPES or
            type(facts.is_error) is not bool or
            type(facts.usage_state) is not str or
            facts.usage_state not in _USAGE_STATES or
            type(facts.evidence_digest) is not str or
            len(facts.evidence_digest) != 64 or
            any(char not in _HEX for char in facts.evidence_digest)):
        return False
    if facts.reason is not None and (
        type(facts.reason) is not str or len(facts.reason) > 64 or
        any(not 0x20 <= ord(char) <= 0x7E for char in facts.reason)
    ):
        return False
    if facts.subtype == 'success' and facts.reason:
        return False
    return (facts.subtype == 'error') == facts.is_error


def assess_execution(
    process: ProcessFacts, terminals: tuple[TerminalFacts, ...]
) -> ExecutionAssessment:
    """Derive execution only; effects and billing remain separate unknowns."""
    if not _process_valid(process):
        raise OutcomeError('process_invalid') from None
    if type(terminals) is not tuple:
        raise OutcomeError('terminal_invalid') from None

    reasons = set()
    never_started = process.spawn_state == 'failed_before_process'
    if process.containment == 'failed':
        reasons.add('containment_failed')
    elif process.containment == 'unknown' and not never_started:
        reasons.add('containment_unknown')
    if process.timed_out:
        reasons.add('timeout')
    if process.cancelled:
        reasons.add('cancelled')
    if never_started:
        reasons.add('spawn_failed')
    elif process.spawn_state == 'unknown':
        reasons.add('spawn_unknown')
    if not process.exit_observed and not never_started:
        reasons.add('exit_missing')
    elif process.exit_signal is not None:
        reasons.add('signaled_exit')
    elif process.exit_code is not None and process.exit_code != 0:
        reasons.add('nonzero_exit')

    terminal = None
    if not terminals:
        reasons.add('missing_terminal')
    elif len(terminals) != 1:
        reasons.add('duplicate_terminal')
    elif _terminal_valid(terminals[0]):
        terminal = terminals[0]
        if terminal.is_error:
            reasons.add('result_error')
        if terminal.usage_state == 'malformed':
            reasons.add('usage_malformed')
    else:
        reasons.add('terminal_invalid')

    if reasons & {'containment_failed', 'containment_unknown'}:
        state = 'containment_failed'
    elif reasons & {'timeout', 'cancelled'}:
        state = 'cancelled'
    elif reasons & {'spawn_failed', 'result_error', 'nonzero_exit', 'signaled_exit'}:
        state = 'failed'
    elif reasons:
        state = 'incomplete'
    else:
        state = 'succeeded'
    usage = 'known' if terminal is not None and terminal.usage_state == 'known' else 'unknown'
    return ExecutionAssessment(state, tuple(sorted(reasons)), usage, never_started)


__all__ = ['ExecutionAssessment', 'OutcomeError', 'ProcessFacts', 'TerminalFacts',
           'assess_execution']
