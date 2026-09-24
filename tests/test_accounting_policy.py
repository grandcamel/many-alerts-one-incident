"""Independent known answers for evaluation-only accounting, never paid admission."""
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from grafana_jsm_sandbox import accounting_policy as ap

AT = datetime(2026, 9, 24, 12, tzinfo=UTC)


@pytest.mark.parametrize('amount', [-(2**63), -1, 0, 3_000_000, 2**63 - 1])
def test_money_exact_signed_integer(amount):
    assert ap.validate_usd_micros(amount) == amount


@pytest.mark.parametrize('amount', [True, False, 1.0, float('nan'), Decimal(1),
                                   '1', None, -(2**63)-1, 2**63])
def test_money_rejects_coercions_and_overflow(amount):
    with pytest.raises(ap.PolicyInputError) as caught:
        ap.validate_usd_micros(amount)
    assert caught.value.args == ('invalid_money',)
    assert caught.value.__context__ is None


@pytest.mark.parametrize('currency', ['EUR', 'usd', None, 1])
def test_currency_is_usd_only(currency):
    with pytest.raises(ap.PolicyInputError, match='^currency_unsupported$'):
        ap.validate_usd_micros(1, currency)


@pytest.mark.parametrize('instant,start,end', [
    ('2026-03-08T12:00:00+00:00', '2026-03-02T05:00:00+00:00', '2026-03-09T04:00:00+00:00'),
    ('2026-11-01T12:00:00+00:00', '2026-10-26T04:00:00+00:00', '2026-11-02T05:00:00+00:00'),
    ('2026-09-21T03:59:59+00:00', '2026-09-14T04:00:00+00:00', '2026-09-21T04:00:00+00:00'),
    ('2026-09-21T04:00:00+00:00', '2026-09-21T04:00:00+00:00', '2026-09-28T04:00:00+00:00'),
])
def test_week_monday_boundary_and_dst_known_answers(instant, start, end):
    week = ap.week_for(datetime.fromisoformat(instant))
    assert week == ap.Week(start[:10], datetime.fromisoformat(start),
                           datetime.fromisoformat(end), 'America/New_York')
    with pytest.raises(FrozenInstanceError):
        week.key = 'changed'


@pytest.mark.parametrize('at', [None, True, '2026-09-24', AT.replace(tzinfo=None),
                               datetime(1999, 1, 1, tzinfo=UTC),
                               datetime(9999, 1, 1, tzinfo=UTC),
                               AT.astimezone(timezone(timedelta(hours=1)))])
def test_week_refuses_noncanonical_or_unbounded_time(at):
    with pytest.raises(ap.PolicyInputError, match='^invalid_time$'):
        ap.week_for(at)


@pytest.mark.parametrize('field,limit,code', [
    ('experiment', 49_999_999, 'experiment_limit'),
    ('week_model', 150_000_000, 'weekly_limit'),
    ('lifecycle', 30_000_000, 'lifecycle_limit'),
    ('diagnostic', 30_000_000, 'diagnostic_limit'),
    ('lifecycle_attempts', 10, 'lifecycle_attempt_limit'),
    ('diagnostic_attempts', 10, 'diagnostic_attempt_limit'),
])
def test_limit_predicates_independently(field, limit, code):
    # This is an arithmetic predicate test, not a reachable combined snapshot.
    totals = ap.Totals(0, 0, 0, 0, 0, 0)
    assert ap.check_limits(replace(totals, **{field: limit})) is None
    assert ap.check_limits(replace(totals, **{field: limit + 1})) == ap.Refusal(code)


@pytest.mark.parametrize('value,code', [(True, 'invalid_money'), (-1, 'invalid_money'),
                                      (2**63, 'arithmetic_overflow'), ('0', 'invalid_money')])
def test_limit_predicate_rejects_malformed_totals(value, code):
    assert ap.check_limits(ap.Totals(value, 0, 0, 0, 0, 0)) == ap.Refusal(code)


def uid(n):
    return f'00000000-0000-0000-0000-{n:012x}'


def profile():
    return ap.Profile(uid(1), uid(2), uid(3))


