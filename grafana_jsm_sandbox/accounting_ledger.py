"""Receiver-facing construction of non-reserving durable accounting events."""

from .accounting_events import ZERO, AccountingEventError, encode_event
from .accounting_store import LedgerError, LedgerStore


class AccountingLedger:
    """Build receiver-origin events from a verified store head; never reserve."""

    def __init__(self, store):
        self._store = store

    @classmethod
    def create(cls, directory, *, ledger_uuid, ledger_generation, experiment_id,
               event_id, recorded_at_utc):
        try:
            genesis = encode_event(
                ledger_uuid=ledger_uuid, ledger_generation=ledger_generation,
                experiment_id=experiment_id, sequence=1, previous_digest=ZERO,
                event_id=event_id, recorded_at_utc=recorded_at_utc,
                actor_kind='receiver', event_type='genesis',
                data={'policy_revision': 'accounting-v1', 'population': 'unknown'},
            )
        except AccountingEventError:
            raise LedgerError('ledger_event_invalid') from None
        return cls(LedgerStore.create(directory, genesis))

    @classmethod
    def open(cls, directory):
        return cls(LedgerStore.open(directory))

    @classmethod
    def inspect(cls, directory):
        return LedgerStore.inspect(directory)

    @property
    def head(self):
        return self._store.head

    @property
    def population(self):
        return self._store.projection.population

    def record(self, event_type, data, *, event_id, recorded_at_utc,
               expected_head):
        if event_type == 'reservation_created':
            raise LedgerError('reservation_unavailable')
        projection = self._store.projection
        predecessor = next(
            (index for index, event in enumerate(projection.events, 1)
             if event.digest == expected_head), None,
        )
        if predecessor is None:
            raise LedgerError('stale_head')
        try:
            event = encode_event(
                ledger_uuid=projection.ledger_uuid,
                ledger_generation=projection.ledger_generation,
                experiment_id=projection.experiment_id,
                sequence=predecessor + 1,
                previous_digest=expected_head,
                event_id=event_id, recorded_at_utc=recorded_at_utc,
                actor_kind='receiver', event_type=event_type, data=data,
            )
        except AccountingEventError:
            raise LedgerError('ledger_event_invalid') from None
        return self._store.append(event, expected_head=expected_head)

    def close(self):
        self._store.close()

    def __enter__(self):
        return self

    def __exit__(self, *_unused):
        self.close()


__all__ = ['AccountingLedger']
