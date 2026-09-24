"""Tests for the additive ``max_string_bytes`` keyword on ``parse_json``
(ticket 37, unit 16, cases S1-S6). This keyword lets the raw-ingress
sanitizer raise the per-string cap to the body bound; every existing call
site keeps the 16 KiB default untouched.
"""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

from grafana_jsm_sandbox.forwarder_json import (
    MAX_JSON_DOCUMENT_BYTES,
    MAX_JSON_STRING_BYTES,
    JSONPolicyError,
    canonical_json,
    parse_json,
    tagged_digest,
)

REPOSITORY = pathlib.Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPOSITORY / "grafana_jsm_sandbox"


def parse(data: bytes, *, max_bytes: int = MAX_JSON_DOCUMENT_BYTES, **kwargs) -> object:
    return parse_json(data, max_bytes=max_bytes, **kwargs)


def expect_code(call, code: str) -> JSONPolicyError:
    with pytest.raises(JSONPolicyError) as caught:
        call()
    assert caught.value.code == code
    return caught.value


def _string_of(byte_length: int) -> str:
    """A string whose UTF-8 encoding is exactly ``byte_length`` bytes."""
    return "a" * byte_length


# === S1: the default is unchanged ==============================================


def test_s1_default_boundary_value_and_key():
    ok = _string_of(MAX_JSON_STRING_BYTES)
    document = json.dumps({"k": ok}).encode("utf-8")
    assert parse(document) == {"k": ok}
    bad = _string_of(MAX_JSON_STRING_BYTES + 1)
    bad_value = json.dumps({"k": bad}).encode("utf-8")
    expect_code(lambda: parse(bad_value), "json_string_too_long")
    bad_key = json.dumps({bad: 1}).encode("utf-8")
    expect_code(lambda: parse(bad_key), "json_string_too_long")


def test_s1_explicit_default_keyword_matches_implicit_default():
    ok = _string_of(MAX_JSON_STRING_BYTES)
    document = json.dumps({"k": ok}).encode("utf-8")
    assert parse(document) == parse(document, max_string_bytes=MAX_JSON_STRING_BYTES)
    bad = _string_of(MAX_JSON_STRING_BYTES + 1)
    bad_document = json.dumps({"k": bad}).encode("utf-8")
    implicit = expect_code(lambda: parse(bad_document), "json_string_too_long")
    explicit = expect_code(
        lambda: parse(bad_document, max_string_bytes=MAX_JSON_STRING_BYTES),
        "json_string_too_long",
    )
    assert implicit.code == explicit.code


# === S2: a raised cap ===========================================================


def test_s2_raised_cap_accepts_strings_the_default_would_refuse():
    for size in (MAX_JSON_STRING_BYTES + 1, 200_000):
        value = _string_of(size)
        document = json.dumps({"k": value}).encode("utf-8")
        result = parse(document, max_string_bytes=262_144)
        assert result == {"k": value}
        key_document = json.dumps({value: 1}).encode("utf-8")
        assert parse(key_document, max_string_bytes=262_144) == {value: 1}


def test_s2_raised_cap_still_refuses_above_itself():
    value = _string_of(20_001)
    document = json.dumps({"k": value}).encode("utf-8")
    expect_code(
        lambda: parse(document, max_bytes=MAX_JSON_DOCUMENT_BYTES, max_string_bytes=20_000),
        "json_string_too_long",
    )


# === S3: argument validation =====================================================


@pytest.mark.parametrize("bad", [0, -1, MAX_JSON_DOCUMENT_BYTES + 1, True, 1.0, "16384", None])
def test_s3_argument_rejections(bad):
    expect_code(lambda: parse(b"1", max_string_bytes=bad), "json_argument")


def test_s3_argument_check_runs_before_decoding():
    # Undecodable bytes would otherwise fail with json_encoding; the
    # max_string_bytes argument check must win regardless.
    undecodable = b"\xff\xfe"
    expect_code(lambda: parse(undecodable, max_string_bytes="bogus"), "json_argument")


# === S4: a raised cap changes nothing else ======================================


def test_s4_nul_and_lone_surrogate_still_refuse():
    expect_code(lambda: parse(b'"a\\u0000b"', max_string_bytes=262_144), "json_unicode")
    expect_code(lambda: parse(b'"\\ud800"', max_string_bytes=262_144), "json_unicode")


def test_s4_ascii_only_still_refuses():
    expect_code(
        lambda: parse('"é"'.encode(), ascii_only=True, max_string_bytes=262_144), "json_unicode",
    )