def bounded(amount=3_000_000):
    return ap.Exposure('bounded', amount, AT + timedelta(days=2), None)


def snapshot(**changes):
    life = ap.Lifecycle(uid(4), 'rehearsal_1', ap.week_for(AT), profile())
    return replace(ap.Snapshot(uid(5), 1, AT, 'hypothetical_complete',
                               (profile(),), (life,), (), (), ()), **changes)


def candidate(**changes):
    return replace(ap.Candidate(uid(5), 1, uid(10), uid(11), uid(12), uid(13),
                                profile(), 'initial', uid(4), None, False, bounded()), **changes)


def evaluate(s=None, c=None, **kwargs):
    return ap.evaluate_reservation(s if s is not None else snapshot(),
                                   c if c is not None else candidate(), at=kwargs.get('at', AT))


def test_empty_hypothetical_snapshot_proposes_only_without_mutation():
    s, c = snapshot(), candidate()
    before = repr((s, c))
    result = evaluate(s, c)
    assert result == ap.HypotheticalProposal(c, ap.week_for(AT), 3_000_000, 3_000_000,
                                            ap.Totals(3_000_000, 3_000_000,
                                                      3_000_000, 0, 1, 0))
    assert repr((s, c)) == before
    with pytest.raises(FrozenInstanceError):
        result.liability_usd_micros = 0


@pytest.mark.parametrize('changes,code', [
    ({'population': 'unknown'}, 'population_unknown'),
    ({'population': 'conflicted'}, 'population_unknown'),
    ({'population': 'complete'}, 'invalid_input'),
    ({'holds': ('billing_lag',)}, 'held'),
    ({'holds': ('caller text',)}, 'invalid_input'),
    ({'as_of': AT - timedelta(seconds=1)}, 'stale_snapshot'),
    ({'attempts': []}, 'invalid_input'),
    ({'profiles': ()}, 'configuration_conflict'),
    ({'profiles': (profile(), profile())}, 'configuration_conflict'),
    ({'journal_generation': True}, 'invalid_input'),
])
def test_snapshot_gate_refusals(changes, code):
    assert evaluate(snapshot(**changes)) == ap.Refusal(code)


@pytest.mark.parametrize('changes,code', [
    ({'experiment_id': uid(100)}, 'identity_conflict'),
    ({'journal_generation': 2}, 'identity_conflict'),
    ({'journal_generation': 0}, 'invalid_input'),
    ({'profile': ap.Profile(uid(100), uid(2), uid(3))}, 'configuration_conflict'),
    ({'reservation_id': uid(10)}, 'identity_conflict'),
    ({'attempt_id': 'CALLER_SECRET'}, 'invalid_input'),
    ({'kind': 'retry'}, 'lineage_conflict'),
    ({'effects_reconciled': 0}, 'invalid_input'),
    ({'lifecycle_id': uid(100)}, 'configuration_conflict'),
    ({'exposure': ap.Exposure('unknown', None, None, None)}, 'exposure_unknown'),
    ({'exposure': ap.Exposure('bounded', None, AT + timedelta(days=1), None)},
     'exposure_unknown'),
    ({'exposure': ap.Exposure('bounded', 3_000_000, AT, None)}, 'exposure_stale'),
    ({'exposure': bounded(2_999_999)}, 'invalid_money'),
])
def test_candidate_closed_refusals(changes, code):
    assert evaluate(c=candidate(**changes)) == ap.Refusal(code)


def attempt(n=0, **changes):
    return replace(ap.Attempt(uid(100+n*4), uid(101+n*4), uid(102+n*4), uid(103+n*4),
                              AT - timedelta(hours=24) + timedelta(seconds=n), ap.week_for(AT),
                              profile(), 'initial', uid(4), None, False, bounded()), **changes)


def settled(actual=0, upper=3_000_000):
    return ap.Exposure('settled', upper, None, actual)


