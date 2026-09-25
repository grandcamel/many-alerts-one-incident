"""Pure same-generation relation between archive and caller-supplied active rows.

This checks structural continuity only. Neither input is authenticated as a
durable active store, off-cluster copy or independent continuity witness.
"""

from dataclasses import dataclass
from pathlib import Path

from .accounting_archive_index import ArchiveIndex, ArchiveIndexError, decode_index
from .accounting_archive_segment import ArchiveSegment
from .accounting_events import AccountingEvent, AccountingEventError, decode_event
from .accounting_store import LedgerStore
from .accounting_transition import AccountingTransitionError, Projection, replay_accounting

MAX_ACTIVE_EVENTS = 8192


class ArchiveOverlapError(ValueError):
    """Fixed structural refusal without event bytes or a path."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ArchiveOverlap:
    projection: Projection
    archived_count: int
    active_count: int
    overlap_count: int
    suffix_count: int


def _check(condition: bool, code: str = 'archive_overlap_invalid') -> None:
    if not condition:
        raise ArchiveOverlapError(code)


def compare_archive_active(
    segments: tuple[ArchiveSegment, ...], index: ArchiveIndex,
    active_events: tuple[AccountingEvent, ...], *, active_head: tuple[int, str],
) -> ArchiveOverlap:
    """Replay one union after exact overlap; return no admission authority."""
    _check(type(segments) is tuple and type(index) is ArchiveIndex)
    _check(type(active_events) is tuple and 1 <= len(active_events) <= MAX_ACTIVE_EVENTS)
    _check(type(active_head) is tuple and len(active_head) == 2 and
           type(active_head[0]) is int and 1 <= active_head[0] <= MAX_ACTIVE_EVENTS and
           type(active_head[1]) is str and len(active_head[1]) == 64 and
           all(character in '0123456789abcdef' for character in active_head[1]))
    try:
        archive = decode_index(index.raw, expected_digest=index.digest,
                               segments=segments)
    except ArchiveIndexError:
        raise ArchiveOverlapError('archive_index_invalid') from None
    prefix = archive.projection.events
    checked: list[AccountingEvent] = []
    for event in active_events:
        _check(type(event) is AccountingEvent, 'archive_active_invalid')
        try:
            checked.append(decode_event(event.raw, expected_digest=event.digest))
        except AccountingEventError:
            raise ArchiveOverlapError('archive_active_invalid') from None
    first = checked[0].fields()['sequence']
    last = checked[-1].fields()['sequence']
    _check(first <= len(prefix) + 1 and last >= len(prefix), 'archive_gap')
    _check(last == active_head[0] and checked[-1].digest == active_head[1],
           'archive_head_conflict')
    owner = (archive.projection.ledger_uuid, archive.projection.ledger_generation,
             archive.projection.experiment_id)
    suffix: list[AccountingEvent] = []
    overlap = 0
    for offset, event in enumerate(checked):
        fields = event.fields()
        sequence = first + offset
        _check(fields['sequence'] == sequence, 'archive_gap')
        _check((fields['ledger_uuid'], fields['ledger_generation'],
                fields['experiment_id']) == owner, 'archive_identity_conflict')
        if sequence <= len(prefix):
            prior = prefix[sequence - 1]
            _check(event.raw == prior.raw and event.digest == prior.digest,
                   'archive_overlap_conflict')
            overlap += 1
        else:
            suffix.append(event)
    try:
        projection = replay_accounting(prefix + tuple(suffix))
    except AccountingTransitionError:
        raise ArchiveOverlapError('archive_union_invalid') from None
    _check(projection.head_sequence == active_head[0] and
           projection.head_digest == active_head[1], 'archive_head_conflict')
    return ArchiveOverlap(projection, len(prefix), len(checked), overlap, len(suffix))


def compare_archive_to_ledger(
    directory: Path, segments: tuple[ArchiveSegment, ...], index: ArchiveIndex,
) -> ArchiveOverlap:
    """Compare one closed, query-only ledger image; grant no continuing lease."""
    view = LedgerStore.inspect_archive_active_view(directory)
    if view.state != 'ready' or view.head is None:
        raise ArchiveOverlapError('archive_active_unverified')
    return compare_archive_active(segments, index, view.events, active_head=view.head)


__all__ = ['ArchiveOverlap', 'ArchiveOverlapError', 'compare_archive_active',
           'compare_archive_to_ledger']
