"""Pure byte preflight for the ticket-16 synthetic ADF subset.

This does not build a Report or authorize a Jira operation. Native ADF
features remain disabled until their supported shapes are pinned separately.
"""

from __future__ import annotations

import dataclasses
import hashlib

from .forwarder_json import JSONPolicyError, canonical_json, parse_json

MAX_ADF_BYTES = 8_192
MAX_TEXT_BYTES = 2_048
MAX_BLOCKS = 128


class ADFError(ValueError):
    """Fixed, non-diagnostic preflight rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclasses.dataclass(frozen=True)
class ADFPreflight:
    body: bytes
    byte_count: int
    sha256: str


def _fail(code: str) -> None:
    raise ADFError(code) from None


def _keys(value: object, expected: set[str]) -> bool:
    return (
        type(value) is dict
        and len(value) == len(expected)
        and all(type(key) is str for key in value)
        and set(value) == expected
    )


def _text_code(value: object) -> str | None:
    if not _keys(value, {"type", "text"}):
        return "adf_shape"
    if type(value["type"]) is not str or value["type"] != "text":
        return "adf_shape"
    text = value["text"]
    if type(text) is not str or not text:
        return "adf_shape"
    # Character count is a constant-time lower bound for UTF-8 byte count;
    # reject a huge string before the bounded encoding below allocates.
    if len(text) > MAX_TEXT_BYTES:
        return "json_string_too_long"
    code = None
    try:
        text_bytes = len(text.encode("utf-8"))
    except UnicodeEncodeError:
        code = "json_unicode"
    if code is not None:
        return code
    if text_bytes > MAX_TEXT_BYTES:
        return "json_string_too_long"
    return None


def _shape_code(value: object) -> str | None:
    if not _keys(value, {"version", "type", "content"}):
        return "adf_shape"
    if type(value["version"]) is not int or value["version"] != 1:
        return "adf_shape"
    if type(value["type"]) is not str or value["type"] != "doc":
        return "adf_shape"
    if type(value["content"]) not in (list, tuple):
        return "adf_shape"
    if not value["content"] or len(value["content"]) > MAX_BLOCKS:
        return "adf_shape"
    for block in value["content"]:
        if type(block) is not dict or type(block.get("type")) is not str:
            return "adf_shape"
        if block["type"] not in ("heading", "paragraph"):
            return "adf_shape"
        if block["type"] == "heading":
            if not _keys(block, {"type", "attrs", "content"}):
                return "adf_shape"
            attrs = block["attrs"]
            if (not _keys(attrs, {"level"})
                    or type(attrs["level"]) is not int or attrs["level"] != 2):
                return "adf_shape"
        elif not _keys(block, {"type", "content"}):
            return "adf_shape"
        content = block["content"]
        if type(content) not in (list, tuple) or len(content) != 1:
            return "adf_shape"
        code = _text_code(content[0])
        if code is not None:
            return code
    return None


def decode_preflight(data: object) -> ADFPreflight:
    """Accept exact canonical UTF-8 bytes for the pinned ADF subset."""
    if type(data) is not bytes:
        _fail("adf_argument")
    if len(data) > MAX_ADF_BYTES:
        _fail("adf_overflow")
    code = None
    try:
        value = parse_json(data, max_bytes=MAX_ADF_BYTES)
    except JSONPolicyError as error:
        code = error.code
    if code is not None:
        raise ADFError(code) from None
    code = _shape_code(value)
    if code is not None:
        _fail(code)
    # The shape check bounds each text node. Canonicalizing after that check
    # pins the bytes that are counted and hashed.
    body = canonical_json(value)
    if body != data:
        _fail("adf_noncanonical")
    return ADFPreflight(body, len(body), hashlib.sha256(body).hexdigest())


def encode_preflight(value: object) -> ADFPreflight:
    """Canonicalize a local ADF value, then apply the same strict read-back."""
    code = _shape_code(value)
    if code is not None:
        _fail(code)
    code = None
    try:
        body = canonical_json(value)
    except JSONPolicyError as error:
        code = error.code
    if code is not None:
        raise ADFError(code) from None
    return decode_preflight(body)