def test_history_settled_actual_replaces_upper_and_nonmodel_never_enters_model_totals():
    costs = tuple(ap.NonModelCost(uid(800+i), kind, bounded(1_000_000))
                  for i, kind in enumerate(('support', 'review', 'venue')))
    s = snapshot(attempts=(attempt(exposure=settled(2_000_000, 6_000_000)),),
                 non_model_costs=costs)
    result = evaluate(s, candidate(exposure=bounded(5_000_000)))
    assert result.totals == ap.Totals(7_000_000, 10_000_000, 7_000_000, 0, 2, 0)
    assert result.reservation_usd_micros == 3_000_000
    assert result.liability_usd_micros == 5_000_000


@pytest.mark.parametrize('prior,expected', [(46_999_999, 'proposal'), (47_000_000, 'refusal')])
def test_combined_experiment_strict_cap_independent_known_answer(prior, expected):
    cost = ap.NonModelCost(uid(800), 'support', bounded(prior))
    result = evaluate(snapshot(non_model_costs=(cost,)))
    if expected == 'proposal':
        assert result.totals == ap.Totals(3_000_000, 49_999_999, 3_000_000, 0, 1, 0)
    else:
        assert result == ap.Refusal('experiment_limit')


@pytest.mark.parametrize('exposure,code', [
    (ap.Exposure('unknown', None, None, None), 'exposure_unknown'),
    (ap.Exposure('conflicted', 0, None, 0), 'exposure_unknown'),
    (ap.Exposure('bounded', 3_000_000, AT - timedelta(seconds=1), None), 'exposure_stale'),
    (settled(4_000_000), 'above_liability'),
    (settled(-1), 'invalid_money'),
])
@pytest.mark.parametrize('nonmodel', [False, True])
def test_unknown_stale_or_inconsistent_history_never_becomes_zero(exposure, code, nonmodel):
    s = snapshot(non_model_costs=(ap.NonModelCost(uid(800), 'venue', exposure),)) if nonmodel else \
        snapshot(attempts=(attempt(exposure=exposure),))
    assert evaluate(s) == ap.Refusal(code)


def test_old_week_liability_remains_in_lifetime_but_not_new_week():
    old_at = AT - timedelta(days=7)
    old_week = ap.week_for(old_at)
    old_life = ap.Lifecycle(uid(6), 'rehearsal_1', old_week, profile())
    old = attempt(reserved_at=old_at, week=old_week, lifecycle_id=uid(6),
                  exposure=bounded(20_000_000))
    s = snapshot(lifecycles=(old_life, *snapshot().lifecycles), attempts=(old,))
    assert evaluate(s).totals == ap.Totals(3_000_000, 23_000_000, 3_000_000, 0, 1, 0)
    assert s.attempts[0].week is old_week


@pytest.mark.parametrize('kind', ['initial', 'diagnostic'])
def test_low_settled_actuals_do_not_erase_attempt_ceiling(kind):
    rows = tuple(attempt(i, kind=kind, lifecycle_id=None if kind == 'diagnostic' else uid(4),
                         exposure=settled(10_000)) for i in range(10))
    c = candidate(kind=kind, lifecycle_id=None if kind == 'diagnostic' else uid(4))
    assert isinstance(evaluate(snapshot(attempts=rows[:9]), c), ap.HypotheticalProposal)
    code = 'diagnostic_attempt_limit' if kind == 'diagnostic' else 'lifecycle_attempt_limit'
    assert evaluate(snapshot(attempts=rows), c) == ap.Refusal(code)


def test_duplicate_identity_is_not_a_second_charge_or_reusable_proposal():
    s = snapshot(attempts=(attempt(attempt_id=uid(10)),))
    assert evaluate(s) == ap.Refusal('identity_conflict')


def test_nonmodel_identity_conflict_with_run_id_is_refused():
    s = snapshot(attempts=(attempt(),),
                 non_model_costs=(ap.NonModelCost(uid(102), 'venue', bounded()),))
    assert evaluate(s) == ap.Refusal('identity_conflict')


@pytest.mark.parametrize('reserved_at', [AT, AT + timedelta(seconds=1)])
def test_candidate_must_follow_history_strictly(reserved_at):
    assert evaluate(snapshot(attempts=(attempt(reserved_at=reserved_at),))) == \
        ap.Refusal('lineage_conflict')


