"""Adversarial tests for ``journal_ingress`` (ticket 37, unit 16; Tester T,
cases X1-X12 of ``reviews/journal-ingress/implementation-plan.md``), plus the
two-phase precedence (D11), Resolved-first summaries (D8), custody (N9) and
``refusal_to_json``/``oversize_refusal`` black-box checks the task also asks
this file to cover.

Imports the three helpers ``tests/test_journal_ingress_corpus.py`` defines
(``wire``, ``capture_rows``, ``grafana_group``); defines no data file and
writes nothing. Every body is synthesized in memory from the committed
captures or from literals; nothing here posts HTTP or touches SQLite.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import random
import time

import pytest

from grafana_jsm_sandbox import journal_ingress as ji
from grafana_jsm_sandbox import journal_source as js
from grafana_jsm_sandbox.forwarder_json import JSONPolicyError, parse_json
from tests.test_journal_ingress_corpus import capture_rows, grafana_group, wire


def _row(filename: str, line_no: int) -> dict:
    for name, n, envelope in capture_rows():
        if name == filename and n == line_no:
            return envelope
    raise LookupError((filename, line_no))


CG1 = _row("notifications-paymentUnreachable.jsonl", 1)
CG2 = _row("notifications-paymentUnreachable.jsonl", 21)
BASE_BODY = copy.deepcopy(CG1["body"])
A0 = BASE_BODY["alerts"][0]


def _mut(fn):
    body = copy.deepcopy(BASE_BODY)
    fn(body)
    return wire(body)


def _alert_mut(fn):
    return _mut(lambda body: fn(body["alerts"][0]))


def _minimal_members(n, values=None, fingerprint=lambda i: f"{i:016x}"):
    """``n`` clones of payment line 1's alert (heavy labels/annotations kept),
    each with a distinct Fingerprint. Safe up to a few dozen members before
    the 262,144-byte body bound itself becomes the binding constraint --
    never used here above 40."""
    body = copy.deepcopy(BASE_BODY)
    body["alerts"] = [dict(A0, fingerprint=fingerprint(i), values=values) for i in range(n)]
    body["message"] = "m"
    return wire(body)


def _tiny_members(n):
    """``n`` genuinely minimal alerts (fingerprint/status/startsAt/values
    only), for member counts too large for ``_minimal_members`` to stay
    under the 262,144-byte body bound (X4's 256/257)."""
    body = {
        "groupKey": "g",
        "truncatedAlerts": 0,
        "alerts": [
            {
                "fingerprint": f"{i:016x}", "status": "firing",
                "startsAt": "0001-01-01T00:00:00Z", "values": None,
            }
            for i in range(n)
        ],
    }
    return wire(body)


# === X1: body bound ============================================================


def test_x1_body_bound_admitted_at_262144_refused_at_262145():
    compact = wire(BASE_BODY)
    pad = ji.MAX_INGRESS_BODY_BYTES - len(compact)
    assert pad > 0

    padded_ok = compact[:-1] + b" " * pad + b"}"
    assert len(padded_ok) == ji.MAX_INGRESS_BODY_BYTES
    assert ji.sanitize_notification(padded_ok).refusal is None

    padded_over = compact[:-1] + b" " * (pad + 1) + b"}"
    assert len(padded_over) == ji.MAX_INGRESS_BODY_BYTES + 1
    outcome = ji.sanitize_notification(padded_over)
    assert outcome.source is None
    assert outcome.refusal.code == "ingress_too_large"
    assert outcome.refusal.body_digest is None


def test_oversize_refusal_direct_and_matches_sanitize_notification():
    refusal = ji.oversize_refusal(300_000)
    assert refusal.code == "ingress_too_large"
    assert refusal.body_bytes == 300_000
    assert refusal.body_digest is None
    assert refusal.source_group is None
    assert refusal.refused_group is None
    assert refusal.members == ()

    raw = wire(BASE_BODY)
    pad = 300_000 - len(raw)
    padded = raw[:-1] + b" " * pad + b"}"
    assert len(padded) == 300_000
    outcome = ji.sanitize_notification(padded)
    assert outcome.source is None
    assert outcome.refusal == ji.oversize_refusal(300_000)

    for bad in (ji.MAX_INGRESS_BODY_BYTES, 2**53, True, "300000", -1):
        with pytest.raises(ji.IngressError) as info:
            ji.oversize_refusal(bad)
        assert info.value.args == ("ingress_argument",)
        assert info.value.__cause__ is None
        assert info.value.__context__ is None


# === X2: ignored large strings ==================================================


def test_x2_ignored_large_strings_admitted_where_the_default_parser_refuses():
    big_message = _mut(lambda body: body.update(message="m" * 200_000))
    big_description = _alert_mut(
        lambda alert: alert["annotations"].update(description="d" * 17_000)
    )
    for raw in (big_message, big_description):
        assert ji.sanitize_notification(raw).refusal is None

    # Documents the option (a) difference: the committed default cap refuses both.
    for raw in (big_message, big_description):
        with pytest.raises(JSONPolicyError) as info:
            parse_json(raw, max_bytes=262_144, numbers="finite")
        assert info.value.code == "json_string_too_long"


# === X3: the realistic N-alert template (normative generator) ================


@pytest.mark.parametrize(
    "label,status,base",
    [("CG1", "firing", CG1), ("CG1", "resolved", CG1), ("CG2", "firing", CG2),
     ("CG2", "resolved", CG2)],
    ids=["CG1-firing", "CG1-resolved", "CG2-firing", "CG2-resolved"],
)
def test_x3_message_crosses_16kib_between_19_and_20_alerts(label, status, base):
    raw19, body19 = grafana_group(base, 19, status, 2)
    raw20, body20 = grafana_group(base, 20, status, 2)
    message19 = len(body19["message"].encode())
    message20 = len(body20["message"].encode())
    assert message19 <= 16_384
    assert message20 > 16_384

    # Option (c) admits both 19 and 20; only option (a) would refuse the 20th.
    assert ji.sanitize_notification(raw19).refusal is None
    assert ji.sanitize_notification(raw20).refusal is None


@pytest.mark.parametrize(
    "label,status,base", [("CG1", "firing", CG1), ("CG2", "resolved", CG2)],
)
def test_x3_two_value_ceiling_is_28(label, status, base):
    raw28, _ = grafana_group(base, 28, status, 2)
    raw29, _ = grafana_group(base, 29, status, 2)
    outcome28 = ji.sanitize_notification(raw28)
    outcome29 = ji.sanitize_notification(raw29)
    assert outcome28.refusal is None
    assert outcome29.source is None
    assert outcome29.refusal.code == "ingress_record_too_large"
    assert outcome29.refusal.alerts == 29


def test_x3_33_alerts_give_too_many_alerts_with_32_listed_1_omitted():
    raw, _ = grafana_group(CG2, 33, "resolved", 2)
    outcome = ji.sanitize_notification(raw)
    assert outcome.source is None
    refusal = outcome.refusal
    assert refusal.code == "ingress_too_many_alerts"
    assert refusal.alerts == 33
    # Gap 3: resolved counts every member, not just the 32 listed.
    assert refusal.resolved == 33
    assert len(refusal.members) == 32
    assert refusal.members_omitted == 1


# === Gap 3: resolved counts every member, including omitted ones =============


def test_gap3_256_resolved_minimal_members_resolved_counts_all_not_just_listed():
    body = {
        "groupKey": "g",
        "truncatedAlerts": 0,
        "alerts": [
            {
                "fingerprint": f"{i:016x}", "status": "resolved",
                "startsAt": "0001-01-01T00:00:00Z", "values": None,
            }
            for i in range(256)
        ],
    }
    raw = wire(body)
    outcome = ji.sanitize_notification(raw)
    assert outcome.source is None
    refusal = outcome.refusal
    assert refusal.code == "ingress_too_many_alerts"
    assert refusal.alerts == 256
    assert refusal.resolved == 256
    assert len(refusal.members) == 32
    assert refusal.members_omitted == 224


def test_x3_three_value_ceiling_is_21():
    raw21, _ = grafana_group(CG2, 21, "resolved", 3)
    raw22, _ = grafana_group(CG2, 22, "resolved", 3)
    outcome21 = ji.sanitize_notification(raw21)
    outcome22 = ji.sanitize_notification(raw22)
    assert outcome21.refusal is None
    assert outcome22.source is None
    assert outcome22.refusal.code == "ingress_too_many_values"
    assert outcome22.refusal.alerts == 22


# === X4: member bounds =========================================================


def test_x4_32_value_free_members_admitted_33_refused():
    outcome32 = ji.sanitize_notification(_minimal_members(32))
    outcome33 = ji.sanitize_notification(_minimal_members(33))
    assert outcome32.refusal is None
    assert outcome33.source is None
    refusal = outcome33.refusal
    assert refusal.code == "ingress_too_many_alerts"
    assert refusal.alerts == 33
    assert len(refusal.members) == 32
    assert refusal.members_omitted == 1


def test_x4_256_minimal_members_too_many_alerts_257_array_cap():
    outcome256 = ji.sanitize_notification(_tiny_members(256))
    assert outcome256.source is None
    refusal256 = outcome256.refusal
    assert refusal256.code == "ingress_too_many_alerts"
    assert refusal256.alerts == 256
    assert len(refusal256.members) == 32
    assert refusal256.members_omitted == 224

    outcome257 = ji.sanitize_notification(_tiny_members(257))
    assert outcome257.source is None
    refusal257 = outcome257.refusal
    assert refusal257.code == "ingress_json_unsupported"
    assert refusal257.alerts is None
    assert refusal257.members == ()


def test_x4_64_values_admitted_65_refused():
    outcome64 = ji.sanitize_notification(
        _alert_mut(lambda a: a.update(values={f"r{i:02d}": i for i in range(64)}))
    )
    outcome65 = ji.sanitize_notification(
        _alert_mut(lambda a: a.update(values={f"r{i:02d}": i for i in range(65)}))
    )
    assert outcome64.refusal is None
    assert outcome65.source is None
    assert outcome65.refusal.code == "ingress_too_many_values"
    assert outcome65.refusal.alerts == 1


def test_x4_28_clones_of_payment_1_admitted_29_refused():
    outcome28 = ji.sanitize_notification(_minimal_members(28, values=A0["values"]))
    outcome29 = ji.sanitize_notification(_minimal_members(29, values=A0["values"]))
    assert outcome28.refusal is None
    assert outcome29.source is None
    assert outcome29.refusal.code == "ingress_record_too_large"
    assert outcome29.refusal.alerts == 29


# === X5: grammar edges =========================================================


def test_x5_fingerprint_grammar_edge():
    outcome64 = ji.sanitize_notification(_alert_mut(lambda a: a.update(fingerprint="f" * 64)))
    outcome65 = ji.sanitize_notification(_alert_mut(lambda a: a.update(fingerprint="f" * 65)))
    assert outcome64.refusal is None
    assert outcome65.refusal.code == "ingress_fingerprint"


def test_x5_ref_id_grammar_edge():
    outcome32 = ji.sanitize_notification(_alert_mut(lambda a: a.update(values={"r" * 32: 1})))
    outcome33 = ji.sanitize_notification(_alert_mut(lambda a: a.update(values={"r" * 33: 1})))
    outcome_named = ji.sanitize_notification(
        _alert_mut(lambda a: a.update(values={"Query 1": 1}))
    )
    assert outcome32.refusal is None
    assert outcome33.refusal.code == "ingress_ref_id_unsupported"
    assert outcome_named.refusal.code == "ingress_ref_id_unsupported"


def test_x5_group_key_length_grammar_edge():
    outcome1024 = ji.sanitize_notification(_mut(lambda b: b.update(groupKey="g" * 1024)))
    outcome1025 = ji.sanitize_notification(_mut(lambda b: b.update(groupKey="g" * 1025)))
    assert outcome1024.refusal is None
    assert outcome1025.source is None
    refusal = outcome1025.refusal
    assert refusal.code == "ingress_group_key_unsupported"
    assert refusal.source_group is None
    assert refusal.refused_group is not None
    assert refusal.alerts == 1


def test_x5_non_ascii_group_key_is_unsupported():
    outcome = ji.sanitize_notification(
        _mut(lambda b: b.update(groupKey='{}:{grafana_folder="Démo"}'))
    )
    assert outcome.refusal.code == "ingress_group_key_unsupported"


# === X6: duplicates =============================================================


def test_x6_duplicate_key_at_root():
    duplicated = wire(BASE_BODY)[:-1] + b',"groupKey":"x"}'
    outcome = ji.sanitize_notification(duplicated)
    assert outcome.refusal.code == "ingress_json_invalid"


def test_x6_duplicate_key_inside_an_alert():
    raw = wire(BASE_BODY)
    duplicated = raw.replace(
        b'"startsAt":"2026-09-17T21:56:20Z"',
        b'"startsAt":"2026-09-17T21:56:20Z","startsAt":"2026-09-17T21:56:21Z"',
        1,
    )
    assert duplicated != raw
    outcome = ji.sanitize_notification(duplicated)
    assert outcome.refusal.code == "ingress_json_invalid"


def test_x6_duplicate_key_inside_ignored_labels():
    raw = wire(BASE_BODY)
    duplicated = raw.replace(b'"cascade":"otel-demo"', b'"cascade":"otel-demo","cascade":"x"', 1)
    assert duplicated != raw
    outcome = ji.sanitize_notification(duplicated)
    assert outcome.refusal.code == "ingress_json_invalid"


def test_x6_duplicate_fingerprint_non_adjacent():
    body = copy.deepcopy(BASE_BODY)
    body["alerts"] = [A0, dict(A0, fingerprint="0" * 16), dict(A0, status="resolved")]
    outcome = ji.sanitize_notification(wire(body))
    assert outcome.source is None
    refusal = outcome.refusal
    assert refusal.code == "ingress_duplicate_fingerprint"
    assert refusal.alerts is None


# === X7: numbers ================================================================


@pytest.mark.parametrize("label,mutated", [
    ("NaN", wire(BASE_BODY).replace(b'"B":1}', b'"B":NaN}')),
    ("Infinity", wire(BASE_BODY).replace(b'"B":1}', b'"B":Infinity}')),
    ("-Infinity", wire(BASE_BODY).replace(b'"B":1}', b'"B":-Infinity}')),
    ("1e400", wire(BASE_BODY).replace(b'"B":1}', b'"B":1e400}')),
    ("2**53", wire(BASE_BODY).replace(b'"B":1}', b'"B":9007199254740992}')),
    ("33-char lexeme", wire(BASE_BODY).replace(b'"B":1}', b'"B":1.' + b"0" * 31 + b"}")),
])
def test_x7_non_finite_and_overflow_numbers_are_unsupported(label, mutated):
    outcome = ji.sanitize_notification(mutated)
    assert outcome.source is None, label
    assert outcome.refusal.code == "ingress_json_unsupported", label


@pytest.mark.parametrize("label,mutated", [
    ("2**53-1", wire(BASE_BODY).replace(b'"B":1}', b'"B":9007199254740991}')),
    ("1e-400", wire(BASE_BODY).replace(b'"B":1}', b'"B":1e-400}')),
])
def test_x7_boundary_numbers_are_admitted(label, mutated):
    assert ji.sanitize_notification(mutated).refusal is None, label


# === X8: nesting ================================================================


def _nested(bracket_count):
    return _mut(lambda body: body.update(x=json.loads("[" * bracket_count + "]" * bracket_count)))


def test_x8_depth_16_admitted_17_refused():
    outcome_ok = ji.sanitize_notification(_nested(15))
    outcome_bad = ji.sanitize_notification(_nested(16))
    assert outcome_ok.refusal is None
    assert outcome_bad.refusal.code == "ingress_json_invalid"


def test_x8_262144_bytes_of_open_brackets_is_refused(record_property):
    raw = b"[" * 262_144
    start = time.perf_counter()
    outcome = ji.sanitize_notification(raw)
    elapsed_ms = (time.perf_counter() - start) * 1000
    record_property("x8_open_brackets_ms", elapsed_ms)
    print(f"x8 262,144 open brackets: {elapsed_ms:.1f} ms")
    assert outcome.source is None
    assert outcome.refusal.code == "ingress_json_invalid"


# === X9: encoding and syntax ====================================================


@pytest.mark.parametrize("label,raw,expected_code", [
    ("empty body", b"", "ingress_json_invalid"),
    ("whitespace only", b"   ", "ingress_json_invalid"),
    ("BOM plus body", b"\xef\xbb\xbf" + wire(BASE_BODY), "ingress_json_invalid"),
    (
        "invalid utf-8 in message",
        wire(BASE_BODY).replace(b"**Firing**", b"**Fir\xffng**"),
        "ingress_json_invalid",
    ),
    ("trailing garbage", wire(BASE_BODY) + b"x", "ingress_json_invalid"),
    ("top-level array", b"[]", "ingress_shape"),
    ("top-level scalar", b"1", "ingress_shape"),
])
def test_x9_encoding_and_syntax(label, raw, expected_code):
    outcome = ji.sanitize_notification(raw)
    assert outcome.source is None, label
    assert outcome.refusal.code == expected_code, label


def test_x9_nul_escape_in_message_is_unsupported():
    outcome = ji.sanitize_notification(_mut(lambda body: body.update(message="a\u0000b")))
    assert outcome.source is None
    assert outcome.refusal.code == "ingress_json_unsupported"


def test_x9_lone_surrogate_escape_in_message_is_unsupported():
    # A lone surrogate has no UTF-8 encoding, so it must be injected as the
    # literal JSON escape sequence, not built through a Python str + wire().
    raw = (
        b'{"groupKey":"g","alerts":[{"fingerprint":"a","status":"firing"}],'
        b'"message":"\\ud800"}'
    )
    outcome = ji.sanitize_notification(raw)
    assert outcome.source is None
    assert outcome.refusal.code == "ingress_json_unsupported"


# === The two-phase check order (D11), reinforced from the black box ==========


def test_two_phase_400_before_422_across_members():
    raw_a = _mut(lambda b: b.update(alerts=[
        dict(A0, values={"Query 1": 1}), dict(A0, fingerprint="0" * 16, status="x"),
    ]))
    raw_b = _mut(lambda b: b.update(alerts=[
        dict(A0, fingerprint="0" * 16, status="x"), dict(A0, values={"Query 1": 1}),
    ]))
    assert ji.sanitize_notification(raw_a).refusal.code == "ingress_status"
    assert ji.sanitize_notification(raw_b).refusal.code == "ingress_status"

    raw_c = _mut(lambda b: (
        b.update(groupKey='{}:{grafana_folder="Démo"}'),
        b["alerts"][0].update(status="x"),
    ))
    assert ji.sanitize_notification(raw_c).refusal.code == "ingress_status"

    raw_d = _alert_mut(lambda a: a.update(values={"Query 1": 1, "b": "x"}))
    raw_e = _alert_mut(lambda a: a.update(values={"Query 1": 1, "A": "x"}))
    assert ji.sanitize_notification(raw_d).refusal.code == "ingress_values"
    assert ji.sanitize_notification(raw_e).refusal.code == "ingress_values"

    raw_f = _mut(lambda b: b.update(alerts=[
        dict(A0, fingerprint=f"{i:016x}", status="x" if i == 39 else "firing")
        for i in range(40)
    ]))
    assert ji.sanitize_notification(raw_f).refusal.code == "ingress_status"


# === Resolved-first summaries (D8) ============================================


def test_resolved_members_are_listed_first_in_refusal_summary():
    body = copy.deepcopy(BASE_BODY)
    body["alerts"] = [
        dict(A0, fingerprint=f"a{i:02d}", status="firing", values=None) for i in range(32)
    ] + [dict(A0, fingerprint="zz-resolved", status="resolved", values=None)]
    body["message"] = "m"

    outcome = ji.sanitize_notification(wire(body))
    refusal = outcome.refusal
    assert refusal.code == "ingress_too_many_alerts"
    assert refusal.alerts == 33
    assert refusal.resolved == 1
    assert refusal.members[0] == ("zz-resolved", "resolved")
    assert refusal.members_omitted == 1
    assert all(status == "firing" for _, status in refusal.members[1:])


# === refusal_to_json validation and forged summaries ==========================


def test_refusal_to_json_rejects_forged_refusals():
    raw, _ = grafana_group(CG1, 33, "firing", 2)
    base = ji.sanitize_notification(raw).refusal
    assert base is not None and base.code == "ingress_too_many_alerts"

    forgeries = {
        "unknown code": dataclasses.replace(base, code="nope"),
        "members_omitted wrong": dataclasses.replace(base, members_omitted=0),
        "duplicate fingerprint": dataclasses.replace(
            base, members=(base.members[0], base.members[0]) + base.members[2:],
        ),
        "both groups set": dataclasses.replace(base, refused_group="0" * 64),
        "bad body_digest": dataclasses.replace(base, body_digest="x" * 64),
        "resolved greater than alerts": dataclasses.replace(base, resolved=base.alerts + 1),
        "unsorted members": dataclasses.replace(base, members=tuple(reversed(base.members))),
    }
    for label, forged in forgeries.items():
        with pytest.raises(ji.IngressError) as info:
            ji.refusal_to_json(forged)
        assert info.value.args == ("ingress_argument",), label
        assert info.value.__cause__ is None, label
        assert info.value.__context__ is None, label


# === Custody: canaries (I10-style, reinforced from the black box) ============


def test_canary_custody_invalid_grammar_never_appears_valid_grammar_is_verbatim():
    canary_space = "CANARY 7f3a"     # invalid: contains a space
    canary_slash = "CANARY-7f3a/"    # invalid: contains a slash
    canary_valid = "CANARY-7f3a"     # valid under the fingerprint/refId grammar

    bodies = [
        _mut(lambda b: b.update(message=canary_valid, title=canary_valid)),
        _alert_mut(lambda a: (
            a["labels"].update(x=canary_valid), a["annotations"].update(y=canary_valid),
        )),
        _mut(lambda b: b.update(groupKey="é" + canary_valid)),
        _alert_mut(lambda a: a.update(startsAt=canary_valid)),
        _alert_mut(lambda a: a.update(fingerprint=canary_space)),
        _alert_mut(lambda a: a.update(fingerprint=canary_slash)),
        _alert_mut(lambda a: a.update(values={f"{canary_space} x": 1})),
        _alert_mut(lambda a: a.update(values={canary_slash: 1})),
        _alert_mut(lambda a: a.update(status=canary_valid)),
    ]
    for raw in bodies:
        outcome = ji.sanitize_notification(raw)
        text = repr(outcome)
        if outcome.refusal is not None:
            text += json.dumps(ji.refusal_to_json(outcome.refusal))
        assert "CANARY" not in text

    verbatim_raw = _alert_mut(
        lambda a: a.update(fingerprint=canary_valid, values={canary_valid: 1})
    )
    outcome = ji.sanitize_notification(verbatim_raw)
    assert outcome.refusal is None
    assert outcome.source.alerts[0].fingerprint == canary_valid
    assert outcome.source.alerts[0].values == ((canary_valid, "1"),)


# === X10: totality fuzz (seed-fixed) ===========================================


def test_x10_totality_fuzz_seeded():
    rnd = random.Random(20260923)
    seeds = [wire(envelope["body"]) for _, _, envelope in list(capture_rows())[:5]]
    outcomes = 0
    for _ in range(2000):
        raw = bytearray(rnd.choice(seeds))
        op = rnd.randrange(4)
        if op == 0:
            raw[rnd.randrange(len(raw))] = rnd.randrange(256)
        elif op == 1:
            raw = raw[: rnd.randrange(len(raw))]
        elif op == 2:
            pos = rnd.randrange(len(raw))
            raw[pos:pos] = bytes(rnd.randrange(256) for _ in range(rnd.randrange(1, 8)))
        else:
            pos = rnd.randrange(len(raw))
            del raw[pos: pos + rnd.randrange(1, 16)]
        outcome = ji.sanitize_notification(bytes(raw))
        outcomes += 1
        assert (outcome.source is None) != (outcome.refusal is None)
        if outcome.source is not None:
            assert js.validate_source(outcome.source) == outcome.source
        else:
            assert ji.refusal_to_json(outcome.refusal)

    for _ in range(200):
        raw = bytes(rnd.randrange(256) for _ in range(rnd.randrange(0, 300)))
        outcome = ji.sanitize_notification(raw)
        outcomes += 1
        assert (outcome.source is None) != (outcome.refusal is None)
        if outcome.source is not None:
            assert js.validate_source(outcome.source) == outcome.source
        else:
            assert ji.refusal_to_json(outcome.refusal)

    assert outcomes == 2200


# === X11: work at the bound (printed, never asserted) ==========================


def test_x11_work_at_the_bound(record_property):
    shapes = {
        "small objects": b"[" + b",".join([b"{}"] * 87_000) + b"]",
        "many keys": b"{" + b",".join(b'"k%06d":0' % i for i in range(23_000)) + b"}",
        "escapes": b'{"m":"' + b"\\u0041" * 43_000 + b'"}',
        "numbers": b"[" + b",".join([b"1.5"] * 65_000) + b"]",
        "big message": _mut(lambda body: body.update(message="m" * 250_000)),
    }
    for label, raw in shapes.items():
        raw = raw[:262_144]
        start = time.perf_counter()
        outcome = ji.sanitize_notification(raw)
        elapsed_ms = (time.perf_counter() - start) * 1000
        record_property(f"x11_{label.replace(' ', '_')}_ms", elapsed_ms)
        code = outcome.refusal.code if outcome.refusal else "admitted"
        print(f"x11 {label}: {len(raw)} B, {elapsed_ms:.1f} ms -> {code}")
        assert (outcome.source is None) != (outcome.refusal is None)


# === X12: resends and members ===================================================


def test_x12_refused_group_stable_across_resends():
    non_ascii_group = '{}:{grafana_folder="Démo"}'
    body1 = copy.deepcopy(CG2["body"])
    body1["groupKey"] = non_ascii_group
    body1["message"] = "resend 1"
    body2 = copy.deepcopy(CG2["body"])
    body2["groupKey"] = non_ascii_group
    body2["message"] = "resend 2"
    body2["alerts"] = body2["alerts"][:2]

    refusal1 = ji.sanitize_notification(wire(body1)).refusal
    refusal2 = ji.sanitize_notification(wire(body2)).refusal
    assert refusal1.code == refusal2.code == "ingress_group_key_unsupported"
    assert refusal1.refused_group == refusal2.refused_group
    assert refusal1.body_digest != refusal2.body_digest
    expected = hashlib.sha256(
        ji.REFUSED_GROUP_TAG.encode("ascii") + b"\x00" + non_ascii_group.encode("utf-8")
    ).hexdigest()
    assert refusal1.refused_group == expected


def _phase2_refusal_cases():
    grafana_raw, _ = grafana_group(CG2, 33, "resolved", 2)
    return [
        ("grafana_group 33 resolved", grafana_raw),
        ("29 clones record too large", _minimal_members(29, values=A0["values"])),
        ("33 value-free too many alerts", _minimal_members(33)),
        (
            "65 values too many values",
            _alert_mut(lambda a: a.update(values={f"r{i:02d}": i for i in range(65)})),
        ),
        ("groupKey 1025 unsupported", _mut(lambda b: b.update(groupKey="g" * 1025))),
        ("refId unsupported", _alert_mut(lambda a: a.update(values={"Query 1": 1}))),
    ]


PHASE2_CASES = _phase2_refusal_cases()


@pytest.mark.parametrize("label,raw", PHASE2_CASES, ids=[c[0] for c in PHASE2_CASES])
def test_x12_phase_2_refusals_name_members_consistently(label, raw):
    outcome = ji.sanitize_notification(raw)
    assert outcome.source is None, label
    refusal = outcome.refusal
    assert refusal.code in ji.MEMBER_CODES, label

    body = json.loads(raw)
    assert refusal.alerts == len(body["alerts"]), label

    keys = [(status != "resolved", fingerprint) for fingerprint, status in refusal.members]
    assert keys == sorted(keys), label
    assert len(refusal.members) == min(refusal.alerts, 32), label
    assert refusal.members_omitted == refusal.alerts - len(refusal.members), label

    encoded = ji.refusal_to_json(refusal)
    assert encoded["code"] == refusal.code
