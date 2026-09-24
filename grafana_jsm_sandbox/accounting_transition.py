"""Pure accounting history transition and replay; never a durable receipt."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from .accounting_events import (
    ZERO,
    AccountingEvent,
    AccountingEventError,
    decode_event,
)
from .accounting_policy import (
    Attempt,
    Candidate,
    Exposure,
    HypotheticalProposal,
    Lifecycle,
    NonModelCost,
    Profile,
    Snapshot,
    Week,
    evaluate_reservation,
)


class AccountingTransitionError(ValueError):
    """A fixed transition refusal without caller data."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _check(ok, code='transition_invalid'):
    if not ok:
        raise AccountingTransitionError(code)


def _stamp(value):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=UTC)


def _profile(value):
    return Profile(value['model_id'], value['auth_id'], value['venue_id'])


def _week(value):
    return Week(value['key'], _stamp(value['start_utc']),
                _stamp(value['end_utc']), value['timezone'])


@dataclass(frozen=True, slots=True)
class LifecycleOrigin:
    lifecycle: Lifecycle
    journal_origin: tuple[str, int]


@dataclass(frozen=True, slots=True)
class AttemptOrigin:
    attempt: Attempt
    journal_origin: tuple[str, int]
    admission_id: str
    intent_id: str
    intent_digest: str


@dataclass(frozen=True, slots=True)
class Projection:
    ledger_uuid: str
    ledger_generation: int
    experiment_id: str
    population: str
    events: tuple[AccountingEvent, ...]
    claimed_ids: frozenset[str]
    event_ids: frozenset[str]
    last_at: datetime
    bindings: tuple[tuple[str, int], ...]
    profiles: tuple[Profile, ...]
    lifecycles: tuple[LifecycleOrigin, ...]
    costs: tuple[NonModelCost, ...]
    attempts: tuple[AttemptOrigin, ...]
    holds: tuple[tuple[str, str], ...]

    @property
    def head_sequence(self):
        return len(self.events)

    @property
    def head_digest(self):
        return self.events[-1].digest

    @property
    def active_origin(self):
        return self.bindings[-1] if self.bindings else None


def _all_ids(projection):
    return projection.claimed_ids


def _fresh(values, projection):
    _check(len(values) == len(set(values)) and
           not set(values).intersection(_all_ids(projection)), 'identity_conflict')


def _register(projection, data):
    origin = (data['journal_uuid'], data['journal_generation'])
    _check(origin == projection.active_origin, 'origin_conflict')
    life = Lifecycle(data['lifecycle_id'], data['slot'], _week(data['week']),
                     _profile(data['profile']))
    _fresh((life.lifecycle_id,), projection)
    _check(life.profile in projection.profiles, 'configuration_conflict')
    _check(all((entry.lifecycle.week.key, entry.lifecycle.slot) !=
               (life.week.key, life.slot) for entry in projection.lifecycles),
           'configuration_conflict')
    return replace(projection, lifecycles=(*projection.lifecycles,
                                           LifecycleOrigin(life, origin)))


def _cost(projection, data, at):
    _fresh((data['cost_id'],), projection)
    _check(_stamp(data['valid_until_utc']) > at, 'exposure_stale')
    cost = NonModelCost(data['cost_id'], data['kind'],
                        Exposure('bounded', data['upper_bound_usd_micros'],
                                 _stamp(data['valid_until_utc']), None))
    _check(len(projection.costs) < 512, 'history_limit')
    return replace(projection, costs=(*projection.costs, cost))


