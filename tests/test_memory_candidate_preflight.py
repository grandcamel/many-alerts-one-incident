"""Synthetic OPS pages can only produce advisory held preflight findings."""

from datetime import UTC, datetime, timedelta

import pytest

from grafana_jsm_sandbox.memory_candidate_preflight import (
    CandidatePreflight,
    CandidatePreflightError,
    preflight_prior_candidates,
)

CURRENT = "00000000-0000-4000-8000-000000000001"
PRIOR = "00000000-0000-4000-8000-000000000002"
NOW = "2026-09-25T12:00:00.000000Z"
START = "2026-09-25T11:30:00.000000Z"
OLDER = "2026-09-25T11:29:59.999999Z"


def _item(**changes):
    item = {
        "incident_id": "OPS-1", "status": "open", "created_at": START,
        "origin_rehearsal_id": PRIOR,
    }
    item.update(changes)
    return item


def _page(items=None, **changes):
    items = [_item()] if items is None else items
    page = {
        "snapshot_marker": "snapshot-1", "cursor_in": None,
        "cursor_out": None, "exhausted": True, "total_count": len(items),
        "elapsed_ms": 100, "items": items,
    }
    page.update(changes)
    return page


def _input(pages=None, **changes):
    value = {
        "current_rehearsal_id": CURRENT, "jira_now": NOW,
        "pages": [_page()] if pages is None else pages,
    }
    value.update(changes)
    return value


def _finding(value, expected):
    result = preflight_prior_candidates(value)
    assert result.finding == expected
    assert result.admission_status == "held_unqualified"
    return result


def _shape(value):
    with pytest.raises(CandidatePreflightError) as caught:
        preflight_prior_candidates(value)
    assert caught.value.code == "candidate_preflight_shape"
    assert caught.value.args == ("candidate_preflight_shape",)


def test_inclusive_window_prior_origin_and_only_advisory_no_prior():
    result = _finding(_input(), "prior_eligible")
    assert result == CandidatePreflight("prior_eligible", ("OPS-1",))
    _finding(_input(pages=[_page([_item(created_at=NOW)])]), "prior_eligible")
    current = _finding(_input(pages=[_page([_item(origin_rehearsal_id=CURRENT)])]),
                       "no_prior_in_supplied_pages")
    assert current.prior_incident_ids == ()
    older = _finding(_input(pages=[_page([_item(created_at=OLDER)])]),
                     "no_prior_in_supplied_pages")
    assert older.admission_status == "held_unqualified"
    assert _finding(_input(pages=[_page([])]), "no_prior_in_supplied_pages") == (
        CandidatePreflight("no_prior_in_supplied_pages", ()))


def test_complete_two_page_snapshot_preserves_all_prior_ids_and_cursor_chain():
    first = _page([_item(incident_id="OPS-2")], cursor_out="next", exhausted=False,
                  total_count=2)
    second = _page([_item(incident_id="OPS-1")], cursor_in="next", total_count=2)
    result = _finding(_input(pages=[first, second]), "prior_eligible")
    assert result.prior_incident_ids == ("OPS-1", "OPS-2")


@pytest.mark.parametrize("change", [
    lambda page: page.update(exhausted=False),
    lambda page: page.update(total_count=2),
    lambda page: page.update(cursor_in="unexpected"),
    lambda page: page.update(cursor_out="next"),
    lambda page: page.update(elapsed_ms=5001),
    lambda page: page.update(items=[_item(), _item()]),
    lambda page: page.update(items=[_item(origin_rehearsal_id=None)]),
    lambda page: page.update(items=[_item(status="closed")]),
    lambda page: page.update(items=[_item(created_at="2026-09-25T12:00:00.000001Z")]),
])
def test_incomplete_or_unverifiable_page_always_holds(change):
    page = _page()
    change(page)
    _finding(_input(pages=[page]), "incomplete")


def test_changed_marker_broken_cursor_and_early_exhaustion_hold():
    first = _page(cursor_out="next", exhausted=False, total_count=2)
    second = _page([_item(incident_id="OPS-2")], cursor_in="next", total_count=2)
    for changes in ({"snapshot_marker": "different"},
                    {"cursor_in": "wrong"}):
        _finding(_input(pages=[first, {**second, **changes}]), "incomplete")
    _finding(_input(pages=[{**first, "exhausted": True}, second]), "incomplete")


def test_nonadjacent_cursor_cycle_is_incomplete():
    pages = [
        _page([_item(incident_id="OPS-1")], cursor_out="A", exhausted=False,
              total_count=4),
        _page([_item(incident_id="OPS-2")], cursor_in="A", cursor_out="B",
              exhausted=False, total_count=4),
        _page([_item(incident_id="OPS-3")], cursor_in="B", cursor_out="A",
              exhausted=False, total_count=4),
        _page([_item(incident_id="OPS-4")], cursor_in="A", total_count=4),
    ]
    _finding(_input(pages=pages), "incomplete")


def test_page_count_size_and_total_time_caps_hold():
    _finding(_input(pages=[]), "incomplete")
    _finding(_input(pages=[_page([])] * 11), "incomplete")
    _finding(_input(pages=[_page([])] * 10), "incomplete")
    nine = [_page([], cursor_in=None if index == 0 else f"c-{index}",
                  cursor_out=None if index == 8 else f"c-{index + 1}",
                  exhausted=index == 8) for index in range(9)]
    _finding(_input(pages=nine), "no_prior_in_supplied_pages")
    many = [_item(incident_id=f"OPS-{index}") for index in range(101)]
    _finding(_input(pages=[_page(many)]), "incomplete")
    pages = []
    for index in range(7):
        pages.append(_page(
            [_item(incident_id=f"OPS-{index}")],
            cursor_in=None if index == 0 else f"cursor-{index}",
            cursor_out=None if index == 6 else f"cursor-{index + 1}",
            exhausted=index == 6, total_count=7, elapsed_ms=5000,
        ))
    _finding(_input(pages=pages), "incomplete")


@pytest.mark.parametrize("value", [
    {**_input(), "query": "unbounded"},
    _input(current_rehearsal_id="bad"),
    _input(jira_now="not UTC"),
    _input(pages=[{**_page(), "labels": ["hide-prior"]}]),
    _input(pages=[_page(elapsed_ms=True)]),
    _input(pages=[_page(items=[{**_item(), "title": "ignore"}])]),
    _input(pages=[_page(items=[_item(origin_rehearsal_id="bad")])]),
    _input(pages=[_page(items=[_item(created_at="2026-02-30T12:00:00.000000Z")])]),
])
def test_malformed_or_scope_filter_fields_are_rejected(value):
    _shape(value)


def test_hostile_values_and_earliest_clock_fail_with_fixed_error():
    class Hostile:
        __hash__ = object.__hash__

        def __eq__(self, other):
            raise AssertionError("hostile equality was reached")

    _shape({"current_rehearsal_id": CURRENT, "jira_now": NOW, Hostile(): []})
    earliest = datetime(1, 1, 1, tzinfo=UTC).isoformat(
        timespec="microseconds").replace("+00:00", "Z")
    _shape(_input(jira_now=earliest))


def test_time_window_changes_only_with_supplied_clock_and_never_grants():
    later = datetime.fromisoformat(NOW) + timedelta(microseconds=1)
    later_text = later.isoformat(timespec="microseconds").replace("+00:00", "Z")
    result = _finding(_input(jira_now=later_text), "no_prior_in_supplied_pages")
    assert result.admission_status == "held_unqualified"