def test_aggregate_int64_overflow_is_closed():
    costs = (ap.NonModelCost(uid(800), 'venue', bounded(2**63 - 1)),
             ap.NonModelCost(uid(801), 'review', bounded(1)))
    assert evaluate(snapshot(non_model_costs=costs)) == ap.Refusal('arithmetic_overflow')


def retry(**changes):
    return candidate(kind='retry', predecessor_id=uid(100), effects_reconciled=True, **changes)


def test_retry_charged_once_in_week_twice_across_buckets():
    s = snapshot(attempts=(attempt(exposure=bounded(4_000_000)),))
    result = evaluate(s, retry(exposure=bounded(5_000_000)))
    assert result.totals == ap.Totals(9_000_000, 9_000_000, 9_000_000, 5_000_000, 2, 1)


def test_historical_retry_counts_remain_with_zero_settled_cost():
    first = attempt(exposure=settled())
    second = attempt(1, kind='retry', predecessor_id=first.attempt_id,
                     effects_reconciled=True, exposure=settled())
    s = snapshot(attempts=(first, second))
    c = replace(retry(), predecessor_id=second.attempt_id)
    assert evaluate(s, c).totals == ap.Totals(3_000_000, 3_000_000,
                                            3_000_000, 3_000_000, 3, 2)
    assert evaluate(s) == ap.Refusal('lineage_conflict')
    assert evaluate(s, retry()) == ap.Refusal('lineage_conflict')


def test_retry_must_follow_latest_ordinary_initial_in_lifecycle():
    rows = (attempt(exposure=settled()), attempt(1, exposure=settled()))
    s = snapshot(attempts=rows)
    assert evaluate(s, retry()) == ap.Refusal('lineage_conflict')
    assert isinstance(evaluate(s, replace(retry(), predecessor_id=rows[-1].attempt_id)),
                      ap.HypotheticalProposal)


@pytest.mark.parametrize('change', [
    {'effects_reconciled': False}, {'predecessor_id': uid(900)},
    {'profile': ap.Profile(uid(30), uid(2), uid(3))},
])
def test_retry_reconciliation_link_and_model_are_required(change):
    s = snapshot(attempts=(attempt(),), profiles=(profile(), ap.Profile(uid(30), uid(2), uid(3))))
    assert isinstance(evaluate(s, replace(retry(), **change)), ap.Refusal)


def test_retry_cannot_reallocate_old_lifecycle_to_new_week():
    old = attempt(reserved_at=AT-timedelta(days=7), week=ap.week_for(AT-timedelta(days=7)))
    life = replace(snapshot().lifecycles[0], week=old.week)
    assert evaluate(snapshot(lifecycles=(life,), attempts=(old,)), retry()) == \
        ap.Refusal('configuration_conflict')


def test_unrelated_old_lifecycle_overage_holds_new_proposal():
    old_week = ap.week_for(AT-timedelta(days=7))
    old_life = ap.Lifecycle(uid(6), 'rehearsal_1', old_week, profile())
    old = attempt(reserved_at=AT-timedelta(days=7), week=old_week,
                  lifecycle_id=uid(6), exposure=bounded(30_000_001))
    assert evaluate(snapshot(lifecycles=(old_life, *snapshot().lifecycles), attempts=(old,))) == \
        ap.Refusal('lifecycle_limit')


@pytest.mark.parametrize('changes', [
    {'start_utc': datetime(2026, 9, 21, 12, tzinfo=UTC),
     'end_utc': datetime(2026, 9, 28, 12, tzinfo=UTC)},
    {'start_utc': datetime(2026, 9, 21, 4, 0, 1, tzinfo=UTC)},
    {'end_utc': datetime(2026, 9, 29, 4, tzinfo=UTC)},
    {'timezone': 'UTC'}, {'key': '2026-09-22'}, {'key': AT},
])
def test_stored_week_rejects_shifted_or_malformed_boundaries(changes):
    life = snapshot().lifecycles[0]
    bad = replace(life, week=replace(life.week, **changes))
    assert evaluate(snapshot(lifecycles=(bad,))) == ap.Refusal('invalid_week')