def _reserve(projection, data, at):
    origin = (data['journal_uuid'], data['journal_generation'])
    _check(origin == projection.active_origin, 'origin_conflict')
    _check(data['lifecycle_id'] is None or any(
        entry.lifecycle.lifecycle_id == data['lifecycle_id'] and
        entry.journal_origin == origin for entry in projection.lifecycles),
        'origin_conflict')
    ids = tuple(data[key] for key in ('intent_id', 'attempt_id',
                                     'reservation_id', 'run_id', 'lease_id'))
    _fresh(ids, projection)
    prior_admissions = {entry.admission_id for entry in projection.attempts}
    _check(data['admission_id'] not in _all_ids(projection) - prior_admissions and
           data['admission_id'] not in ids, 'identity_conflict')
    _check(all(entry.admission_id != data['admission_id'] or
               entry.journal_origin == origin for entry in projection.attempts),
           'origin_conflict')
    _check(len(projection.attempts) < 512, 'history_limit')
    _check(all((entry.admission_id, entry.intent_id) !=
               (data['admission_id'], data['intent_id'])
               for entry in projection.attempts), 'identity_conflict')
    _check(data['week'] == _week_dict_for(at), 'invalid_week')
    exposure = Exposure('bounded', data['liability_usd_micros'],
                        _stamp(data['valid_until_utc']), None)
    candidate = Candidate(
        projection.experiment_id, origin[1], data['attempt_id'],
        data['reservation_id'], data['run_id'], data['lease_id'],
        _profile(data['profile']), data['kind'], data['lifecycle_id'],
        data['predecessor_id'], data['effects_reconciled'], exposure,
    )
    snapshot = Snapshot(
        projection.experiment_id, origin[1], at,
        'hypothetical_complete' if projection.population == 'synthetic_complete'
        else 'unknown', projection.profiles,
        tuple(entry.lifecycle for entry in projection.lifecycles),
        tuple(entry.attempt for entry in projection.attempts),
        projection.costs, tuple(code for _, code in projection.holds),
    )
    result = evaluate_reservation(snapshot, candidate, at=at)
    _check(isinstance(result, HypotheticalProposal),
           result.code if not isinstance(result, HypotheticalProposal) else
           'transition_invalid')
    _check(result.week == _week(data['week']) and
           result.reservation_usd_micros == data['reservation_usd_micros'] and
           result.liability_usd_micros == data['liability_usd_micros'],
           'reservation_conflict')
    attempt = Attempt(data['attempt_id'], data['reservation_id'], data['run_id'],
                      data['lease_id'], at, result.week, candidate.profile,
                      data['kind'], data['lifecycle_id'], data['predecessor_id'],
                      data['effects_reconciled'], exposure)
    return replace(projection, attempts=(*projection.attempts,
                                         AttemptOrigin(attempt, origin,
                                                       data['admission_id'],
                                                       data['intent_id'],
                                                       data['intent_digest'])))


def _week_dict_for(at):
    from .accounting_policy import week_for
    _check(2000 <= at.year <= 9998, 'invalid_time')
    week = week_for(at)
    return {'key': week.key, 'timezone': week.timezone,
                'start_utc': week.start_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                'end_utc': week.end_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}


def _body_ids(kind, body):
    if kind == 'journal_bound':
        return (body['journal_uuid'],)
    if kind == 'profile_configured':
        return tuple(body['profile'].values())
    if kind == 'lifecycle_registered':
        return (body['lifecycle_id'], body['journal_uuid'],
                *body['profile'].values())
    if kind == 'non_model_committed':
        return (body['cost_id'],)
    if kind == 'reservation_created':
        result = [body[key] for key in (
            'journal_uuid', 'admission_id', 'intent_id', 'attempt_id',
            'reservation_id', 'run_id', 'lease_id')]
        result.extend(body['profile'].values())
        result.extend(body[key] for key in ('lifecycle_id', 'predecessor_id')
                      if body[key] is not None)
        return tuple(result)
    return (body['hold_id'],)


