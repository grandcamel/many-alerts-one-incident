"""Unit tests for the raw-ingress sanitizer (ticket 37, unit 16), cases
I1-I14 of the implementation plan. Every body here is a Python literal
built in the test; the ticket-14 capture corpus is exercised separately in
``test_journal_ingress_corpus.py`` (not owned by this file).

Nothing here opens a socket, a clock or a file, other than reading this
module's own source for the AST checks in I12.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import json
import pathlib

import pytest

from grafana_jsm_sandbox import forwarder_json
from grafana_jsm_sandbox import journal_ingress as ji
from grafana_jsm_sandbox import journal_source as js
from grafana_jsm_sandbox.forwarder_json import JSONPolicyError, canonical_json

REPOSITORY = pathlib.Path(__file__).resolve().parent.parent

_OMIT = object()


# === Shared helpers ==========================================================


def expect_ingress_error(code, fn, *args, **kwargs):
    with pytest.raises(ji.IngressError) as info:
        fn(*args, **kwargs)
    error = info.value
    assert error.code == code
    assert error.args == (code,)
    assert error.__cause__ is None
    assert error.__context__ is None
    return error


def _minimal_body(**overrides) -> dict:
    body = {
        "groupKey": "g",
        "truncatedAlerts": 0,
        "alerts": [{"fingerprint": "5e8d72dc87b1ff35", "status": "firing"}],
    }
    body.update(overrides)
    return body


def _dump(body: dict) -> bytes:
    return json.dumps(body).encode("utf-8")


def _body_starts_at(value, fingerprint: str = "5e8d72dc87b1ff35") -> dict:
    alert = {"fingerprint": fingerprint, "status": "firing"}
    if value is not _OMIT:
        alert["startsAt"] = value
    return {"groupKey": "g", "alerts": [alert]}


def _body_with_raw_values(values_json: str) -> bytes:
    return (
        '{"groupKey":"g","alerts":[{"fingerprint":"5e8d72dc87b1ff35","status":"firing",'
        f'"values":{values_json}}}]}}'
    ).encode("ascii")


def _source_accepts_fingerprint(fingerprint) -> bool:
    alert = js.SourceAlert(fingerprint=fingerprint, status="firing", values=None, starts_at=None)
    record = js.SourceRecord(
        source_group=js.source_group_digest("g"), alerts=(alert,), truncated_alerts=None,
        body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )
    try:
        js.validate_source(record)
    except js.SourceError:
        return False
    return True


def _source_accepts_ref_id(ref_id) -> bool:
    alert = js.SourceAlert(
        fingerprint="a" * 16, status="firing", values=((ref_id, "1"),), starts_at=None,
    )
    record = js.SourceRecord(
        source_group=js.source_group_digest("g"), alerts=(alert,), truncated_alerts=None,
        body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )
    try:
        js.validate_source(record)
    except js.SourceError:
        return False
    return True


def _source_accepts_starts_at(value) -> bool:
    alert = js.SourceAlert(fingerprint="a" * 16, status="firing", values=None, starts_at=value)
    record = js.SourceRecord(
        source_group=js.source_group_digest("g"), alerts=(alert,), truncated_alerts=None,
        body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )
    try:
        js.validate_source(record)
    except js.SourceError:
        return False
    return True


# === I1: the minimal admissible body =========================================


def test_i1_minimal_admissible_body():
    raw = b'{"groupKey":"g","alerts":[{"fingerprint":"f","status":"firing"}]}'
    outcome = ji.sanitize_notification(raw)
    assert outcome.refusal is None
    source = outcome.source
    assert source.truncated_alerts is None
    assert source.alerts[0].values is None
    assert source.alerts[0].starts_at is None
    assert outcome.starts_at_dropped == ()
    assert source.provenance == js.HTTP_PROVENANCE


# === I2: body_digest known answers ===========================================


def test_i2_body_digest_known_answer_empty():
    assert ji.body_digest(b"") == (
        "5f669e48d59a42bd8cfd8f738d4498286a8241edbdee93abfc679eb0b3793fb7"
    )


@pytest.mark.parametrize("body", [b"", b"x", b"{}", b"a" * 1000])
def test_i2_body_digest_matches_manual_formula(body):
    expected = hashlib.sha256(b"rj.body.v1" + b"\x00" + body).hexdigest()
    assert ji.body_digest(body) == expected


# === I3: payment-line-1-shaped mutation table =================================


NUMBER_CASES = [
    ('{"A":100.0}', "100"),
    ('{"A":1e-7}', "1e-07"),
    ('{"A":-0}', "0"),
    ('{"A":1e-400}', "0"),
    ('{"A":9007199254740991}', "9007199254740991"),
]


@pytest.mark.parametrize("values_json,expected", NUMBER_CASES)
def test_i3_number_canonicalization(values_json, expected):
    outcome = ji.sanitize_notification(_body_with_raw_values(values_json))
    assert outcome.refusal is None
    assert outcome.source.alerts[0].values == (("A", expected),)


def test_i3_values_absent():
    body = _minimal_body()
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.source.alerts[0].values is None


def test_i3_values_null():
    body = _minimal_body()
    body["alerts"][0]["values"] = None
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.source.alerts[0].values is None


def test_i3_values_empty_object():
    body = _minimal_body()
    body["alerts"][0]["values"] = {}
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.source.alerts[0].values == ()


def test_i3_values_with_null_member():
    body = _minimal_body()
    body["alerts"][0]["values"] = {"A": None}
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.source.alerts[0].values == (("A", None),)


def test_i3_values_sorted_by_ref_id():
    outcome = ji.sanitize_notification(_body_with_raw_values('{"C":3,"A":1,"B":2}'))
    assert outcome.refusal is None
    assert outcome.source.alerts[0].values == (("A", "1"), ("B", "2"), ("C", "3"))


@pytest.mark.parametrize("truncated", [7, 2**31 - 1])
def test_i3_truncated_alerts_present(truncated):
    body = _minimal_body(truncatedAlerts=truncated)
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.refusal is None
    assert outcome.source.truncated_alerts == truncated


def test_i3_truncated_alerts_null():
    body = _minimal_body(truncatedAlerts=None)
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.source.truncated_alerts is None


def test_i3_truncated_alerts_absent():
    body = _minimal_body()
    del body["truncatedAlerts"]
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.source.truncated_alerts is None


def test_i3_fixture_w1_fingerprint_accepted():
    body = _minimal_body()
    body["alerts"][0]["fingerprint"] = "fixture-w1"
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.refusal is None
    assert outcome.source.alerts[0].fingerprint == "fixture-w1"


def test_i3_ignored_fields_do_not_change_the_record():
    baseline = ji.sanitize_notification(_dump(_minimal_body())).source
    body = _minimal_body()
    body["alerts"][0]["imageURL"] = "http://example/img.png"
    body["orgId"] = 7
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.refusal is None
    assert dataclasses.replace(outcome.source, body_digest="x") == dataclasses.replace(
        baseline, body_digest="x",
    )
    assert outcome.source.body_digest != baseline.body_digest


# === Gap 1: shape/type branches always return, never raise ===================


def _values_body(values) -> dict:
    body = _minimal_body()
    body["alerts"][0]["values"] = values
    return body


SHAPE_TYPE_CASES = [
    ("no_alerts_key", {"groupKey": "g"}, "ingress_shape"),
    ("alerts_is_an_object", {"groupKey": "g", "alerts": {}}, "ingress_shape"),
    ("alerts_is_empty", {"groupKey": "g", "alerts": []}, "ingress_shape"),
    ("alerts_element_is_an_int", {"groupKey": "g", "alerts": [5]}, "ingress_shape"),
    (
        "alerts_element_is_a_nested_array",
        {"groupKey": "g", "alerts": [["x"]]},
        "ingress_shape",
    ),
    (
        "group_key_is_an_int",
        {"groupKey": 5, "alerts": [{"fingerprint": "f", "status": "firing"}]},
        "ingress_group_key",
    ),
    ("values_is_an_array", _values_body([1]), "ingress_values"),
    ("values_is_a_string", _values_body("x"), "ingress_values"),
]


@pytest.mark.parametrize(
    "label,body,expected_code", SHAPE_TYPE_CASES, ids=[case[0] for case in SHAPE_TYPE_CASES],
)
def test_gap1_shape_type_branches_return_an_outcome_and_never_raise(label, body, expected_code):
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.source is None, label
    refusal = outcome.refusal
    assert refusal.code == expected_code, label
    ji.refusal_to_json(refusal)  # must succeed, never raise


# === Gap 2: exact-type rules for values, truncatedAlerts and status ==========


VALUES_EXACT_TYPE_CASES = [
    ({"A": True}, "bool_value"),
    ({"A": [1]}, "array_value"),
    ({"A": {}}, "object_value"),
]


@pytest.mark.parametrize(
    "values,label", VALUES_EXACT_TYPE_CASES, ids=[case[1] for case in VALUES_EXACT_TYPE_CASES],
)
def test_gap2_values_exact_type_rules(values, label):
    outcome = ji.sanitize_notification(_dump(_values_body(values)))
    assert outcome.refusal is not None, label
    assert outcome.refusal.code == "ingress_values", label


TRUNCATED_EXACT_TYPE_CASES = [
    (True, "bool"),
    (2**31, "one_above_max"),
    (1.5, "decimal"),
    ("7", "string"),
]


@pytest.mark.parametrize(
    "truncated,label", TRUNCATED_EXACT_TYPE_CASES,
    ids=[case[1] for case in TRUNCATED_EXACT_TYPE_CASES],
)
def test_gap2_truncated_alerts_exact_type_rules(truncated, label):
    body = _minimal_body(truncatedAlerts=truncated)
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.refusal is not None, label
    assert outcome.refusal.code == "ingress_truncated", label


@pytest.mark.parametrize("status", ["FIRING", "Firing"])
def test_gap2_status_is_exact_and_case_sensitive(status):
    body = _minimal_body()
    body["alerts"][0]["status"] = status
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.refusal is not None
    assert outcome.refusal.code == "ingress_status"


# === I4: startsAt table ========================================================


@pytest.mark.parametrize("value", [ji.GO_ZERO_TIME, None, _OMIT])
def test_i4_starts_at_none_and_unreported(value):
    outcome = ji.sanitize_notification(_dump(_body_starts_at(value)))
    assert outcome.refusal is None
    assert outcome.source.alerts[0].starts_at is None
    assert outcome.starts_at_dropped == ()


def test_i4_starts_at_kept_with_max_fraction():
    value = "2026-09-17T21:56:20." + "1" * 9 + "Z"
    outcome = ji.sanitize_notification(_dump(_body_starts_at(value)))
    assert outcome.refusal is None
    assert outcome.source.alerts[0].starts_at == value
    assert outcome.starts_at_dropped == ()


def test_i4_starts_at_kept_one_second_after_zero_time():
    value = "0001-01-01T00:00:01Z"
    outcome = ji.sanitize_notification(_dump(_body_starts_at(value)))
    assert outcome.source.alerts[0].starts_at == value


DROPPED_STARTS_AT = [
    "2026-09-17T23:56:20+02:00",
    "2026-09-17T18:26:20-05:30",
    "2026-02-30T00:00:00Z",
    "2026-09-17T23:59:60Z",
    "0000-01-01T00:00:00Z",
    "yesterday",
    5,
    "x" * 100_000,
]


@pytest.mark.parametrize("value", DROPPED_STARTS_AT)
def test_i4_starts_at_dropped_and_named(value):
    outcome = ji.sanitize_notification(_dump(_body_starts_at(value)))
    assert outcome.refusal is None
    assert outcome.source.alerts[0].starts_at is None
    assert outcome.starts_at_dropped == ("5e8d72dc87b1ff35",)


def test_i4_multiple_members_two_dropped_sorted():
    body = {
        "groupKey": "g",
        "alerts": [
            {"fingerprint": "c" * 16, "status": "firing", "startsAt": "bogus"},
            {"fingerprint": "a" * 16, "status": "firing", "startsAt": "2026-01-01T00:00:00Z"},
            {"fingerprint": "b" * 16, "status": "firing", "startsAt": 5},
        ],
    }
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.refusal is None
    assert outcome.starts_at_dropped == ("b" * 16, "c" * 16)


def test_i4_dropped_starts_at_never_changes_dedupe_key():
    baseline = ji.sanitize_notification(_dump(_body_starts_at(_OMIT))).source
    for value in DROPPED_STARTS_AT:
        outcome = ji.sanitize_notification(_dump(_body_starts_at(value)))
        assert js.dedupe_key(outcome.source) == js.dedupe_key(baseline)


def test_i4_none_of_the_table_refuses():
    for value in [ji.GO_ZERO_TIME, None, _OMIT, *DROPPED_STARTS_AT]:
        outcome = ji.sanitize_notification(_dump(_body_starts_at(value)))
        assert outcome.refusal is None


# === Gap 6: an ignored endsAt never leaks into starts_at =======================


def test_gap6_ignored_ends_at_does_not_fall_back_into_starts_at():
    body = _body_starts_at(_OMIT)
    body["alerts"][0]["endsAt"] = "2026-09-17T22:05:20Z"
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.refusal is None
    assert outcome.source.alerts[0].starts_at is None
    assert outcome.starts_at_dropped == ()

    baseline = ji.sanitize_notification(_dump(_body_starts_at(_OMIT))).source
    assert dataclasses.replace(outcome.source, body_digest="x") == dataclasses.replace(
        baseline, body_digest="x",
    )


# === I5: one refusal per code, with summary-field shape ======================


def _refuse(body: dict) -> ji.IngressRefusal:
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.source is None, "expected a refusal"
    return outcome.refusal


def test_i5_ingress_too_large():
    big = b"0" * (ji.MAX_INGRESS_BODY_BYTES + 1)
    outcome = ji.sanitize_notification(big)
    refusal = outcome.refusal
    assert refusal.code == "ingress_too_large"
    assert refusal.body_bytes == len(big)
    assert refusal.body_digest is None
    assert refusal.source_group is None and refusal.refused_group is None
    assert refusal.alerts is None and refusal.members == ()


def test_i5_ingress_json_invalid():
    raw = b"{"
    outcome = ji.sanitize_notification(raw)
    refusal = outcome.refusal
    assert refusal.code == "ingress_json_invalid"
    assert refusal.body_bytes == len(raw)
    assert refusal.body_digest is not None
    assert refusal.source_group is None and refusal.refused_group is None
    assert refusal.alerts is None


def test_i5_ingress_shape_root_not_object():
    refusal = _refuse_raw(b"5")
    assert refusal.code == "ingress_shape"
    assert refusal.body_digest is not None
    assert refusal.source_group is None and refusal.refused_group is None
    assert refusal.alerts is None


def _refuse_raw(raw: bytes) -> ji.IngressRefusal:
    outcome = ji.sanitize_notification(raw)
    assert outcome.source is None
    return outcome.refusal


def test_i5_ingress_group_key():
    body = {"alerts": [{"fingerprint": "f", "status": "firing"}]}
    refusal = _refuse(body)
    assert refusal.code == "ingress_group_key"
    assert refusal.body_digest is not None
    assert refusal.source_group is None and refusal.refused_group is None
    assert refusal.alerts is None


def test_i5_ingress_truncated():
    body = _minimal_body(truncatedAlerts=-1)
    refusal = _refuse(body)
    assert refusal.code == "ingress_truncated"
    assert refusal.source_group is not None and refusal.refused_group is None
    assert refusal.alerts is None


def test_i5_ingress_fingerprint():
    body = _minimal_body()
    body["alerts"][0]["fingerprint"] = "bad fingerprint"
    refusal = _refuse(body)
    assert refusal.code == "ingress_fingerprint"
    assert refusal.source_group is not None
    assert refusal.alerts is None


def test_i5_ingress_status():
    body = _minimal_body()
    body["alerts"][0]["status"] = "BOGUS"
    refusal = _refuse(body)
    assert refusal.code == "ingress_status"
    assert refusal.source_group is not None
    assert refusal.alerts is None


def test_i5_ingress_values():
    body = _minimal_body()
    body["alerts"][0]["values"] = {"A": "not a number"}
    refusal = _refuse(body)
    assert refusal.code == "ingress_values"
    assert refusal.source_group is not None
    assert refusal.alerts is None


def test_i5_ingress_duplicate_fingerprint():
    body = {
        "groupKey": "g",
        "alerts": [
            {"fingerprint": "same", "status": "firing"},
            {"fingerprint": "same", "status": "resolved"},
        ],
    }
    refusal = _refuse(body)
    assert refusal.code == "ingress_duplicate_fingerprint"
    assert refusal.source_group is not None
    assert refusal.alerts is None


def test_i5_ingress_json_unsupported():
    raw = json.dumps({
        "groupKey": "g", "message": "a\u0000b",
        "alerts": [{"fingerprint": "f", "status": "firing"}],
    }).encode()
    refusal = _refuse_raw(raw)
    assert refusal.code == "ingress_json_unsupported"
    assert refusal.body_digest is not None
    assert refusal.source_group is None and refusal.refused_group is None
    assert refusal.alerts is None and refusal.members == ()


def test_i5_ingress_group_key_unsupported():
    body = {"groupKey": "Démo", "alerts": [{"fingerprint": "f", "status": "firing"}]}
    refusal = _refuse(body)
    assert refusal.code == "ingress_group_key_unsupported"
    assert refusal.source_group is None
    assert refusal.refused_group is not None
    assert refusal.alerts == 1 and refusal.members == (("f", "firing"),)


def test_i5_ingress_ref_id_unsupported():
    body = _minimal_body()
    body["alerts"][0]["values"] = {"Query 1": 1}
    refusal = _refuse(body)
    assert refusal.code == "ingress_ref_id_unsupported"
    assert refusal.source_group is not None
    assert refusal.alerts == 1 and len(refusal.members) == 1


def test_i5_ingress_too_many_alerts():
    body = {
        "groupKey": "g",
        "alerts": [{"fingerprint": f"{i:016x}", "status": "firing"} for i in range(33)],
    }
    refusal = _refuse(body)
    assert refusal.code == "ingress_too_many_alerts"
    assert refusal.alerts == 33
    assert len(refusal.members) == 32
    assert refusal.members_omitted == 1


def test_i5_ingress_too_many_values():
    values = {f"r{i:02d}": 1 for i in range(65)}
    body = {"groupKey": "g", "alerts": [{"fingerprint": "f", "status": "firing", "values": values}]}
    refusal = _refuse(body)
    assert refusal.code == "ingress_too_many_values"
    assert refusal.alerts == 1


def test_i5_ingress_record_too_large():
    alerts = [
        {
            "fingerprint": f"{i:064x}", "status": "firing",
            "values": {"A": 0.123456789012345, "B": 0.2},
        }
        for i in range(24)
    ]
    body = {"groupKey": "g", "alerts": alerts}
    refusal = _refuse(body)
    assert refusal.code == "ingress_record_too_large"
    assert refusal.alerts == 24


DIVERGENCE_PATCHES = [
    ("validate_source", js.SourceError("source_order")),
    ("validate_source", JSONPolicyError("json_number")),
    ("canonical_number", js.SourceError("source_number")),
    ("canonical_number", JSONPolicyError("json_number")),
    ("source_group_digest", JSONPolicyError("json_number")),
]


@pytest.mark.parametrize("target,exception", DIVERGENCE_PATCHES)
def test_i5_ingress_divergence_via_monkeypatch(monkeypatch, target, exception):
    monkeypatch.setattr(ji, target, lambda *a, **k: (_ for _ in ()).throw(exception))
    body = _minimal_body()
    body["alerts"][0]["values"] = {"A": 1}
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.source is None
    assert outcome.refusal.code == "ingress_divergence"


def test_i5_exercised_codes_equal_the_closed_set():
    # Gap 7: rebuilt from the actual outcomes of one minimal mutation per code
    # (mirroring the I5 rows above), instead of a hand-copied literal, so an
    # extra code slipped into INGRESS_REFUSAL_CODES that no real body ever
    # produces cannot hide behind a matching hardcoded set.
    exercised: set[str] = set()

    big = b"0" * (ji.MAX_INGRESS_BODY_BYTES + 1)
    exercised.add(_refuse_raw(big).code)
    exercised.add(_refuse_raw(b"{").code)
    exercised.add(_refuse_raw(b"5").code)
    exercised.add(_refuse({"alerts": [{"fingerprint": "f", "status": "firing"}]}).code)
    exercised.add(_refuse(_minimal_body(truncatedAlerts=-1)).code)

    bad_fingerprint = _minimal_body()
    bad_fingerprint["alerts"][0]["fingerprint"] = "bad fingerprint"
    exercised.add(_refuse(bad_fingerprint).code)

    bad_status = _minimal_body()
    bad_status["alerts"][0]["status"] = "BOGUS"
    exercised.add(_refuse(bad_status).code)

    bad_values = _minimal_body()
    bad_values["alerts"][0]["values"] = {"A": "not a number"}
    exercised.add(_refuse(bad_values).code)

    exercised.add(_refuse({
        "groupKey": "g",
        "alerts": [
            {"fingerprint": "same", "status": "firing"},
            {"fingerprint": "same", "status": "resolved"},
        ],
    }).code)

    nul_message = json.dumps({
        "groupKey": "g", "message": "a\u0000b",
        "alerts": [{"fingerprint": "f", "status": "firing"}],
    }).encode()
    exercised.add(_refuse_raw(nul_message).code)

    exercised.add(
        _refuse({"groupKey": "Démo", "alerts": [{"fingerprint": "f", "status": "firing"}]}).code
    )

    bad_ref_id = _minimal_body()
    bad_ref_id["alerts"][0]["values"] = {"Query 1": 1}
    exercised.add(_refuse(bad_ref_id).code)

    too_many_alerts = {
        "groupKey": "g",
        "alerts": [{"fingerprint": f"{i:016x}", "status": "firing"} for i in range(33)],
    }
    exercised.add(_refuse(too_many_alerts).code)

    too_many_values = {
        "groupKey": "g",
        "alerts": [{
            "fingerprint": "f", "status": "firing",
            "values": {f"r{i:02d}": 1 for i in range(65)},
        }],
    }
    exercised.add(_refuse(too_many_values).code)

    record_too_large = {
        "groupKey": "g",
        "alerts": [
            {
                "fingerprint": f"{i:064x}", "status": "firing",
                "values": {"A": 0.123456789012345, "B": 0.2},
            }
            for i in range(24)
        ],
    }
    exercised.add(_refuse(record_too_large).code)

    for target, exception in DIVERGENCE_PATCHES:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                ji, target,
                lambda *a, exception=exception, **k: (_ for _ in ()).throw(exception),
            )
            body = _minimal_body()
            body["alerts"][0]["values"] = {"A": 1}
            outcome = ji.sanitize_notification(_dump(body))
            assert outcome.source is None
            exercised.add(outcome.refusal.code)

    assert exercised == ji.INGRESS_REFUSAL_CODES


# === I6: precedence ============================================================


def test_i6_bad_status_beats_bad_ref_id_either_order():
    body_a = {
        "groupKey": "g",
        "alerts": [
            {"fingerprint": "a" * 16, "status": "firing", "values": {"Query 1": 1}},
            {"fingerprint": "b" * 16, "status": "BOGUS"},
        ],
    }
    body_b = {
        "groupKey": "g",
        "alerts": [
            {"fingerprint": "b" * 16, "status": "BOGUS"},
            {"fingerprint": "a" * 16, "status": "firing", "values": {"Query 1": 1}},
        ],
    }
    assert _refuse(body_a).code == "ingress_status"
    assert _refuse(body_b).code == "ingress_status"


@pytest.mark.parametrize("values", [
    {"Query 1": 1, "b": "x"},
    {"Query 1": 1, "A": "x"},
])
def test_i6_mixed_values_gives_ingress_values_any_key_order(values):
    body = _minimal_body()
    body["alerts"][0]["values"] = values
    assert _refuse(body).code == "ingress_values"


def test_i6_non_ascii_group_key_with_bad_status_carries_refused_group():
    body = {
        "groupKey": "Démo",
        "alerts": [{"fingerprint": "f", "status": "BOGUS"}],
    }
    refusal = _refuse(body)
    assert refusal.code == "ingress_status"
    assert refusal.refused_group is not None
    assert refusal.source_group is None


def test_i6_empty_group_key_with_bad_status_gives_group_key():
    body = {"groupKey": "", "alerts": [{"fingerprint": "f", "status": "BOGUS"}]}
    assert _refuse(body).code == "ingress_group_key"


def test_i6_truncated_negative_with_bad_status_gives_truncated():
    body = _minimal_body(truncatedAlerts=-1)
    body["alerts"][0]["status"] = "BOGUS"
    assert _refuse(body).code == "ingress_truncated"


def test_i6_fortieth_member_bad_status():
    alerts = [{"fingerprint": f"{i:016x}", "status": "firing"} for i in range(39)]
    alerts.append({"fingerprint": f"{39:016x}", "status": "BOGUS"})
    body = {"groupKey": "g", "alerts": alerts}
    assert _refuse(body).code == "ingress_status"


def test_i6_non_ascii_group_key_bad_ref_id_forty_members():
    alerts = [{"fingerprint": f"{i:016x}", "status": "firing"} for i in range(39)]
    alerts.append(
        {"fingerprint": f"{39:016x}", "status": "firing", "values": {"Query 1": 1}},
    )
    body = {"groupKey": "Démo", "alerts": alerts}
    assert _refuse(body).code == "ingress_group_key_unsupported"


def test_i6_bad_ref_id_forty_members():
    alerts = [{"fingerprint": f"{i:016x}", "status": "firing"} for i in range(39)]
    alerts.append(
        {"fingerprint": f"{39:016x}", "status": "firing", "values": {"Query 1": 1}},
    )
    body = {"groupKey": "g", "alerts": alerts}
    refusal = _refuse(body)
    assert refusal.code == "ingress_ref_id_unsupported"
    assert refusal.alerts == 40 and len(refusal.members) == 32 and refusal.members_omitted == 8


def test_i6_forty_members_too_many_values():
    alerts = [
        {"fingerprint": f"{i:016x}", "status": "firing", "values": {"A": 1, "B": 1, "C": 1}}
        for i in range(40)
    ]
    body = {"groupKey": "g", "alerts": alerts}
    refusal = _refuse(body)
    assert refusal.code == "ingress_too_many_alerts"
    assert refusal.alerts == 40 and len(refusal.members) == 32 and refusal.members_omitted == 8


def test_i6_unread_fields_never_refuse():
    body = _minimal_body()
    body["version"] = "2"
    body["status"] = "x"
    body["title"] = 7
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.refusal is None


# === Gap 5: duplicate-fingerprint precedence (S9 beats S11 and the S13 bound) ==


def test_gap5_duplicate_fingerprint_beats_non_ascii_group_key():
    body = {
        "groupKey": "Démo",
        "alerts": [
            {"fingerprint": "same", "status": "firing"},
            {"fingerprint": "same", "status": "resolved"},
        ],
    }
    refusal = _refuse(body)
    assert refusal.code == "ingress_duplicate_fingerprint"
    assert refusal.alerts is None


def test_gap5_duplicate_fingerprint_beats_too_many_alerts_above_32():
    alerts = [{"fingerprint": f"{i:016x}", "status": "firing"} for i in range(33)]
    alerts[5] = dict(alerts[5], fingerprint=alerts[0]["fingerprint"])
    body = {"groupKey": "g", "alerts": alerts}
    refusal = _refuse(body)
    assert refusal.code == "ingress_duplicate_fingerprint"
    assert refusal.alerts is None


# === I7: grammar parity with validate_source ==================================


FINGERPRINT_GRAMMAR_CASES = [
    "a" * 64, "a" * 65, "", "٥" * 5, "a b", "normal-fp.1_2",
]


@pytest.mark.parametrize("fingerprint", FINGERPRINT_GRAMMAR_CASES)
def test_i7_fingerprint_grammar_parity(fingerprint):
    body = {"groupKey": "g", "alerts": [{"fingerprint": fingerprint, "status": "firing"}]}
    outcome = ji.sanitize_notification(_dump(body))
    accepted = outcome.refusal is None
    assert accepted == _source_accepts_fingerprint(fingerprint)
    if not accepted:
        assert outcome.refusal.code == "ingress_fingerprint"


REF_ID_GRAMMAR_CASES = [
    "a" * 32, "a" * 33, "", "٥" * 5, "a b", "Query.1-2_3",
]


@pytest.mark.parametrize("ref_id", REF_ID_GRAMMAR_CASES)
def test_i7_ref_id_grammar_parity(ref_id):
    body = _minimal_body()
    body["alerts"][0]["values"] = {ref_id: 1}
    outcome = ji.sanitize_notification(_dump(body))
    accepted = outcome.refusal is None
    assert accepted == _source_accepts_ref_id(ref_id)
    if not accepted:
        assert outcome.refusal.code == "ingress_ref_id_unsupported"


STARTS_AT_GRAMMAR_CASES = [
    "2026-09-17T21:56:20Z",
    "٢٠٢٦-09-17T21:56:20Z",  # Arabic-Indic digit year
    "2026-09-17T21:56:20." + "1" * 9 + "Z",   # 30 characters: kept
    "2026-09-17T21:56:20." + "1" * 10 + "Z",  # 31 characters: dropped
]


@pytest.mark.parametrize("value", STARTS_AT_GRAMMAR_CASES)
def test_i7_starts_at_grammar_parity(value):
    outcome = ji.sanitize_notification(_dump(_body_starts_at(value)))
    assert outcome.refusal is None  # startsAt never refuses
    kept = outcome.source.alerts[0].starts_at is not None
    assert kept == _source_accepts_starts_at(value)


def test_i7_no_row_gives_divergence():
    for fingerprint in FINGERPRINT_GRAMMAR_CASES:
        body = {"groupKey": "g", "alerts": [{"fingerprint": fingerprint, "status": "firing"}]}
        outcome = ji.sanitize_notification(_dump(body))
        if outcome.refusal is not None:
            assert outcome.refusal.code != "ingress_divergence"
    for ref_id in REF_ID_GRAMMAR_CASES:
        body = _minimal_body()
        body["alerts"][0]["values"] = {ref_id: 1}
        outcome = ji.sanitize_notification(_dump(body))
        if outcome.refusal is not None:
            assert outcome.refusal.code != "ingress_divergence"


# === I8: closed sets ===========================================================


def test_i8_http_status_domain_equals_refusal_codes():
    assert set(ji.INGRESS_HTTP_STATUS) == ji.INGRESS_REFUSAL_CODES
    assert set(ji.INGRESS_HTTP_STATUS.values()) <= {400, 413, 422, 500}


def test_i8_member_codes_are_exactly_the_five_and_all_422():
    assert ji.MEMBER_CODES == frozenset({
        "ingress_group_key_unsupported", "ingress_ref_id_unsupported",
        "ingress_too_many_alerts", "ingress_too_many_values", "ingress_record_too_large",
    })
    for code in ji.MEMBER_CODES:
        assert ji.INGRESS_HTTP_STATUS[code] == 422


def test_i8_json_refusal_codes_total_over_json_error_codes():
    assert set(ji.JSON_REFUSAL_CODES) == forwarder_json.JSON_ERROR_CODES
    assert set(ji.JSON_REFUSAL_CODES.values()) <= ji.INGRESS_REFUSAL_CODES
    assert ji.JSON_REFUSAL_CODES["json_unicode"] == "ingress_json_unsupported"
    assert ji.INGRESS_HTTP_STATUS["ingress_json_unsupported"] == 422


def test_i8_ingress_error_args():
    for code in ji.INGRESS_ERROR_CODES:
        assert ji.IngressError(code).args == (code,)


# === I9: the refusal summary ===================================================


def test_i9_refusal_to_json_exact_keys_and_no_http_status():
    refusal = ji.oversize_refusal(ji.MAX_INGRESS_BODY_BYTES + 1)
    result = ji.refusal_to_json(refusal)
    assert set(result) == {
        "alerts", "body_bytes", "body_digest", "code", "members",
        "members_omitted", "refused_group", "resolved", "source_group",
    }
    assert "http_status" not in result
    canonical_json(result, ascii_only=True)  # succeeds: canonical, ASCII


def test_i9_resolved_listed_first_and_a_firing_one_omitted():
    alerts = [{"fingerprint": f"{i:016x}", "status": "firing"} for i in range(32)]
    alerts.append({"fingerprint": "f" * 16, "status": "resolved"})
    body = {"groupKey": "Démo", "alerts": alerts}
    outcome = ji.sanitize_notification(_dump(body))
    refusal = outcome.refusal
    assert refusal.code == "ingress_group_key_unsupported"
    assert refusal.alerts == 33
    assert refusal.members[0] == ("f" * 16, "resolved")
    assert len(refusal.members) == 32
    assert refusal.members_omitted == 1
    listed = {member[0] for member in refusal.members}
    omitted = [f"{i:016x}" for i in range(32) if f"{i:016x}" not in listed]
    assert len(omitted) == 1


def test_i9_worst_case_summary_within_bound():
    members = tuple((f"{i:064x}", "resolved") for i in range(32))
    refusal = ji.IngressRefusal(
        code="ingress_group_key_unsupported", body_bytes=ji.MAX_INGRESS_BODY_BYTES,
        body_digest="0" * 64, source_group=None, refused_group="1" * 64,
        alerts=256, resolved=256, members=members, members_omitted=224,
    )
    encoded = canonical_json(ji.refusal_to_json(refusal), ascii_only=True)
    assert len(encoded) <= 3_072
    assert len(encoded) <= ji.MAX_REFUSAL_JSON_BYTES


def _valid_member_refusal() -> ji.IngressRefusal:
    resolved = [(f"{i:064x}", "resolved") for i in range(10)]
    firing = [(f"{i:064x}", "firing") for i in range(10, 32)]
    members = tuple(sorted(resolved + firing, key=ji._member_key))
    return ji.IngressRefusal(
        code="ingress_too_many_alerts", body_bytes=1_000, body_digest="0" * 64,
        source_group="a" * 64, refused_group=None, alerts=40, resolved=10,
        members=members, members_omitted=8,
    )


def test_i9_valid_member_refusal_baseline_is_accepted():
    ji.refusal_to_json(_valid_member_refusal())


FORGED_REFUSALS = [
    ("body_bytes_huge", lambda r: dataclasses.replace(r, body_bytes=2**60)),
    ("body_bytes_bool", lambda r: dataclasses.replace(r, body_bytes=True)),
    (
        "alerts_none_with_members",
        lambda r: dataclasses.replace(r, alerts=None, resolved=None, members_omitted=0),
    ),
    ("alerts_257", lambda r: dataclasses.replace(r, alerts=257, members_omitted=225)),
    ("resolved_exceeds_alerts", lambda r: dataclasses.replace(r, resolved=41)),
    ("members_unsorted", lambda r: dataclasses.replace(r, members=tuple(reversed(r.members)))),
    (
        "members_duplicate_fingerprint",
        lambda r: dataclasses.replace(
            r, members=(r.members[0],) + r.members[1:-1] + (r.members[0],),
        ),
    ),
    (
        "members_space_in_fingerprint",
        lambda r: dataclasses.replace(
            r, members=(("bad fp", "firing"),) + r.members[1:],
        ),
    ),
    ("members_omitted_inconsistent", lambda r: dataclasses.replace(r, members_omitted=999)),
    ("resolved_mismatches_listed", lambda r: dataclasses.replace(r, resolved=5)),
    (
        "members_on_json_invalid",
        lambda r: dataclasses.replace(
            r, code="ingress_json_invalid", source_group=None, refused_group=None,
        ),
    ),
    (
        "group_on_json_invalid",
        lambda r: dataclasses.replace(
            r, code="ingress_json_invalid", alerts=None, resolved=None,
            members=(), members_omitted=0,
        ),
    ),
    (
        "both_groups_set",
        lambda r: dataclasses.replace(
            r, code="ingress_fingerprint", refused_group="b" * 64,
            alerts=None, resolved=None, members=(), members_omitted=0,
        ),
    ),
    (
        "digest_on_too_large",
        lambda r: dataclasses.replace(
            r, code="ingress_too_large", body_bytes=ji.MAX_INGRESS_BODY_BYTES + 1,
            alerts=None, resolved=None, members=(), members_omitted=0, source_group=None,
        ),
    ),
    (
        "small_body_bytes_on_too_large",
        lambda r: dataclasses.replace(
            r, code="ingress_too_large", body_bytes=100, body_digest=None,
            alerts=None, resolved=None, members=(), members_omitted=0,
            source_group=None,
        ),
    ),
    (
        "missing_counts_on_too_many_alerts",
        lambda r: dataclasses.replace(
            r, alerts=None, resolved=None, members=(), members_omitted=0,
        ),
    ),
]


@pytest.mark.parametrize("name,mutate", FORGED_REFUSALS, ids=[case[0] for case in FORGED_REFUSALS])
def test_i9_forged_refusals_raise_ingress_argument(name, mutate):
    baseline = _valid_member_refusal()
    forged = mutate(baseline)
    expect_ingress_error("ingress_argument", ji.refusal_to_json, forged)


# === Gap 4: forged summaries closing the root _groups_ok/_members_ok gaps =====
#
# Each row below is otherwise-valid (every field but the one under test
# satisfies refusal_to_json's cross-field rules) so it isolates exactly one
# check: swapping source_group/refused_group, a member status outside
# ALERT_STATUSES, an out-of-range body_bytes, a missing group, or an
# alerts-count that violates the root's per-code tightening.


def test_gap4_group_key_unsupported_carrying_source_group_instead_of_refused_group():
    # D12: this code must carry only refused_group. Dropping its special-case
    # branch in _groups_ok would fall through to the generic MEMBER_CODES rule
    # (source_group set, refused_group None), which this forgery satisfies.
    refusal = ji.IngressRefusal(
        code="ingress_group_key_unsupported", body_bytes=1_000, body_digest="0" * 64,
        source_group="a" * 64, refused_group=None, alerts=1, resolved=0,
        members=(("f" * 16, "firing"),), members_omitted=0,
    )
    expect_ingress_error("ingress_argument", ji.refusal_to_json, refusal)


def test_gap4_member_status_outside_firing_or_resolved():
    refusal = ji.IngressRefusal(
        code="ingress_ref_id_unsupported", body_bytes=1_000, body_digest="0" * 64,
        source_group="a" * 64, refused_group=None, alerts=1, resolved=0,
        members=(("f" * 16, "pending"),), members_omitted=0,
    )
    expect_ingress_error("ingress_argument", ji.refusal_to_json, refusal)


def test_gap4_body_bytes_oversized_on_a_non_oversize_code():
    refusal = ji.IngressRefusal(
        code="ingress_fingerprint", body_bytes=300_000, body_digest="0" * 64,
        source_group="a" * 64, refused_group=None, alerts=None, resolved=None,
        members=(), members_omitted=0,
    )
    expect_ingress_error("ingress_argument", ji.refusal_to_json, refusal)


def test_gap4_phase1_code_with_no_group_set():
    refusal = ji.IngressRefusal(
        code="ingress_fingerprint", body_bytes=1_000, body_digest="0" * 64,
        source_group=None, refused_group=None, alerts=None, resolved=None,
        members=(), members_omitted=0,
    )
    expect_ingress_error("ingress_argument", ji.refusal_to_json, refusal)


def test_gap4_ref_id_unsupported_with_only_refused_group():
    refusal = ji.IngressRefusal(
        code="ingress_ref_id_unsupported", body_bytes=1_000, body_digest="0" * 64,
        source_group=None, refused_group="b" * 64, alerts=1, resolved=0,
        members=(("f" * 16, "firing"),), members_omitted=0,
    )
    expect_ingress_error("ingress_argument", ji.refusal_to_json, refusal)


def test_gap4_record_too_large_with_only_refused_group():
    members = tuple((f"{i:064x}", "firing") for i in range(10))
    refusal = ji.IngressRefusal(
        code="ingress_record_too_large", body_bytes=1_000, body_digest="0" * 64,
        source_group=None, refused_group="c" * 64, alerts=10, resolved=0,
        members=members, members_omitted=0,
    )
    expect_ingress_error("ingress_argument", ji.refusal_to_json, refusal)


def test_gap4_too_many_alerts_with_alerts_of_one():
    refusal = ji.IngressRefusal(
        code="ingress_too_many_alerts", body_bytes=1_000, body_digest="0" * 64,
        source_group="a" * 64, refused_group=None, alerts=1, resolved=0,
        members=(("f" * 16, "firing"),), members_omitted=0,
    )
    expect_ingress_error("ingress_argument", ji.refusal_to_json, refusal)


def test_gap4_too_many_values_with_alerts_of_forty():
    members = tuple((f"{i:064x}", "firing") for i in range(32))
    refusal = ji.IngressRefusal(
        code="ingress_too_many_values", body_bytes=1_000, body_digest="0" * 64,
        source_group="a" * 64, refused_group=None, alerts=40, resolved=0,
        members=members, members_omitted=8,
    )
    expect_ingress_error("ingress_argument", ji.refusal_to_json, refusal)


# === I10: custody ===============================================================


CANARY_SPACE = "CANARY 7f3a"
CANARY_SLASH = "CANARY-7f3a/"
CANARY_VALID = "CANARY-7f3a"


def _assert_no_leak(outcome):
    text = repr(outcome)
    for canary in (CANARY_SPACE, CANARY_SLASH, CANARY_VALID):
        assert canary not in text
    if outcome.refusal is not None:
        summary_text = repr(ji.refusal_to_json(outcome.refusal))
        for canary in (CANARY_SPACE, CANARY_SLASH, CANARY_VALID):
            assert canary not in summary_text


CANARY_BODIES = [
    {"groupKey": "g", "alerts": [{"fingerprint": CANARY_SPACE, "status": "firing"}]},
    {"groupKey": "g", "alerts": [{"fingerprint": CANARY_SLASH, "status": "firing"}]},
    {
        "groupKey": "g",
        "alerts": [{"fingerprint": "a" * 16, "status": "firing", "values": {CANARY_SPACE: 1}}],
    },
    {
        "groupKey": "g",
        "alerts": [{"fingerprint": "a" * 16, "status": "firing", "values": {CANARY_SLASH: 1}}],
    },
    {"groupKey": "g", "alerts": [{"fingerprint": "a" * 16, "status": CANARY_VALID}]},
    {
        "groupKey": "g", "message": CANARY_VALID,
        "alerts": [{"fingerprint": "a" * 16, "status": "firing"}],
    },
    {
        "groupKey": "g",
        "alerts": [{"fingerprint": "a" * 16, "status": "firing", "labels": {"x": CANARY_VALID}}],
    },
    {
        "groupKey": f"Démo-{CANARY_VALID}",
        "alerts": [{"fingerprint": "a" * 16, "status": "firing"}],
    },
    {
        "groupKey": "g",
        "alerts": [{"fingerprint": "a" * 16, "status": "firing", "startsAt": CANARY_VALID}],
    },
]


@pytest.mark.parametrize("body", CANARY_BODIES)
def test_i10a_grammar_invalid_canaries_never_leak(body):
    outcome = ji.sanitize_notification(_dump(body))
    _assert_no_leak(outcome)


def test_i10b_grammar_valid_canary_admitted_verbatim():
    body = {
        "groupKey": "g",
        "alerts": [{
            "fingerprint": CANARY_VALID, "status": "firing", "values": {CANARY_VALID: 1},
        }],
    }
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.refusal is None
    alert = outcome.source.alerts[0]
    assert alert.fingerprint == CANARY_VALID
    assert alert.values == ((CANARY_VALID, "1"),)


# === I11: arguments ==============================================================


@pytest.mark.parametrize("bad", ["x", bytearray(b"x"), memoryview(b"x"), None])
def test_i11_argument_errors(bad):
    expect_ingress_error("ingress_argument", ji.sanitize_notification, bad)
    expect_ingress_error("ingress_argument", ji.body_digest, bad)


# === I12: AST checks =============================================================


MODULE_PATH = REPOSITORY / "grafana_jsm_sandbox" / "journal_ingress.py"
ALLOWED_TOP_LEVEL_IMPORTS = frozenset({
    "__future__", "dataclasses", "datetime", "hashlib", "re", "types",
})


def _module_ast() -> ast.Module:
    source = MODULE_PATH.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(MODULE_PATH))


def test_i12_imports_match_the_exact_allowlist():
    tree = _module_ast()
    top_level_names: set[str] = set()
    from_imports: set[tuple[int, str | None, tuple[str, ...]]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level_names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            names = tuple(sorted(alias.name for alias in node.names))
            from_imports.add((node.level, module, names))
            if node.level == 0:
                top_level_names.add((module or "").split(".")[0])
        elif isinstance(node, ast.Call):
            target = node.func
            is_dunder_import = isinstance(target, ast.Name) and target.id == "__import__"
            is_importlib = isinstance(target, ast.Attribute) and target.attr == "import_module"
            assert not is_dunder_import and not is_importlib, "dynamic import call found"

    assert top_level_names == ALLOWED_TOP_LEVEL_IMPORTS
    assert (0, "__future__", ("annotations",)) in from_imports
    assert (0, "types", ("MappingProxyType",)) in from_imports
    assert (1, "forwarder_json", (
        "JSONDecimal", "JSONPolicyError", "MAX_JSON_ARRAY_ITEMS", "MAX_SAFE_INTEGER",
        "canonical_json", "parse_json",
    )) in from_imports
    assert (1, "journal_source", (
        "ALERT_STATUSES", "BODY_TAG", "HTTP_PROVENANCE", "MAX_ALERTS", "MAX_FINGERPRINT_BYTES",
        "MAX_REF_ID_BYTES", "MAX_STARTS_AT_BYTES", "MAX_TRUNCATED_ALERTS", "MAX_VALUES",
        "SourceAlert", "SourceError", "SourceRecord", "canonical_number", "source_group_digest",
        "validate_source",
    )) in from_imports
    assert len(from_imports) == 4


def test_i12_except_bodies_are_only_assign_annassign_or_pass():
    tree = _module_ast()
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    assert len(handlers) >= 5  # sanity: the module really does have handlers to check
    for handler in handlers:
        for statement in handler.body:
            assert isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Pass)), (
                f"except body has a {type(statement).__name__} at line {statement.lineno}"
            )
        for inner in ast.walk(handler):
            if isinstance(inner, ast.Raise):
                pytest.fail(f"raise inside except handler at line {inner.lineno}")


def test_i12_no_clock_or_io_calls():
    tree = _module_ast()
    banned_attrs = {"now", "utcnow", "today"}
    banned_names = {"open", "print"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Attribute):
                assert target.attr not in banned_attrs, f"banned call .{target.attr} found"
            if isinstance(target, ast.Name):
                assert target.id not in banned_names, f"banned call {target.id} found"
    # No `import logging` (or any logging use) is possible without also
    # failing the import-allowlist check in test_i12_imports_match_the_exact_allowlist.


def test_i12_all_equals_the_public_api():
    expected = frozenset({
        "GO_ZERO_TIME", "INGRESS_ERROR_CODES", "INGRESS_HTTP_STATUS", "INGRESS_REFUSAL_CODES",
        "JSON_REFUSAL_CODES", "MAX_INGRESS_BODY_BYTES", "MAX_INGRESS_STRING_BYTES",
        "MAX_REFUSAL_JSON_BYTES", "MAX_REFUSAL_MEMBERS", "MEMBER_CODES", "REFUSED_GROUP_TAG",
        "IngressError", "IngressOutcome", "IngressRefusal", "body_digest", "oversize_refusal",
        "refusal_to_json", "sanitize_notification",
    })
    assert set(ji.__all__) == expected
    assert len(ji.__all__) == len(expected)


# === I13: determinism and inertness ==============================================


def test_i13_two_calls_agree_on_goldens_and_refusals():
    bodies = [
        _dump(_minimal_body()),
        b"not json",
        _dump({"groupKey": "g", "alerts": [{"fingerprint": "bad fp", "status": "firing"}]}),
        _dump({"groupKey": "Démo", "alerts": [{"fingerprint": "f", "status": "firing"}]}),
        b"0" * (ji.MAX_INGRESS_BODY_BYTES + 1),
    ]
    for raw in bodies:
        first = ji.sanitize_notification(raw)
        second = ji.sanitize_notification(raw)
        assert first == second


def test_i13_module_globals_are_unchanged_after_calls():
    watched = [
        "INGRESS_HTTP_STATUS", "INGRESS_REFUSAL_CODES", "INGRESS_ERROR_CODES",
        "JSON_REFUSAL_CODES", "MEMBER_CODES",
    ]
    before = {name: copy.deepcopy(dict(getattr(ji, name))) if hasattr(getattr(ji, name), "items")
              else copy.deepcopy(getattr(ji, name)) for name in watched}
    ji.sanitize_notification(_dump(_minimal_body()))
    ji.sanitize_notification(b"not json")
    big = b"0" * (ji.MAX_INGRESS_BODY_BYTES + 1)
    ji.sanitize_notification(big)
    for name in watched:
        current = getattr(ji, name)
        current_value = dict(current) if hasattr(current, "items") else current
        assert current_value == before[name]


# === I14: oversize_refusal ========================================================


def test_i14_boundary_values_accepted():
    for declared in (ji.MAX_INGRESS_BODY_BYTES + 1, 2**53 - 1):
        refusal = ji.oversize_refusal(declared)
        assert refusal.code == "ingress_too_large"
        assert refusal.body_bytes == declared
        assert refusal.body_digest is None
        assert refusal.source_group is None and refusal.refused_group is None
        assert refusal.alerts is None and refusal.members == ()


@pytest.mark.parametrize("bad", [
    ji.MAX_INGRESS_BODY_BYTES, 2**53, True, "300000", -1,
])
def test_i14_boundary_values_rejected(bad):
    expect_ingress_error("ingress_argument", ji.oversize_refusal, bad)


def test_i14_sanitize_notification_agrees_with_oversize_refusal():
    size = ji.MAX_INGRESS_BODY_BYTES + 1
    body = b"0" * size
    outcome = ji.sanitize_notification(body)
    assert outcome.refusal == ji.oversize_refusal(size)


# === Gap T1: phase-1 refusals on an unsupported groupKey carry refused_group,
# never source_group (D12) =====================================================


def _demo_body(**overrides) -> dict:
    body = {
        "groupKey": "Démo",
        "truncatedAlerts": 0,
        "alerts": [{"fingerprint": "5e8d72dc87b1ff35", "status": "firing"}],
    }
    body.update(overrides)
    return body


T1_CASES = [
    ("ingress_truncated", lambda: _demo_body(truncatedAlerts=-1)),
    ("ingress_shape", lambda: _demo_body(alerts=[])),
    (
        "ingress_fingerprint",
        lambda: _demo_body(alerts=[{"fingerprint": "bad fingerprint", "status": "firing"}]),
    ),
    (
        "ingress_values",
        lambda: _demo_body(
            alerts=[{"fingerprint": "f", "status": "firing", "values": {"A": "x"}}],
        ),
    ),
    (
        "ingress_duplicate_fingerprint",
        lambda: _demo_body(alerts=[
            {"fingerprint": "same", "status": "firing"},
            {"fingerprint": "same", "status": "resolved"},
        ]),
    ),
]


@pytest.mark.parametrize("expected_code,make_body", T1_CASES, ids=[c[0] for c in T1_CASES])
def test_t1_phase1_refusal_on_unsupported_group_key_carries_refused_group(
    expected_code, make_body,
):
    refusal = _refuse(make_body())
    assert refusal.code == expected_code
    assert refusal.refused_group is not None
    assert refusal.source_group is None
    ji.refusal_to_json(refusal)  # must succeed (N16)


# === Gap T2: refusal_to_json succeeds for the group-less I5 rows (N16) ========


def test_t2_group_less_ingress_shape_summary_encodes():
    outcome = ji.sanitize_notification(b"5")
    refusal = outcome.refusal
    assert refusal.code == "ingress_shape"
    assert refusal.source_group is None and refusal.refused_group is None
    ji.refusal_to_json(refusal)  # must succeed


def test_t2_member_less_divergence_summary_encodes(monkeypatch):
    monkeypatch.setattr(
        ji, "source_group_digest",
        lambda *a, **k: (_ for _ in ()).throw(JSONPolicyError("json_number")),
    )
    outcome = ji.sanitize_notification(_dump(_minimal_body()))
    refusal = outcome.refusal
    assert refusal.code == "ingress_divergence"
    assert refusal.alerts is None and refusal.members == ()
    ji.refusal_to_json(refusal)  # must succeed


# === Gap T3: a null value still counts toward the 64-value bound (N15) =======


def test_t3_sixty_five_values_with_nulls_gives_too_many_values_not_divergence():
    values = {f"r{i:02d}": (None if i % 2 == 0 else i) for i in range(65)}
    body = {
        "groupKey": "g",
        "alerts": [{"fingerprint": "f", "status": "firing", "values": values}],
    }
    refusal = _refuse(body)
    assert refusal.code == "ingress_too_many_values"
    assert refusal.alerts == 1


# === Gap T4: exactly MAX_REFUSAL_MEMBERS (32) alerts lists all 32, omits 0 ===


def test_t4_exactly_32_alerts_too_many_values_lists_all_32_omits_none():
    alerts = [
        {"fingerprint": f"{i:016x}", "status": "firing", "values": {"A": 1, "B": 1, "C": 1}}
        for i in range(32)
    ]
    body = {"groupKey": "g", "alerts": alerts}
    refusal = _refuse(body)
    assert refusal.code == "ingress_too_many_values"
    assert refusal.alerts == 32
    assert len(refusal.members) == 32
    assert refusal.members_omitted == 0


def test_t4_exactly_32_alerts_ref_id_unsupported_lists_all_32_omits_none():
    alerts = [{"fingerprint": f"{i:016x}", "status": "firing"} for i in range(31)]
    alerts.append({"fingerprint": f"{31:016x}", "status": "firing", "values": {"Query 1": 1}})
    body = {"groupKey": "g", "alerts": alerts}
    refusal = _refuse(body)
    assert refusal.code == "ingress_ref_id_unsupported"
    assert refusal.alerts == 32
    assert len(refusal.members) == 32
    assert refusal.members_omitted == 0


# === Gap T5: pin GO_ZERO_TIME and the refused-group tag literal ==============


def test_t5_go_zero_time_literal():
    assert ji.GO_ZERO_TIME == "0001-01-01T00:00:00Z"
    # It is the actual sentinel the sanitizer treats as "not supplied":
    body = _body_starts_at("0001-01-01T00:00:00Z")
    outcome = ji.sanitize_notification(_dump(body))
    assert outcome.refusal is None
    assert outcome.source.alerts[0].starts_at is None
    assert outcome.starts_at_dropped == ()


def test_t5_refused_group_tag_literal():
    assert ji.REFUSED_GROUP_TAG == "rj.refused-group.v1"
    group_key = "Démo"
    expected = hashlib.sha256(
        b"rj.refused-group.v1" + b"\x00" + group_key.encode("utf-8")
    ).hexdigest()
    body = {"groupKey": group_key, "alerts": [{"fingerprint": "f", "status": "firing"}]}
    refusal = _refuse(body)
    assert refusal.code == "ingress_group_key_unsupported"
    assert refusal.refused_group == expected


# === Gap T6: refusal_to_json boundaries, and fingerprint before status =======


def _boundary_refusal(**overrides) -> ji.IngressRefusal:
    fields = {
        "code": "ingress_ref_id_unsupported", "body_bytes": 1_000, "body_digest": "0" * 64,
        "source_group": "a" * 64, "refused_group": None, "alerts": 1, "resolved": 0,
        "members": (("f" * 16, "firing"),), "members_omitted": 0,
    }
    fields.update(overrides)
    return ji.IngressRefusal(**fields)


def test_t6_boundary_alerts_lower_bound_one_is_accepted():
    ji.refusal_to_json(_boundary_refusal())  # alerts == 1: must not raise


def test_t6_boundary_alerts_upper_bound_256_is_accepted():
    members = tuple((f"{i:016x}", "firing") for i in range(32))
    refusal = _boundary_refusal(
        code="ingress_too_many_alerts", alerts=256, resolved=0,
        members=members, members_omitted=224,
    )
    ji.refusal_to_json(refusal)  # alerts == 256: must not raise


def test_t6_boundary_resolved_equals_alerts_is_accepted():
    members = (("f" * 16, "resolved"),)
    refusal = _boundary_refusal(alerts=1, resolved=1, members=members)
    ji.refusal_to_json(refusal)  # resolved == alerts: must not raise


def test_t6_boundary_members_omitted_zero_at_max_refusal_members_is_accepted():
    members = tuple((f"{i:016x}", "firing") for i in range(32))
    refusal = _boundary_refusal(
        code="ingress_record_too_large", alerts=32, resolved=0,
        members=members, members_omitted=0,
    )
    ji.refusal_to_json(refusal)  # alerts == len(members) == 32: must not raise


def test_t6_bad_fingerprint_and_bad_status_gives_fingerprint_first():
    body = {"groupKey": "g", "alerts": [{"fingerprint": "bad fingerprint", "status": "BOGUS"}]}
    refusal = _refuse(body)
    assert refusal.code == "ingress_fingerprint"


# === Gap S1: a permissive-__eq__ tuple subclass cannot fake an empty members
# tuple for a member-less refusal (root fix: exact-type + emptiness) =========


class _LyingTuple(tuple):
    def __eq__(self, other):
        return True

    __hash__ = tuple.__hash__


def test_s1_permissive_eq_tuple_subclass_is_rejected():
    fake_members = _LyingTuple((("f" * 16, "firing"),))
    refusal = ji.IngressRefusal(
        code="ingress_fingerprint", body_bytes=100, body_digest="0" * 64,
        source_group="a" * 64, refused_group=None, alerts=None, resolved=None,
        members=fake_members, members_omitted=0,
    )
    expect_ingress_error("ingress_argument", ji.refusal_to_json, refusal)
