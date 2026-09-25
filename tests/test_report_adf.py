"""Offline byte preflight for the ticket-16 synthetic ADF subset."""

import hashlib
import io
import json

import pytest

from grafana_jsm_sandbox.forwarder_json import parse_json
from grafana_jsm_sandbox.report_adf import (
    ADFError,
    decode_preflight,
    encode_preflight,
)

EXAMPLE = (
    b'{"version":1,"type":"doc","content":['
    b'{"type":"heading","attrs":{"level":2},"content":'
    b'[{"type":"text","text":"Summary"}]},'
    b'{"type":"paragraph","content":[{"type":"text","text":'
    b'"Observed checkout error evidence is cited; root cause remains an inference."}]},'
    b'{"type":"paragraph","content":[{"type":"text","text":'
    b'"Status: partial. Confidence: medium."}]}]}'
)


def _document(*texts):
    return {
        "version": 1, "type": "doc", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
            for text in texts
        ],
    }


def _sized_document(size):
    empty = _document("", "", "", "")
    overhead = len(json.dumps(empty, sort_keys=True, separators=(",", ":")).encode())
    text_bytes = size - overhead
    assert 4 <= text_bytes <= 4 * 2048
    lengths = []
    for remaining in (3, 2, 1, 0):
        length = min(2048, text_bytes - remaining)
        lengths.append(length)
        text_bytes -= length
    assert text_bytes == 0
    return _document(*(length * "x" for length in lengths))


def _code(call, expected):
    with pytest.raises(ADFError) as caught:
        call()
    assert caught.value.code == expected
    assert caught.value.args == (expected,)


def test_proposal_example_is_parsed_then_canonicalized_and_read_back():
    parsed = parse_json(EXAMPLE, max_bytes=8192, max_string_bytes=2048)
    artifact = encode_preflight(parsed)
    assert artifact.body != EXAMPLE  # proposal's key order is not canonical
    assert artifact.body == json.dumps(
        parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    assert decode_preflight(artifact.body) == artifact
    assert artifact.byte_count == len(artifact.body)
    assert artifact.sha256 == hashlib.sha256(artifact.body).hexdigest()
    assert b'"sha256"' not in artifact.body
    _code(lambda: decode_preflight(EXAMPLE), "adf_noncanonical")


def test_unicode_and_escaping_are_counted_after_serialization():
    artifact = encode_preflight(_document('é "quoted" \\ newline\n'))
    assert b"\xc3\xa9" in artifact.body
    assert b'\\"quoted\\"' in artifact.body
    assert b"\\\\" in artifact.body
    assert b"\\n" in artifact.body
    assert artifact.byte_count == len(artifact.body)
    assert artifact.byte_count > len('é "quoted" \\ newline\n')
    assert decode_preflight(artifact.body) == artifact


def test_text_byte_limit_and_exact_document_boundary():
    assert decode_preflight(encode_preflight(_document("é" * 1024)).body).byte_count > 2048
    _code(lambda: encode_preflight(_document("é" * 1025)), "json_string_too_long")
    exact = _sized_document(8192)
    raw = json.dumps(exact, sort_keys=True, separators=(",", ":")).encode()
    assert len(raw) == 8192
    assert encode_preflight(exact).byte_count == 8192
    assert decode_preflight(raw).byte_count == 8192
    overflow = _sized_document(8193)
    too_large = json.dumps(overflow, sort_keys=True, separators=(",", ":")).encode()
    assert len(too_large) == 8193
    _code(lambda: encode_preflight(overflow), "adf_overflow")
    _code(lambda: decode_preflight(too_large), "adf_overflow")


@pytest.mark.parametrize(("data", "code"), [
    (b"\xff", "json_encoding"),
    (b'{"type":"doc","type":"doc"}', "json_duplicate_key"),
    (b'{"type":"doc","version":NaN}', "json_number"),
    (b'{"content":[],"type":"doc","version":1}', "adf_shape"),
    (b'{"content":[{"content":[],"type":"bulletList"}],"type":"doc","version":1}',
     "adf_shape"),
])
def test_malformed_or_unsupported_bytes_fail_closed(data, code):
    _code(lambda: decode_preflight(data), code)


@pytest.mark.parametrize("bad", [
    _document(""),
    {**_document("valid"), "extra": True},
    {**_document("valid"), "version": True},
    {"version": 1, "type": "doc", "content": [{
        "type": "heading", "attrs": {"level": 3},
        "content": [{"type": "text", "text": "wrong level"}],
    }]},
    {"version": 1, "type": "doc", "content": [{
        "type": "paragraph", "content": [{"type": "text", "text": "x", "marks": []}],
    }]},
    {"version": 1, "type": "doc", "content": [{
        "type": "paragraph", "content": [{"type": "paragraph", "content": []}],
    }]},
])
def test_unknown_shape_and_attributes_fail_closed(bad):
    _code(lambda: encode_preflight(bad), "adf_shape")


def test_hostile_python_values_and_early_input_bounds_fail_closed():
    class Hostile:
        def __eq__(self, other):
            raise AssertionError("caller-controlled equality was reached")

        def __ne__(self, other):
            raise AssertionError("caller-controlled inequality was reached")

    for bad in (
        {**_document("valid"), "type": Hostile()},
        _document("valid", *(("x",) * 128)),
    ):
        _code(lambda bad=bad: encode_preflight(bad), "adf_shape")
    _code(lambda: encode_preflight(_document("x" * 100_000)),
          "json_string_too_long")
    _code(lambda: encode_preflight(_document("\ud800")), "json_unicode")


def test_exact_file_and_stdin_equivalent_byte_readback(tmp_path):
    artifact = encode_preflight(_document("Synthetic, partial evidence only."))
    path = tmp_path / "adf.json"
    path.write_bytes(artifact.body)
    assert decode_preflight(path.read_bytes()) == artifact
    assert decode_preflight(io.BytesIO(artifact.body).read()) == artifact
