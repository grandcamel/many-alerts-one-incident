"""Known-answer and closed-vocabulary tests for ``journal_source`` (unit 15,
module 1 split; ticket 37 cases A6-A10, the source parts of A11, and A12 for
this module).

Golden values are recomputed independently here with ``hashlib.sha256`` and
plain dict/list encodings, per the implementation plan, rather than trusted
from the module under test. Captured alert data comes from the committed
ticket-14 extracts cited by ticket-31 (``sc31``); nothing here posts HTTP,
spawns a process, or touches SQLite.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import pathlib

import pytest

from grafana_jsm_sandbox import journal_source as js
from grafana_jsm_sandbox.forwarder_json import (
    JSONDecimal,
    canonical_json,
    parse_json,
    tagged_digest,
)

REPOSITORY = pathlib.Path(__file__).resolve().parent.parent
CAPTURE_DIR = (
    REPOSITORY / ".scratch" / "many-alerts-one-incident" / "reviews" / "ticket-14" / "jira"
)
PAYMENT_JSONL = CAPTURE_DIR / "notifications-paymentUnreachable.jsonl"
EMAIL_JSONL = CAPTURE_DIR / "notifications-emailMemoryLeak.jsonl"


# === Shared helpers ==========================================================


def expect_source(code, fn, *args, **kwargs):
    with pytest.raises(js.SourceError) as info:
        fn(*args, **kwargs)
    error = info.value
    assert error.code == code
    assert error.args == (code,)
    assert error.__cause__ is None
    assert error.__context__ is None
    return error


def sample_source() -> js.SourceRecord:
    group_key = '{}:{alertname="Service error rate is elevated", grafana_folder="demo"}'
    alert = js.SourceAlert(
        fingerprint="5e8d72dc87b1ff35", status="firing",
        values=(("A", "1"), ("B", "1")), starts_at=None,
    )
    return js.SourceRecord(
        source_group=js.source_group_digest(group_key), alerts=(alert,),
        truncated_alerts=0, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )


# === A6/A7: canonical numbers =================================================


CANONICAL_NUMBER_CASES = [
    (100, "100"),
    (JSONDecimal("100.0"), "100"),
    (JSONDecimal("1e2"), "100"),
    (JSONDecimal("10.0"), "10"),
    (JSONDecimal("0.1"), "0.1"),
    (JSONDecimal("0.10000000000000001"), "0.1"),
    (JSONDecimal("-0.0"), "0"),
    (-0, "0"),
    (JSONDecimal("1e16"), "1e+16"),
    (JSONDecimal("1e-7"), "1e-07"),
    (JSONDecimal("9007199254740992.0"), "9007199254740992.0"),
    (JSONDecimal("5e-324"), "5e-324"),
]


@pytest.mark.parametrize("value,expected", CANONICAL_NUMBER_CASES)
def test_a6_canonical_number_known_answers(value, expected):
    assert js.canonical_number(value) == expected


@pytest.mark.parametrize("bad", [True, False, "100", 1.5])
def test_a6_canonical_number_rejects_bool_str_float(bad):
    expect_source("source_number", js.canonical_number, bad)


ACCEPTED_CANONICAL_STRINGS = [expected for _, expected in CANONICAL_NUMBER_CASES]
REJECTED_CANONICAL_STRINGS = [
    "1.0", "-0", "1e16", "1E+16", "+1", "01", "9007199254740992", "nan", "inf", "x" * 33,
]


@pytest.mark.parametrize("text", ACCEPTED_CANONICAL_STRINGS)
def test_a7_is_canonical_number_accepts_known_outputs(text):
    assert js.is_canonical_number(text) is True


@pytest.mark.parametrize("text", REJECTED_CANONICAL_STRINGS)
def test_a7_is_canonical_number_rejects(text):
    assert js.is_canonical_number(text) is False


# === A8: SourceRecord validation =============================================


def _capture_body(path: pathlib.Path, line_no: int) -> dict:
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if index == line_no:
                envelope = json.loads(line)
                raw = json.dumps(envelope["body"]).encode("utf-8")
                return parse_json(raw, max_bytes=1_048_576, numbers="finite")
    raise AssertionError(f"line {line_no} not found in {path}")


def _source_from_capture(path: pathlib.Path, line_no: int, *, body_seed: str) -> js.SourceRecord:
    body = _capture_body(path, line_no)
    alerts = []
    for raw_alert in body["alerts"]:
        values = tuple(
            (ref_id, js.canonical_number(value)) for ref_id, value in raw_alert["values"].items()
        )
        alerts.append(js.SourceAlert(
            fingerprint=raw_alert["fingerprint"], status=raw_alert["status"],
            values=values, starts_at=raw_alert.get("startsAt"),
        ))
    alerts.sort(key=lambda a: a.fingerprint)
    return js.SourceRecord(
        source_group=js.source_group_digest(body["groupKey"]),
        alerts=tuple(alerts),
        truncated_alerts=body["truncatedAlerts"],
        body_digest=hashlib.sha256(f"rj.body.v1\x00{body_seed}".encode()).hexdigest(),
        provenance=js.HTTP_PROVENANCE,
    )


CAPTURED_LINES = [
    (PAYMENT_JSONL, 1), (PAYMENT_JSONL, 2), (PAYMENT_JSONL, 16), (PAYMENT_JSONL, 18),
    (PAYMENT_JSONL, 20), (PAYMENT_JSONL, 21), (PAYMENT_JSONL, 23), (PAYMENT_JSONL, 24),
    (PAYMENT_JSONL, 26), (EMAIL_JSONL, 57), (EMAIL_JSONL, 62), (EMAIL_JSONL, 63),
]


@pytest.mark.parametrize("path,line_no", CAPTURED_LINES)
def test_a8_captured_projections_validate(path, line_no):
    record = _source_from_capture(path, line_no, body_seed=f"{path.name}:{line_no}")
    validated = js.validate_source(record)
    assert validated == record


def test_a8_unsorted_alerts_give_source_order():
    source = sample_source()
    b_alert = dataclasses.replace(source.alerts[0], fingerprint="zzzzzzzzzzzzzzzz")
    unsorted = dataclasses.replace(source, alerts=(b_alert, source.alerts[0]))
    expect_source("source_order", js.validate_source, unsorted)


def test_a8_duplicate_fingerprint():
    alert = sample_source().alerts[0]
    duplicate = dataclasses.replace(sample_source(), alerts=(alert, alert))
    expect_source("source_duplicate_fingerprint", js.validate_source, duplicate)


def test_a8_wrong_case_status():
    source = sample_source()
    bad = dataclasses.replace(source, alerts=(
        dataclasses.replace(source.alerts[0], status="Firing"),
    ))
    expect_source("source_status", js.validate_source, bad)


def test_a8_too_many_alerts():
    source = sample_source()
    alerts = tuple(
        dataclasses.replace(source.alerts[0], fingerprint=f"{i:04d}" + "a" * 12, values=None)
        for i in range(33)
    )
    bad = dataclasses.replace(source, alerts=tuple(sorted(alerts, key=lambda a: a.fingerprint)))
    expect_source("source_too_many_alerts", js.validate_source, bad)
    ok = dataclasses.replace(source, alerts=tuple(sorted(alerts, key=lambda a: a.fingerprint)[:32]))
    js.validate_source(ok)


def test_a8_too_many_values_total():
    source = sample_source()

    def alert(fp, n):
        return js.SourceAlert(
            fingerprint=fp, status="firing",
            values=tuple((f"v{i:02d}", "1") for i in range(n)), starts_at=None,
        )

    ok = dataclasses.replace(source, alerts=(alert("aaaa", 32), alert("bbbb", 32)))
    js.validate_source(ok)
    bad = dataclasses.replace(source, alerts=(alert("aaaa", 32), alert("bbbb", 33)))
    expect_source("source_too_many_values", js.validate_source, bad)


def test_a8_too_large_canonical_bytes():
    source = sample_source()

    def filler(i, length):
        prefix = f"a{i:03d}"
        return prefix + "f" * (length - len(prefix))

    def build(n_filler, filler_len, last_len):
        alerts = [
            js.SourceAlert(
                fingerprint=filler(i, filler_len), status="firing", values=None, starts_at=None,
            )
            for i in range(n_filler)
        ]
        last_fp = "z" + "9" * (last_len - 1)
        alerts.append(
            js.SourceAlert(fingerprint=last_fp, status="firing", values=None, starts_at=None)
        )
        alerts.sort(key=lambda a: a.fingerprint)
        return dataclasses.replace(source, alerts=tuple(alerts))

    # Empirically located boundary (29 x 61-char fillers + one tunable
    # fingerprint): exactly MAX_SOURCE_RECORD_BYTES accepted, +1 rejected.
    at_bound = build(29, 61, 27)
    at_bound_size = len(canonical_json(js.source_to_json(at_bound), ascii_only=True))
    assert at_bound_size == js.MAX_SOURCE_RECORD_BYTES
    js.validate_source(at_bound)
    over_bound = build(29, 61, 28)
    assert (
        len(canonical_json(js.source_to_json(over_bound), ascii_only=True))
        == js.MAX_SOURCE_RECORD_BYTES + 1
    )
    expect_source("source_too_large", js.validate_source, over_bound)


def test_a8_fingerprint_length_and_charset():
    source = sample_source()
    bad_length = dataclasses.replace(source, alerts=(
        dataclasses.replace(source.alerts[0], fingerprint="a" * 65),
    ))
    expect_source("source_fingerprint", js.validate_source, bad_length)
    ok_length = dataclasses.replace(source, alerts=(
        dataclasses.replace(source.alerts[0], fingerprint="a" * 64, values=None),
    ))
    js.validate_source(ok_length)
    bad_charset = dataclasses.replace(source, alerts=(
        dataclasses.replace(source.alerts[0], fingerprint="bad fingerprint!"),
    ))
    expect_source("source_fingerprint", js.validate_source, bad_charset)


def test_a8_ref_id_length():
    source = sample_source()
    bad = dataclasses.replace(source, alerts=(
        dataclasses.replace(source.alerts[0], values=(("r" * 33, "1"),)),
    ))
    expect_source("source_values", js.validate_source, bad)
    ok = dataclasses.replace(source, alerts=(
        dataclasses.replace(source.alerts[0], values=(("r" * 32, "1"),)),
    ))
    js.validate_source(ok)


def test_a8_starts_at_valid_and_invalid():
    source = sample_source()
    valid = dataclasses.replace(source, alerts=(
        dataclasses.replace(source.alerts[0], starts_at="2026-09-17T21:56:20.123456789Z"),
    ))
    js.validate_source(valid)
    invalid = dataclasses.replace(source, alerts=(
        dataclasses.replace(source.alerts[0], starts_at="2026-09-17 21:56:20Z"),
    ))
    expect_source("source_starts_at", js.validate_source, invalid)


@pytest.mark.parametrize("value,accepted", [
    (None, True), (0, True), (2**31 - 1, True), (-1, False), (2**31, False), (True, False),
])
def test_a8_truncated_alerts_bounds(value, accepted):
    source = sample_source()
    candidate = dataclasses.replace(source, truncated_alerts=value)
    if accepted:
        js.validate_source(candidate)
    else:
        expect_source("source_truncated", js.validate_source, candidate)


def test_a8_non_hex_body_digest():
    source = sample_source()
    bad = dataclasses.replace(source, body_digest="z" * 64)
    expect_source("source_body_digest", js.validate_source, bad)


def test_a8_non_http_provenance():
    source = sample_source()
    bad = dataclasses.replace(source, provenance=js.Provenance("capture", "/x", 1))
    expect_source("source_provenance", js.validate_source, bad)


def test_a8_values_none_versus_empty_dict_are_distinct():
    source = sample_source()
    none_values = dataclasses.replace(source, alerts=(
        dataclasses.replace(source.alerts[0], values=None),
    ))
    empty_values = dataclasses.replace(source, alerts=(
        dataclasses.replace(source.alerts[0], values=()),
    ))
    v_none = js.validate_source(none_values)
    v_empty = js.validate_source(empty_values)
    assert js.source_to_json(v_none) != js.source_to_json(v_empty)
    assert js.source_to_json(v_none)["alerts"][0]["values"] is None
    assert js.source_to_json(v_empty)["alerts"][0]["values"] == {}
    assert js.dedupe_key(v_none) != js.dedupe_key(v_empty)


def test_a8_values_not_sorted_by_ref_id_give_source_order():
    source = sample_source()
    unsorted = dataclasses.replace(source, alerts=(
        dataclasses.replace(source.alerts[0], values=(("B", "1"), ("A", "1"))),
    ))
    expect_source("source_order", js.validate_source, unsorted)
    source_json = js.source_to_json(source)
    alert = dict(source_json["alerts"][0], values={"B": "1", "A": "1"})
    expect_source("source_order", js.source_from_json, dict(source_json, alerts=(alert,)))


def test_a8_sorted_values_replay_to_the_same_record():
    source = js.validate_source(sample_source())
    stored = parse_json(
        canonical_json(js.source_to_json(source), ascii_only=True),
        max_bytes=js.MAX_SOURCE_RECORD_BYTES, ascii_only=True,
    )
    assert js.source_from_json(stored) == source


def test_a8_starts_at_with_non_ascii_digits_is_a_source_error():
    source = sample_source()
    starts_at = "٢٠٢٦-09-17T21:56:20Z"  # ARABIC-INDIC digits
    bad = dataclasses.replace(source, alerts=(
        dataclasses.replace(source.alerts[0], starts_at=starts_at),
    ))
    expect_source("source_starts_at", js.validate_source, bad)
    source_json = js.source_to_json(source)
    alert = dict(source_json["alerts"][0], starts_at=starts_at)
    expect_source("source_starts_at", js.source_from_json, dict(source_json, alerts=(alert,)))


def test_a8_mutated_frozen_instance_fails_validate_source():
    source = js.validate_source(sample_source())
    mutated = dataclasses.replace(
        source, alerts=(dataclasses.replace(source.alerts[0], fingerprint=123),),
    )
    expect_source("source_fingerprint", js.validate_source, mutated)


# === A9: full-length goldens ==================================================


CG1_GROUP_KEY = '{}:{alertname="Service error rate is elevated", grafana_folder="demo"}'
CG2_GROUP_KEY = '{}:{alertname="Service request rate has dropped to zero", grafana_folder="demo"}'
LEGACY_GROUP_KEY = '{}:{alertname="rolldice request rate is zero", grafana_folder="demo"}'
PF_FINGERPRINT = "5e8d72dc87b1ff35"
LEGACY_FINGERPRINT = "87e2f184874a3b71"

GOLDENS = {
    "cg1_source_group": "5deaf914a2a751fefe64e9b9077fdadad2f5fe11c224ba5451d6d66bb6c7876e",
    "cg2_source_group": "9d37267f6830d441f2c6ce82698704b397a29c16eb135973907fa2fa38045ce4",
    "legacy_source_group": "aa57d128272b37ba89511a41b61e587aa198e2676d80f71925332c0d582bb7f8",
    "key_a": "8fd41b0b50e9410d251c4802436605e54f65a8bbb6989f0fe170cbdc078d874a",
    "key_b": "032a43329187bc6b93f1434f0b0b0d4ee53b5c32fe93b3cb10c6182bc3da4dd9",
    "legacy_firing": "a99b74e0622bbf52ab6f66f38af0034e030e8b301bd0a399b97e7931f81f262d",
    "legacy_resolved": "107b7990e93f96f157da3e1ca394fd0697020a1d94647a7cf30d91b5fe8963f6",
    "values_null": "db1901d7290e2697801453a6f829fb717479abfe954ad061e16400f0c731e810",
    "values_empty": "6a3c39155abbaf9364c9f427f84ebeea57bebbb2aab2c615d78a6ee16551ecd3",
}


def test_a9_source_group_goldens():
    assert js.source_group_digest(CG1_GROUP_KEY) == GOLDENS["cg1_source_group"]
    assert js.source_group_digest(CG2_GROUP_KEY) == GOLDENS["cg2_source_group"]
    assert js.source_group_digest(LEGACY_GROUP_KEY) == GOLDENS["legacy_source_group"]


def _pf_alert(values) -> js.SourceAlert:
    return js.SourceAlert(
        fingerprint=PF_FINGERPRINT, status="firing", values=values, starts_at=None,
    )


def test_a9_key_a_and_key_b_goldens():
    source_a = js.SourceRecord(
        source_group=GOLDENS["cg1_source_group"], alerts=(_pf_alert((("A", "1"), ("B", "1"))),),
        truncated_alerts=0, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )
    source_b = js.SourceRecord(
        source_group=GOLDENS["cg1_source_group"], alerts=(_pf_alert((("A", "2"), ("B", "1"))),),
        truncated_alerts=0, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )
    assert js.dedupe_key(source_a) == GOLDENS["key_a"]
    assert js.dedupe_key(source_b) == GOLDENS["key_b"]
    # The tuple-of-pairs encoding of the SAME data must NOT be what dedupe_key
    # produces (critic 13 ii): it is a different, wrong digest.
    wrong = tagged_digest(
        "rj.dedupe-key.v1", [[PF_FINGERPRINT, "firing", [["A", "1"], ["B", "1"]]]],
    )
    assert wrong == "06b0db0fed2fdd08ae4f0f17bcb683005243abea681aa3a8728fbab4b3d9bcba"
    assert js.dedupe_key(source_a) != wrong


def test_a9_legacy_pair_goldens():
    firing = js.SourceRecord(
        source_group=GOLDENS["legacy_source_group"],
        alerts=(js.SourceAlert(
            fingerprint=LEGACY_FINGERPRINT, status="firing", values=(("A", "0"), ("B", "1")),
            starts_at=None,
        ),),
        truncated_alerts=0, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )
    resolved = js.SourceRecord(
        source_group=GOLDENS["legacy_source_group"],
        alerts=(js.SourceAlert(
            fingerprint=LEGACY_FINGERPRINT, status="resolved",
            values=(("A", "0.11962199449738824"), ("B", "0")), starts_at=None,
        ),),
        truncated_alerts=0, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )
    assert js.dedupe_key(firing) == GOLDENS["legacy_firing"]
    assert js.dedupe_key(resolved) == GOLDENS["legacy_resolved"]


def test_a9_values_null_versus_empty_goldens():
    null_source = js.SourceRecord(
        source_group=GOLDENS["cg1_source_group"], alerts=(_pf_alert(None),),
        truncated_alerts=0, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )
    empty_source = js.SourceRecord(
        source_group=GOLDENS["cg1_source_group"], alerts=(_pf_alert(()),),
        truncated_alerts=0, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )
    assert js.dedupe_key(null_source) == GOLDENS["values_null"]
    assert js.dedupe_key(empty_source) == GOLDENS["values_empty"]


def test_a9_key_excludes_starts_at_truncated_alerts_body_digest_and_provenance():
    base = js.SourceRecord(
        source_group=GOLDENS["cg1_source_group"], alerts=(_pf_alert((("A", "1"), ("B", "1"))),),
        truncated_alerts=0, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )
    varied = dataclasses.replace(
        base,
        alerts=(dataclasses.replace(base.alerts[0], starts_at="2026-09-17T21:56:20Z"),),
        body_digest="f" * 64,
    )
    assert js.dedupe_key(base) == js.dedupe_key(varied) == GOLDENS["key_a"]


# === A10: source_group_digest bounds =========================================


def test_a10_source_group_digest_rejects_empty_too_long_and_non_printable():
    expect_source("source_group", js.source_group_digest, "")
    expect_source("source_group", js.source_group_digest, "x" * 1_025)
    ok = js.source_group_digest("x" * 1_024)
    assert len(ok) == 64
    expect_source("source_group", js.source_group_digest, "bad\x01char")
    expect_source("source_group", js.source_group_digest, 12345)


# === A11 (source part): closed error custody =================================


def test_a11_source_error_codes_are_closed_and_custody_clean():
    for code in js.SOURCE_ERROR_CODES:
        error = js.SourceError(code)
        assert error.args == (code,)
        assert error.code == code
        assert error.__cause__ is None
        assert error.__context__ is None


def test_a11_every_raised_error_code_is_in_the_closed_set():
    # A sweep of realistic failures across this module's public entry points.
    expect_source("source_number", js.canonical_number, "not a number")
    assert "source_number" in js.SOURCE_ERROR_CODES
    expect_source("source_argument", js.validate_source, "not a source record")
    assert "source_argument" in js.SOURCE_ERROR_CODES
    expect_source("source_group", js.source_group_digest, "")
    assert "source_group" in js.SOURCE_ERROR_CODES


# === A12: AST checks (imports, except bodies) ================================

MODULE_PATH = REPOSITORY / "grafana_jsm_sandbox" / "journal_source.py"
ALLOWED_TOP_LEVEL_IMPORTS = frozenset({"__future__", "dataclasses", "math", "re"})


def _module_ast() -> ast.Module:
    source = MODULE_PATH.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(MODULE_PATH))


def test_a12_imports_match_the_exact_allowlist():
    tree = _module_ast()
    top_level_names: set[str] = set()
    from_imports: set[tuple[int, str, tuple[str, ...]]] = set()
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
    assert (1, "forwarder_json", (
        "JSONDecimal", "MAX_JSON_NUMBER_CHARS", "MAX_SAFE_INTEGER",
        "canonical_json", "tagged_digest",
    )) in from_imports
    # Exactly these two `from` imports -- no extra relative or absolute one,
    # and in particular no import of `.journal_records` (no cycle).
    assert len(from_imports) == 2


def test_a12_except_bodies_are_only_assign_annassign_or_pass():
    tree = _module_ast()
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    assert len(handlers) >= 2  # sanity: the module really does have handlers to check
    for handler in handlers:
        for statement in handler.body:
            assert isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Pass)), (
                f"except body has a {type(statement).__name__} at line {statement.lineno}"
            )
        for inner in ast.walk(handler):
            if isinstance(inner, ast.Raise):
                pytest.fail(f"raise inside except handler at line {inner.lineno}")


# === Unit 15a review gaps: checks left unasserted ===========================


def test_a8_http_provenance_with_wrong_path_is_rejected():
    # `kind="http"` (the only accepted kind) and `line=None` are both valid on
    # their own, so only the final `provenance != HTTP_PROVENANCE` equality
    # check can catch the wrong `path`. `test_a8_non_http_provenance` uses a
    # `kind` that is already rejected earlier and never reaches this
    # comparison, so it does not isolate it the way this test does.
    source = sample_source()
    bad = dataclasses.replace(source, provenance=js.Provenance("http", "/other", None))
    expect_source("source_provenance", js.validate_source, bad)


def test_canonical_number_rejects_a_non_str_jsondecimal_text():
    # `JSONDecimal` is a plain dataclass, so nothing stops a caller building
    # one with a non-`str` `.text`. `canonical_number` must reject it with the
    # fixed `source_number` code rather than let a later `len()`/regex call on
    # a non-string raise an uncaught `TypeError`.
    expect_source("source_number", js.canonical_number, JSONDecimal(123))
