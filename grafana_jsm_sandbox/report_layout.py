"""Pure seven-section ADF layout for synthetic ticket-16 Report text.

Shape and byte checks do not verify evidence, authorize Jira, or produce a
complete Report revision.
"""

from __future__ import annotations

from .report_adf import MAX_TEXT_BYTES, ADFError, ADFPreflight, encode_preflight

SECTION_TITLES = (
    ("summary", "Summary"),
    ("blast_radius", "Blast radius"),
    ("timeline", "Timeline"),
    ("evidence", "Evidence"),
    ("suggested_root_cause", "Suggested root cause"),
    ("suggested_remediation", "Suggested remediation"),
    ("fingerprints", "Fingerprints explained"),
)
_SECTION_KEYS = frozenset(key for key, _ in SECTION_TITLES)


def _fail(code: str) -> None:
    raise ADFError(code) from None


def render_report_layout(sections: object) -> ADFPreflight:
    """Return canonical ADF bytes for exactly seven caller-supplied sections."""
    if (type(sections) is not dict or len(sections) != len(_SECTION_KEYS)
            or any(type(key) is not str for key in sections)
            or set(sections) != _SECTION_KEYS):
        _fail("report_layout_shape")
    content = []
    for key, title in SECTION_TITLES:
        supplied = sections[key]
        if type(supplied) is not str:
            _fail("report_layout_shape")
        if len(supplied) > MAX_TEXT_BYTES:
            _fail("json_string_too_long")
        if not supplied.strip():
            _fail("report_layout_shape")
        content.extend((
            {"type": "heading", "attrs": {"level": 2},
             "content": [{"type": "text", "text": title}]},
            {"type": "paragraph", "content": [{"type": "text", "text": supplied}]},
        ))
    return encode_preflight({"version": 1, "type": "doc", "content": content})
