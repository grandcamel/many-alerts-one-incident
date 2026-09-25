"""Seven-section local formatting is not claim or Jira acceptance."""

import hashlib
import json

import pytest

from grafana_jsm_sandbox.report_adf import ADFError, decode_preflight
from grafana_jsm_sandbox.report_layout import SECTION_TITLES, render_report_layout


def _sections():
    return {key: f"Synthetic {key}; support unreviewed." for key, _ in SECTION_TITLES}


def _code(call, expected):
    with pytest.raises(ADFError) as caught:
        call()
    assert caught.value.code == expected
    assert caught.value.args == (expected,)


def test_exact_seven_headings_paragraphs_canonical_bytes_and_readback(tmp_path):
    sections = _sections()
    artifact = render_report_layout(sections)
    parsed = json.loads(artifact.body)
    assert list(parsed) == ["content", "type", "version"]
    assert parsed["type"] == "doc" and parsed["version"] == 1
    assert len(parsed["content"]) == 14
    for index, (key, title) in enumerate(SECTION_TITLES):
        heading, paragraph = parsed["content"][index * 2:index * 2 + 2]
        assert heading == {"type": "heading", "attrs": {"level": 2},
                           "content": [{"type": "text", "text": title}]}
        assert paragraph == {"type": "paragraph", "content": [
            {"type": "text", "text": sections[key]},
        ]}
    assert artifact.byte_count == len(artifact.body) <= 8192
    assert artifact.sha256 == hashlib.sha256(artifact.body).hexdigest()
    assert decode_preflight(artifact.body) == artifact
    path = tmp_path / "seven-sections.json"
    path.write_bytes(artifact.body)
    assert decode_preflight(path.read_bytes()) == artifact


def test_explicit_unknown_partial_and_citation_strings_remain_inert_text():
    sections = _sections()
    sections["evidence"] = "Partial: citation-id-123 and https://example.invalid are unreviewed."
    sections["suggested_root_cause"] = "Undetermined; no retrieved response establishes a cause."
    artifact = render_report_layout(sections)
    parsed = json.loads(artifact.body)
    assert parsed["content"][7]["content"][0]["text"] == sections["evidence"]
    assert parsed["content"][9]["content"][0]["text"] == sections["suggested_root_cause"]
    assert b'"marks"' not in artifact.body
    assert b'"supported"' not in artifact.body
    assert b'"confidence"' not in artifact.body
    assert b'"verified"' not in artifact.body


@pytest.mark.parametrize("change", [
    lambda sections: sections.pop("timeline"),
    lambda sections: sections.update(extra="unreviewed"),
    lambda sections: sections.update(summary=""),
    lambda sections: sections.update(summary="  \n  "),
    lambda sections: sections.update(summary=None),
    lambda sections: sections.update(summary=True),
])
def test_missing_extra_blank_or_nontext_section_is_rejected(change):
    sections = _sections()
    change(sections)
    _code(lambda: render_report_layout(sections), "report_layout_shape")


def test_unicode_escaping_and_byte_limits_are_inherited_from_adf():
    sections = _sections()
    sections["summary"] = 'é "quoted" \\ newline\n'
    artifact = render_report_layout(sections)
    assert b"\xc3\xa9" in artifact.body and b'\\"quoted\\"' in artifact.body
    assert b"\\\\" in artifact.body and b"\\n" in artifact.body
    sections["summary"] = "é" * 1025
    _code(lambda: render_report_layout(sections), "json_string_too_long")
    sections["summary"] = "x" * 2049
    _code(lambda: render_report_layout(sections), "json_string_too_long")
    sections["summary"] = "\ud800"
    _code(lambda: render_report_layout(sections), "json_unicode")
    sections = dict.fromkeys(_sections(), "x" * 1400)
    _code(lambda: render_report_layout(sections), "adf_overflow")


def test_hostile_types_do_not_enter_string_or_key_comparison():
    class Hostile:
        __hash__ = object.__hash__

        def __eq__(self, other):
            raise AssertionError("hostile equality was reached")

        def __str__(self):
            raise AssertionError("hostile formatting was reached")

    sections = _sections()
    sections["summary"] = Hostile()
    _code(lambda: render_report_layout(sections), "report_layout_shape")
    sections = _sections()
    sections[Hostile()] = sections.pop("summary")
    _code(lambda: render_report_layout(sections), "report_layout_shape")
