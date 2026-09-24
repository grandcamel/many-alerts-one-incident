"""Evaluation-only USD reservation policy; no durable receipt or launch authority.

All population, configuration and settled-cost inputs are hypothetical. A future
trusted adapter must establish provenance and re-evaluate under serialization.
Only week_for consults installed timezone data; there is no current-clock read.
"""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


class PolicyInputError(ValueError):
    """A fixed policy code, never caller content."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code='invalid_input'):
    if not condition:
        raise PolicyInputError(code)


def validate_usd_micros(amount, currency='USD'):
    """Validate representation only; signed credits have no evaluation semantics."""
    _require(type(currency) is str and currency == 'USD', 'currency_unsupported')
    _require(type(amount) is int and -(2**63) <= amount < 2**63, 'invalid_money')
    return amount


def _time(value):
    _require(type(value) is datetime and value.tzinfo is UTC, 'invalid_time')
    return value


@dataclass(frozen=True, slots=True)
class Week:
    key: str
    start_utc: datetime
    end_utc: datetime
    timezone: str


def week_for(instant):
    """Compute new reservation boundaries; never use to reinterpret old weeks."""
    _time(instant)
    _require(2000 <= instant.year <= 9998, 'invalid_time')
    local = instant.astimezone(ZoneInfo('America/New_York'))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    start -= timedelta(days=local.weekday())
    end = start + timedelta(days=7)
    return Week(start.date().isoformat(), start.astimezone(UTC),
                end.astimezone(UTC), 'America/New_York')


@dataclass(frozen=True, slots=True)
class Refusal:
    code: str


@dataclass(frozen=True, slots=True)
class Totals:
    week_model: int
    experiment: int
    lifecycle: int
    diagnostic: int
    lifecycle_attempts: int
    diagnostic_attempts: int


def _nonnegative(value):
    _require(type(value) is int and value >= 0, 'invalid_money')
    _require(value < 2**63, 'arithmetic_overflow')
    return value


def _limits(totals):
    _require(type(totals) is Totals)
    for field, ceiling, code in (
        ('week_model', 150_000_000, 'weekly_limit'),
        ('experiment', 49_999_999, 'experiment_limit'),
        ('lifecycle', 30_000_000, 'lifecycle_limit'),
        ('diagnostic', 30_000_000, 'diagnostic_limit'),
        ('lifecycle_attempts', 10, 'lifecycle_attempt_limit'),
        ('diagnostic_attempts', 10, 'diagnostic_attempt_limit'),
    ):
        _require(_nonnegative(getattr(totals, field)) <= ceiling, code)


def check_limits(totals):
    """Arithmetic predicates only; None conveys no snapshot/execution authority."""
    try:
        _limits(totals)
    except PolicyInputError as error:
        code = error.code
    else:
        return None
    return Refusal(code)


@dataclass(frozen=True, slots=True)
class Profile:
    model_id: str
    auth_id: str
    venue_id: str


@dataclass(frozen=True, slots=True)
class Lifecycle:
    lifecycle_id: str
    slot: str
    week: Week
    profile: Profile


@dataclass(frozen=True, slots=True)
class Exposure:
    state: str
    upper_bound: int | None
    valid_until: datetime | None
    actual: int | None


@dataclass(frozen=True, slots=True)
class Attempt:
    attempt_id: str
    reservation_id: str
    run_id: str
    lease_id: str
    reserved_at: datetime
    week: Week
    profile: Profile
    kind: str
    lifecycle_id: str | None
    predecessor_id: str | None
    effects_reconciled: bool
    exposure: Exposure


@dataclass(frozen=True, slots=True)
class NonModelCost:
    cost_id: str
    kind: str
    exposure: Exposure


@dataclass(frozen=True, slots=True)
class Snapshot:
    experiment_id: str
    journal_generation: int
    as_of: datetime
    population: str
    profiles: tuple[Profile, ...]
    lifecycles: tuple[Lifecycle, ...]
    attempts: tuple[Attempt, ...]
    non_model_costs: tuple[NonModelCost, ...]
    holds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Candidate:
    experiment_id: str
    journal_generation: int
    attempt_id: str
    reservation_id: str
    run_id: str
    lease_id: str
    profile: Profile
    kind: str
    lifecycle_id: str | None
    predecessor_id: str | None
    effects_reconciled: bool
    exposure: Exposure


@dataclass(frozen=True, slots=True)
class HypotheticalProposal:
    candidate: Candidate
    week: Week
    reservation_usd_micros: int
    liability_usd_micros: int
    totals: Totals


HOLDS = (
    'billing_unknown', 'billing_lag', 'launch_or_dispatch_unknown',
    'provider_receipt_conflict', 'unmatched_provider_charge', 'above_cap_actual',
    'ledger_missing_or_corrupt', 'recovery_incomplete', 'capacity_exhausted',
    'forwarder_control_unreconciled', 'venue_or_mediated_readiness_failed',
    'history_unavailable', 'execution_recovery', 'effect_recovery',
)


def _choice(value, choices):
    _require(type(value) is str and value in choices)


def _id(value):
    _require(type(value) is str and len(value) == 36)
    _require(all(c == '-' if i in (8, 13, 18, 23) else c in '0123456789abcdef'
                 for i, c in enumerate(value)))
    return value


def _identity(record):
    _id(record.experiment_id)
    _require(type(record.journal_generation) is int and
             1 <= record.journal_generation <= 2**31 - 1)


def _profile(value):
    _require(type(value) is Profile)
    for item in (value.model_id, value.auth_id, value.venue_id):
        _id(item)


def _week(value):
    _require(type(value) is Week, 'invalid_week')
    _require(type(value.key) is str and type(value.timezone) is str, 'invalid_week')
    _require(value.timezone == 'America/New_York', 'invalid_week')
    start, end = _time(value.start_utc), _time(value.end_utc)
    _require(start.date().isoformat() == value.key and start.weekday() == 0, 'invalid_week')
    _require(end.date() - start.date() == timedelta(days=7), 'invalid_week')
    _require(end - start in tuple(timedelta(hours=h) for h in (167, 168, 169)), 'invalid_week')
    for endpoint in (start, end):
        _require(endpoint.hour in (4, 5) and
                 endpoint.minute == endpoint.second == endpoint.microsecond == 0, 'invalid_week')


def _exposure(value, at, *, model):
    _require(type(value) is Exposure)
    _choice(value.state, ('bounded', 'settled', 'unknown', 'conflicted'))
    _require(value.state not in ('unknown', 'conflicted'), 'exposure_unknown')
    _require(value.upper_bound is not None, 'exposure_unknown')
    upper = _nonnegative(value.upper_bound)
    _require(not model or upper >= 3_000_000, 'invalid_money')
    if value.state == 'bounded':
        _require(value.actual is None)
        _require(value.valid_until is not None, 'exposure_unknown')
        _require(_time(value.valid_until) > at, 'exposure_stale')
        return upper
    _require(value.valid_until is None)
    _require(value.actual is not None, 'exposure_unknown')
    actual = _nonnegative(value.actual)
    _require(actual <= upper, 'above_liability')
    return actual


def _claim_ids(record, identities):
    for field in ('attempt_id', 'reservation_id', 'run_id', 'lease_id'):
        value = _id(getattr(record, field))
        _require(value not in identities, 'identity_conflict')
        identities.add(value)


def _attribution(row, week, profiles, lifecycles):
    _profile(row.profile)
    _require(row.profile in profiles, 'configuration_conflict')
    _choice(row.kind, ('initial', 'retry', 'diagnostic'))
    _require(type(row.effects_reconciled) is bool)
    if row.kind == 'diagnostic':
        _require(row.lifecycle_id is None and row.predecessor_id is None and
                 not row.effects_reconciled, 'lineage_conflict')
        return
    _id(row.lifecycle_id)
    _require(row.lifecycle_id in lifecycles, 'configuration_conflict')
    life = lifecycles[row.lifecycle_id]
    _require(life.profile == row.profile and life.week == week, 'configuration_conflict')
    if row.kind == 'initial':
        _require(row.predecessor_id is None and not row.effects_reconciled, 'lineage_conflict')
    else:
        _require(row.effects_reconciled and row.predecessor_id is not None, 'lineage_conflict')
        _id(row.predecessor_id)


class _Accounting:
    """Local scratch totals derived from facts; never exposed or persisted."""

    def __init__(self):
        self.experiment = 0
        self.weeks = {}
        self.lifecycles = {}
        self.diagnostics = {}
        self.identities = set()

    def add(self, row, week, amount):
        self.experiment = _nonnegative(self.experiment + amount)
        self.weeks[week.key] = _nonnegative(self.weeks.get(week.key, 0) + amount)
        if row.kind != 'diagnostic':
            spend, count = self.lifecycles.get(row.lifecycle_id, (0, 0))
            self.lifecycles[row.lifecycle_id] = (_nonnegative(spend + amount), count + 1)
        if row.kind in ('retry', 'diagnostic'):
            spend, count = self.diagnostics.get(week.key, (0, 0))
            self.diagnostics[week.key] = (_nonnegative(spend + amount), count + 1)

    def totals(self, key, lifecycle_id=None):
        life, count = self.lifecycles.get(lifecycle_id, (0, 0))
        diag, diag_count = self.diagnostics.get(key, (0, 0))
        return Totals(self.weeks.get(key, 0), self.experiment, life, diag, count, diag_count)

    def check_history(self, lifecycles):
        _limits(Totals(0, self.experiment, 0, 0, 0, 0))
        for key in self.weeks:
            _limits(self.totals(key))
        for identity, life in lifecycles.items():
            _limits(self.totals(life.week.key, identity))


def _remember_week(week, known):
    _week(week)
    for previous in known.values():
        if week.key == previous.key:
            _require(week == previous, 'invalid_week')
        else:
            _require(week.end_utc <= previous.start_utc or week.start_utc >= previous.end_utc,
                     'invalid_week')
    known[week.key] = week


def _lineage(row, latest):
    if row.kind == 'diagnostic':
        return
    previous = latest.get(row.lifecycle_id)
    if row.kind == 'retry':
        _require(previous is not None and row.predecessor_id == previous.attempt_id and
                 row.profile == previous.profile, 'lineage_conflict')
    else:
        _require(previous is None or previous.kind != 'retry', 'lineage_conflict')
    latest[row.lifecycle_id] = row


def _evaluate(snapshot, candidate, at):
    _require(type(snapshot) is Snapshot and type(candidate) is Candidate)
    current = week_for(at)
    _identity(snapshot)
    _identity(candidate)
    _require(_time(snapshot.as_of) == at, 'stale_snapshot')
    _require((snapshot.experiment_id, snapshot.journal_generation) ==
             (candidate.experiment_id, candidate.journal_generation), 'identity_conflict')
    for field, limit in (('profiles', 16), ('lifecycles', 512), ('attempts', 512),
                         ('non_model_costs', 512), ('holds', 32)):
        value = getattr(snapshot, field)
        _require(type(value) is tuple)
        _require(len(value) <= limit, 'history_limit')
    _choice(snapshot.population, ('hypothetical_complete', 'unknown', 'conflicted'))
    _require(snapshot.population == 'hypothetical_complete', 'population_unknown')
    for hold in snapshot.holds:
        _choice(hold, HOLDS)
    _require(not snapshot.holds, 'held')
    for profile in snapshot.profiles:
        _profile(profile)
    _require(bool(snapshot.profiles) and len(set(snapshot.profiles)) == len(snapshot.profiles),
             'configuration_conflict')
    lifecycles, slots = {}, set()
    known_weeks = {current.key: current}
    for life in snapshot.lifecycles:
        _require(type(life) is Lifecycle)
        _id(life.lifecycle_id)
        _remember_week(life.week, known_weeks)
        _profile(life.profile)
        _require(life.profile in snapshot.profiles, 'configuration_conflict')
        _choice(life.slot, ('rehearsal_1', 'rehearsal_2', 'rehearsal_3', 'presentation'))
        slot = (life.week.key, life.slot)
        _require(life.lifecycle_id not in lifecycles and slot not in slots,
                 'configuration_conflict')
        lifecycles[life.lifecycle_id] = life
        slots.add(slot)
    accounting = _Accounting()
    accounting.identities.update((snapshot.experiment_id, *lifecycles))
    for profile in snapshot.profiles:
        accounting.identities.update((profile.model_id, profile.auth_id, profile.venue_id))
    previous_at = None
    latest = {}
    for row in snapshot.attempts:
        _require(type(row) is Attempt)
        _time(row.reserved_at)
        _require(row.reserved_at < at and
                 (previous_at is None or previous_at < row.reserved_at), 'lineage_conflict')
        previous_at = row.reserved_at
        _remember_week(row.week, known_weeks)
        _require(row.week.start_utc <= row.reserved_at < row.week.end_utc, 'invalid_week')
        _claim_ids(row, accounting.identities)
        _attribution(row, row.week, snapshot.profiles, lifecycles)
        _lineage(row, latest)
        accounting.add(row, row.week, _exposure(row.exposure, at, model=True))
    for cost in snapshot.non_model_costs:
        _require(type(cost) is NonModelCost)
        _id(cost.cost_id)
        _require(cost.cost_id not in accounting.identities, 'identity_conflict')
        accounting.identities.add(cost.cost_id)
        _choice(cost.kind, ('support', 'review', 'venue'))
        amount = _exposure(cost.exposure, at, model=False)
        accounting.experiment = _nonnegative(accounting.experiment + amount)
    accounting.check_history(lifecycles)
    _claim_ids(candidate, accounting.identities)
    _attribution(candidate, current, snapshot.profiles, lifecycles)
    _lineage(candidate, latest)
    upper = _exposure(candidate.exposure, at, model=True)
    _require(candidate.exposure.state == 'bounded')
    accounting.add(candidate, current, upper)
    totals = accounting.totals(current.key, candidate.lifecycle_id)
    _limits(totals)
    return HypotheticalProposal(candidate, current, 3_000_000, upper, totals)


def evaluate_reservation(snapshot, candidate, *, at):
    """Evaluate hypothetical complete facts; does not reserve, persist or launch."""
    try:
        return _evaluate(snapshot, candidate, at)
    except PolicyInputError as error:
        code = error.code
    return Refusal(code)