def _apply_validated(projection, event, *, expected_head):
    _check(type(event) is AccountingEvent)
    _check(type(expected_head) is str and
           expected_head == (projection.head_digest if projection else ZERO),
           'stale_head')
    code = None
    try:
        checked = decode_event(event.raw, expected_digest=event.digest)
    except AccountingEventError as error:
        code = error.code
    if code is not None:
        raise AccountingTransitionError(code) from None
    data = checked.fields()
    if projection is None:
        _check(data['event_type'] == 'genesis' and data['sequence'] == 1 and
               data['previous_digest'] == ZERO, 'history_unavailable')
        _check(len({data['ledger_uuid'], data['experiment_id'],
                    data['event_id']}) == 3, 'identity_conflict')
        return Projection(data['ledger_uuid'], data['ledger_generation'],
                          data['experiment_id'], data['data']['population'],
                          (checked,),
                          frozenset((data['ledger_uuid'], data['experiment_id'],
                                     data['event_id'])),
                          frozenset((data['event_id'],)),
                          _stamp(data['recorded_at_utc']), (), (), (), (), (), ())
    _check((data['ledger_uuid'], data['ledger_generation'],
            data['experiment_id']) ==
           (projection.ledger_uuid, projection.ledger_generation,
            projection.experiment_id), 'identity_conflict')
    if data['event_id'] in projection.event_ids:
        old = next(item for item in projection.events
                   if item.fields()['event_id'] == data['event_id'])
        _check(old.raw == checked.raw, 'event_conflict')
        return projection
    _check(projection.head_sequence < 8192, 'history_limit')
    _check(data['event_id'] not in _all_ids(projection), 'identity_conflict')
    _check(data['sequence'] == projection.head_sequence + 1 and
           data['previous_digest'] == projection.head_digest,
           'chain_conflict')
    at = _stamp(data['recorded_at_utc'])
    _check(at >= projection.last_at, 'time_conflict')
    kind, body = data['event_type'], data['data']
    _check(kind != 'genesis', 'chain_conflict')
    _check(data['event_id'] not in _body_ids(kind, body), 'identity_conflict')
    if kind == 'journal_bound':
        origin = (body['journal_uuid'], body['journal_generation'])
        _check(origin not in projection.bindings, 'origin_conflict')
        _check(all(previous[0] != origin[0] or previous[1] < origin[1]
                   for previous in projection.bindings), 'origin_conflict')
        _check(body['journal_uuid'] not in
               _all_ids(projection).difference({item[0] for item in projection.bindings}),
               'identity_conflict')
        updated = replace(projection, bindings=(*projection.bindings, origin))
    elif kind == 'profile_configured':
        profile = _profile(body['profile'])
        _check(profile not in projection.profiles, 'configuration_conflict')
        _check(len(projection.profiles) < 16, 'history_limit')
        profile_ids = {profile.model_id, profile.auth_id, profile.venue_id}
        used = _all_ids(projection)
        _check(len(profile_ids) == 3, 'identity_conflict')
        for role in ('model_id', 'auth_id', 'venue_id'):
            identity = getattr(profile, role)
            same_role = {getattr(existing, role) for existing in projection.profiles}
            _check(identity not in used or identity in same_role,
                   'identity_conflict')
        updated = replace(projection, profiles=(*projection.profiles, profile))
    elif kind == 'lifecycle_registered':
        _check(len(projection.lifecycles) < 512, 'history_limit')
        updated = _register(projection, body)
    elif kind == 'non_model_committed':
        updated = _cost(projection, body, at)
    elif kind == 'reservation_created':
        updated = _reserve(projection, body, at)
    else:
        _fresh((body['hold_id'],), projection)
        _check(len(projection.holds) < 32, 'history_limit')
        updated = replace(projection, holds=(*projection.holds,
                                             (body['hold_id'], body['code'])))
    return replace(
        updated, events=(*projection.events, checked), last_at=at,
        claimed_ids=projection.claimed_ids.union(
            (data['event_id'], *_body_ids(kind, body))),
        event_ids=projection.event_ids.union((data['event_id'],)),
    )


def apply_event(projection, event, *, expected_head):
    """Rebuild public state from its events before applying a new transition."""
    if projection is not None:
        _check(type(projection) is Projection, 'projection_conflict')
        _check(type(expected_head) is str and
               expected_head == projection.head_digest, 'stale_head')
        rebuilt = replay_accounting(projection.events)
        _check(rebuilt == projection, 'projection_conflict')
    return _apply_validated(projection, event, expected_head=expected_head)


def replay_accounting(events):
    """Fold a complete presented stream; storage must authenticate its head."""
    _check(type(events) is tuple, 'transition_invalid')
    _check(bool(events), 'history_unavailable')
    _check(len(events) <= 8192, 'history_limit')
    projection = None
    for index, event in enumerate(events, 1):
        projection = _apply_validated(
            projection, event,
            expected_head=projection.head_digest if projection else ZERO,
        )
        _check(projection.head_sequence == index, 'chain_conflict')
    return projection


__all__ = ['AccountingTransitionError', 'Projection', 'apply_event',
           'replay_accounting']