def test_s4_depth_still_refuses():
    ok = ("[" * 16 + "1" + "]" * 16).encode("ascii")
    parse(ok, max_string_bytes=262_144)
    bad = ("[" * 17 + "1" + "]" * 17).encode("ascii")
    expect_code(lambda: parse(bad, max_string_bytes=262_144), "json_depth")


def test_s4_array_cap_still_refuses():
    ok = ("[" + ",".join(["1"] * 256) + "]").encode("ascii")
    parse(ok, max_string_bytes=262_144)
    bad = ("[" + ",".join(["1"] * 257) + "]").encode("ascii")
    expect_code(lambda: parse(bad, max_string_bytes=262_144), "json_array_too_long")


def test_s4_duplicate_keys_still_refuse():
    expect_code(lambda: parse(b'{"a":1,"a":2}', max_string_bytes=262_144), "json_duplicate_key")


def test_s4_numbers_still_refuse():
    expect_code(lambda: parse(b"1" * 33, max_string_bytes=262_144), "json_number")
    expect_code(lambda: parse(b"NaN", max_string_bytes=262_144), "json_number")


# === S5: canonical_json and tagged_digest are unaffected =========================


def test_s5_canonical_json_still_refuses_16385_bytes():
    value = _string_of(MAX_JSON_STRING_BYTES)
    canonical_json(value)  # accepted
    over = _string_of(MAX_JSON_STRING_BYTES + 1)
    with pytest.raises(JSONPolicyError) as caught:
        canonical_json(over)
    assert caught.value.code == "json_string_too_long"


def test_s5_tagged_digest_still_refuses_16385_bytes():
    over = _string_of(MAX_JSON_STRING_BYTES + 1)
    with pytest.raises(JSONPolicyError) as caught:
        tagged_digest("maoi.test.v1", over)
    assert caught.value.code == "json_string_too_long"


# === S6: AST checks over the whole package =======================================


def _source_files() -> list[pathlib.Path]:
    return sorted(PACKAGE_DIR.glob("*.py"))


def _parse(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_s6_max_string_bytes_is_passed_only_from_journal_ingress_exactly_once():
    call_sites: list[tuple[pathlib.Path, int]] = []
    for path in _source_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                target = node.func
                is_parse_json_name = isinstance(target, ast.Name) and target.id == "parse_json"
                is_parse_json_attr = (
                    isinstance(target, ast.Attribute) and target.attr == "parse_json"
                )
                if not (is_parse_json_name or is_parse_json_attr):
                    continue
                for keyword in node.keywords:
                    if keyword.arg == "max_string_bytes":
                        call_sites.append((path, node.lineno))
    assert len(call_sites) == 1
    assert call_sites[0][0].name == "journal_ingress.py"


def test_s6_no_parse_json_call_uses_a_double_star_splat():
    for path in _source_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                target = node.func
                is_parse_json = (
                    (isinstance(target, ast.Name) and target.id == "parse_json")
                    or (isinstance(target, ast.Attribute) and target.attr == "parse_json")
                )
                if not is_parse_json:
                    continue
                for keyword in node.keywords:
                    assert keyword.arg is not None, (
                        f"parse_json called with ** in {path.name}:{node.lineno}"
                    )


def test_s6_every_reference_to_parse_json_outside_its_definition_is_a_callee():
    for path in _source_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "parse_json":
                continue  # the definition itself
            if isinstance(node, ast.Name) and node.id == "parse_json":
                parent_is_call_func = False
                for candidate in ast.walk(tree):
                    if (
                        isinstance(candidate, ast.Call)
                        and getattr(candidate.func, "id", None) == "parse_json"
                        and candidate.func is node
                    ):
                        parent_is_call_func = True
                        break
                assert parent_is_call_func, (
                    f"non-callee reference to parse_json in {path.name}:{node.lineno}"
                )
            if isinstance(node, ast.Attribute) and node.attr == "parse_json":
                # e.g. forwarder_json.parse_json(...): must be a call target too.
                for candidate in ast.walk(tree):
                    if (
                        isinstance(candidate, ast.Call) and candidate.func is node
                    ):
                        break
                else:
                    pytest.fail(f"non-callee attribute reference in {path.name}:{node.lineno}")


def test_s6_no_import_aliases_parse_json():
    for path in _source_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "parse_json":
                        assert alias.asname is None, f"aliased import in {path.name}"


def test_s6_max_string_bytes_reaches_only_postwalk_inside_forwarder_json():
    path = PACKAGE_DIR / "forwarder_json.py"
    tree = _parse(path)
    functions_using_it: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Name) and inner.id == "max_string_bytes":
                    functions_using_it.add(node.name)
                if isinstance(inner, ast.arg) and inner.arg == "max_string_bytes":
                    functions_using_it.add(node.name)
    assert functions_using_it == {"parse_json", "_postwalk"}