def test_current_week_must_equal_stored_week_not_silently_recompute_it():
    life = snapshot().lifecycles[0]
    shifted = replace(life.week, start_utc=life.week.start_utc + timedelta(hours=1),
                      end_utc=life.week.end_utc + timedelta(hours=1))
    assert evaluate(snapshot(lifecycles=(replace(life, week=shifted),))) == \
        ap.Refusal('invalid_week')


class Untrusted:
    def __eq__(self, other):
        raise AssertionError('must reject exact type before equality')

    def __repr__(self):
        raise AssertionError('must never render input')


def test_all_input_record_fields_reject_untrusted_objects_without_invoking_hooks():
    from dataclasses import fields
    objects = [snapshot(), candidate(), profile(), snapshot().lifecycles[0],
               attempt(), bounded(), ap.NonModelCost(uid(800), 'venue', bounded()),
               ap.week_for(AT)]
    for obj in objects:
        for field in fields(obj):
            bad = replace(obj, **{field.name: Untrusted()})
            s, c = snapshot(), candidate()
            if type(obj) is ap.Snapshot:
                s = bad
            elif type(obj) is ap.Candidate:
                c = bad
            elif type(obj) is ap.Profile:
                s = replace(s, profiles=(bad,))
            elif type(obj) is ap.Lifecycle:
                s = replace(s, lifecycles=(bad,))
            elif type(obj) is ap.Attempt:
                s = replace(s, attempts=(bad,))
            elif type(obj) is ap.Exposure:
                c = replace(c, exposure=bad)
            elif type(obj) is ap.NonModelCost:
                s = replace(s, non_model_costs=(bad,))
            else:
                s = replace(s, lifecycles=(replace(s.lifecycles[0], week=bad),))
            assert type(evaluate(s, c)) is ap.Refusal, (type(obj).__name__, field.name)


@pytest.mark.parametrize('field,limit', [('profiles', 16), ('lifecycles', 512),
                                        ('attempts', 512), ('non_model_costs', 512), ('holds', 32)])
def test_collection_bounds_checked_before_visiting_entries(field, limit):
    assert evaluate(snapshot(**{field: (Untrusted(),) * (limit + 1)})) == \
        ap.Refusal('history_limit')


def test_pure_module_has_closed_imports_and_no_clock_or_execution_calls():
    import ast
    from pathlib import Path
    source = Path(ap.__file__).read_text()
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0
            imports.add(node.module)
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else \
                node.func.attr if isinstance(node.func, ast.Attribute) else ''
            assert name not in {'now', 'today', 'utcnow', 'open', 'eval', 'exec', '__import__'}
    assert imports <= {'dataclasses', 'datetime', 'zoneinfo', 'uuid'}


def test_money_rejects_subclasses_and_negative_exposure():
    class Subint(int):
        pass
    with pytest.raises(ap.PolicyInputError, match='^invalid_money$'):
        ap.validate_usd_micros(Subint(1))
    assert evaluate(c=candidate(exposure=bounded(-1))) == ap.Refusal('invalid_money')


def test_week_at_lower_year_boundary_has_valid_prior_year_start():
    value = ap.week_for(datetime(2000, 1, 1, tzinfo=UTC))
    assert value.key == '1999-12-27'
    assert value.start_utc == datetime(1999, 12, 27, 5, tzinfo=UTC)


@pytest.mark.parametrize('context_id', [uid(1), uid(2), uid(3), uid(4), uid(5)])
@pytest.mark.parametrize('role', ['cost', 'history', 'candidate'])
def test_new_record_identities_are_disjoint_from_configured_context(context_id, role):
    s, c = snapshot(), candidate()
    if role == 'cost':
        s = replace(s, non_model_costs=(ap.NonModelCost(context_id, 'support', bounded()),))
    elif role == 'history':
        s = replace(s, attempts=(attempt(run_id=context_id),))
    else:
        c = replace(c, reservation_id=context_id)
    assert evaluate(s, c) == ap.Refusal('identity_conflict')
