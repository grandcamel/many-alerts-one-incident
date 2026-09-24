"""Corpus tests for ``journal_ingress`` (ticket 37, unit 16; Tester T, cases
C1-C10 of ``reviews/journal-ingress/implementation-plan.md``).

This module defines the three helpers the plan assigns to Tester T --
``wire()``, ``capture_rows()`` and ``grafana_group()`` -- and
``tests/test_journal_ingress_adversarial.py`` imports them. Every fact
asserted here (the census in C2, the goldens in C4) was independently
recomputed against the committed ``journal_source``/``forwarder_json``
modules and, separately, with plain ``json``/``hashlib`` only, before being
pinned; see the plan's "Claims re-measured" table and probes s1/s2.

Every capture and fixture is read read-only from the committed tree. No test
here writes a repository file. C10 opens a private ``tmp_path`` journal with
real syncs, mirroring ``tests/test_recovery_journal.py``'s skip condition.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import pathlib
import random

import pytest

from grafana_jsm_sandbox import journal_ingress as ji
from grafana_jsm_sandbox import journal_source as js
from grafana_jsm_sandbox import journal_store
from grafana_jsm_sandbox import recovery_journal as rj
from grafana_jsm_sandbox.forwarder_json import canonical_json
from grafana_jsm_sandbox.notification import validate_notification

REPOSITORY = pathlib.Path(__file__).resolve().parent.parent
CAPTURE_DIR = (
    REPOSITORY / ".scratch" / "many-alerts-one-incident" / "reviews" / "ticket-14" / "jira"
)
FIXTURES = REPOSITORY / "fixtures"


# === The three shared helpers (plan: Tester T owns these) ====================


def wire(obj: object) -> bytes:
    """Go-style re-encoding of a parsed Notification body (plan "Worked
    examples"): compact ``json.dumps``, then ``<``, ``>``, ``&``, U+2028 and
    U+2029 replaced by Go's lowercase escapes, then UTF-8. Pinned by
    ``raw_len`` for all 115 captures (C1)."""
    text = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    text = (
        text.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )
    return text.encode("utf-8")


def capture_rows():
    """Yield ``(filename, line_no, envelope)`` for every row of every
    committed ``notifications-*.jsonl`` capture, in sorted file order and
    1-based line order."""
    for path in sorted(CAPTURE_DIR.glob("notifications-*.jsonl")):
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            yield path.name, line_no, json.loads(line)


SERVICES = (
    "accounting", "ad", "cart", "checkout", "currency", "email", "flagd",
    "fraud-detection", "frontend", "frontend-proxy", "image-provider", "kafka",
    "load-generator", "payment", "product-catalog", "quote", "recommendation",
    "shipping", "valkey-cart", "otel-collector", "jaeger", "grafana", "prometheus",
    "opensearch", "llm", "react-native-app", "ts-web", "python-svc", "go-svc",
    "dotnet-svc", "java-svc", "ruby-svc", "rust-svc",
)


def _grafana_group_section(alert: dict) -> str:
    labels = "".join(f" - {k} = {v}\n" for k, v in alert["labels"].items())
    annotations = "".join(f" - {k} = {v}\n" for k, v in alert["annotations"].items())
    values = ", ".join(f"{k}={v}" for k, v in alert["values"].items())
    return (
        f"Value: {values}\nLabels:\n{labels}Annotations:\n{annotations}"
        f"Source: {alert['generatorURL']}\nSilence: {alert['silenceURL']}\n"
    )


def grafana_group(base: dict, n: int, status: str, n_values: int = 2, seed: int = 0):
    """The plan's normative realistic N-alert template (X3), copied from
    ``u16-design/synth-probe/ceilings.py:make()``. ``base`` is a capture
    envelope (with a ``"body"`` key), e.g. from ``capture_rows()``; its first
    alert is the template. Returns ``(wire_bytes, body_dict)``."""
    body = copy.deepcopy(base["body"])
    template = body["alerts"][0]
    rnd = random.Random(seed * 1000 + n)
    alerts = []
    for i in range(n):
        service = SERVICES[i % len(SERVICES)] + ("" if i < len(SERVICES) else f"-{i}")
        alert = copy.deepcopy(template)
        alert["status"] = status
        alert["labels"] = {
            key: (service if key in ("service", "service_name") else value)
            for key, value in template["labels"].items()
        }
        alert["fingerprint"] = hashlib.sha256(service.encode()).hexdigest()[:16]
        alert["values"] = {
            chr(65 + k): (rnd.random() / 7 if k == 0 else (1 if status == "firing" else 0))
            for k in range(n_values)
        }
        alert["endsAt"] = (
            "0001-01-01T00:00:00Z" if status == "firing" else "2026-09-17T22:05:20Z"
        )
        alert["silenceURL"] = template["silenceURL"].split("&matcher=cascade")[0] + "".join(
            f"&matcher={key}%3D{value}"
            for key, value in sorted(alert["labels"].items())
            if key not in ("alertname", "grafana_folder")
        ) + "&orgId=1"
        alert["valueString"] = ", ".join(
            f"[ var='{key}' labels={{service={service}, service_name={service}}} value={value} ]"
            for key, value in alert["values"].items()
        )
        alerts.append(alert)
    body["alerts"] = alerts
    body["status"] = status
    body["commonLabels"] = {
        key: value
        for key, value in alerts[0]["labels"].items()
        if all(alert["labels"].get(key) == value for alert in alerts)
    }
    header = "**Firing**\n\n" if status == "firing" else "**Resolved**\n\n"
    body["message"] = header + "\n".join(_grafana_group_section(alert) for alert in alerts)
    return wire(body), body


# === Private helpers (not part of the plan's three, used only in this file) ==


def _capture_row(name: str, line_no: int) -> dict:
    for row_name, row_line, envelope in capture_rows():
        if row_name == name and row_line == line_no:
            return envelope
    raise LookupError((name, line_no))


def _oracle_number(value: object) -> str:
    """Independent canonicalization mirroring ``canonical_number`` (plan C1):
    an int through ``str``, a float through ``repr`` unless integral, in
    which case through ``str(int(...))``. Never imports ``journal_source``."""
    if isinstance(value, bool):
        raise TypeError("unexpected bool in a captured values map")
    if isinstance(value, int):
        return str(value)
    parsed = float(value)
    if parsed.is_integer() and abs(parsed) <= 2**53 - 1:
        return str(int(parsed))
    return repr(parsed)


def _oracle_alert(alert: dict):
    values = alert.get("values")
    if values is not None:
        values = tuple(
            sorted(
                (ref_id, None if value is None else _oracle_number(value))
                for ref_id, value in values.items()
            )
        )
    starts_at = alert.get("startsAt")
    if starts_at == ji.GO_ZERO_TIME:
        starts_at = None
    return (alert["fingerprint"], alert["status"], values, starts_at)


def _independent_tagged_digest(tag: str, value: object) -> str:
    """The same tagged-digest family as ``journal_source.tagged_digest``, but
    through plain ``json.dumps`` -- independent of the module under test and
    of ``forwarder_json.canonical_json`` (plan C4)."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(tag.encode("ascii") + b"\x00" + encoded.encode("ascii")).hexdigest()


def _independent_source_json(source: js.SourceRecord) -> dict:
    plain = js.source_to_json(source)
    return json.loads(json.dumps({**plain, "alerts": [dict(a) for a in plain["alerts"]]}))


CAPTURE_CASES = list(capture_rows())
CAPTURE_IDS = [f"{name}:{line_no}" for name, line_no, _ in CAPTURE_CASES]
MULTI_ALERT_CAPTURES = [
    case for case in CAPTURE_CASES if len(case[2]["body"]["alerts"]) > 1
]
MULTI_ALERT_IDS = [f"{name}:{line_no}" for name, line_no, _ in MULTI_ALERT_CAPTURES]


# === C1: all 115 captures admit and match an independent oracle ==============


@pytest.mark.parametrize("name,line_no,envelope", CAPTURE_CASES, ids=CAPTURE_IDS)
def test_c1_all_captures_admit_and_match_oracle(name, line_no, envelope):
    body = envelope["body"]
    raw = wire(body)
    assert len(raw) == envelope["raw_len"]

    outcome = ji.sanitize_notification(raw)
    assert outcome.refusal is None, (name, line_no, outcome.refusal)
    source = outcome.source
    assert outcome.starts_at_dropped == ()
    assert js.validate_source(source) == source

    oracle = sorted(_oracle_alert(alert) for alert in body["alerts"])
    got = [(alert.fingerprint, alert.status, alert.values, alert.starts_at)
           for alert in source.alerts]
    assert got == oracle

    assert len(source.alerts) == envelope["n_alerts"]
    assert source.truncated_alerts == body.get("truncatedAlerts")
    assert source.body_digest == hashlib.sha256(b"rj.body.v1\x00" + raw).hexdigest()


# === C2: census pin ===========================================================


def test_c2_census_pin():
    per_file: dict[str, int] = {}
    total_members = firing = resolved = 0
    max_alerts = max_total_values = 0
    sizes: list[tuple[int, str, int]] = []
    group_keys: set[str] = set()

    for name, line_no, envelope in CAPTURE_CASES:
        body = envelope["body"]
        raw = wire(body)
        outcome = ji.sanitize_notification(raw)
        assert outcome.refusal is None, (name, line_no, outcome.refusal)
        source = outcome.source

        per_file[name] = per_file.get(name, 0) + 1
        max_alerts = max(max_alerts, len(source.alerts))
        total_values = 0
        for alert in source.alerts:
            total_members += 1
            if alert.status == "firing":
                firing += 1
            else:
                resolved += 1
            total_values += len(alert.values or ())
        max_total_values = max(max_total_values, total_values)
        size = len(canonical_json(js.source_to_json(source), ascii_only=True))
        sizes.append((size, name, line_no))
        group_keys.add(body["groupKey"])

    assert len(CAPTURE_CASES) == 115
    assert per_file == {
        "notifications-adFailure.jsonl": 3,
        "notifications-cartFailure.jsonl": 23,
        "notifications-emailMemoryLeak.jsonl": 63,
        "notifications-paymentUnreachable.jsonl": 26,
    }
    assert total_members == 168
    assert firing == 149
    assert resolved == 19
    assert max_alerts == 4
    assert max_total_values == 8
    assert min(sizes)[0] == 375
    assert max(sizes) == (800, "notifications-paymentUnreachable.jsonl", 21)
    assert len(group_keys) == 6
    assert {len(key) for key in group_keys} == {63, 70, 72, 80, 81, 83}


# === C3: sc31 known-answer members ============================================


SC31_KNOWN_ANSWERS = {
    ("notifications-paymentUnreachable.jsonl", 1): (
        ("5e8d72dc87b1ff35", "firing", {"A": 0.11440082443757411, "B": 1}),
    ),
    ("notifications-paymentUnreachable.jsonl", 2): (
        ("5e8d72dc87b1ff35", "firing", {"A": 0.19568987579698632, "B": 1}),
    ),
    ("notifications-paymentUnreachable.jsonl", 16): (
        ("6cd7e206a0716d2d", "resolved", {"A": 0.09999958333506945, "B": 0}),
        ("5e8d72dc87b1ff35", "firing", {"A": 0.1999991666701389, "B": 1}),
        ("8e2d9556f6c757b5", "resolved", {"A": 0.09999958333506945, "B": 0}),
    ),
    ("notifications-paymentUnreachable.jsonl", 18): (
        ("5e8d72dc87b1ff35", "firing", {"A": 0.18333409722540508, "B": 1}),
    ),
    ("notifications-paymentUnreachable.jsonl", 20): (
        ("6cd7e206a0716d2d", "firing", {"A": 0.13333111114814752, "B": 1}),
        ("5e8d72dc87b1ff35", "firing", {"A": 0.26666222229629505, "B": 1}),
        ("8e2d9556f6c757b5", "firing", {"A": 0.13749770837152714, "B": 1}),
    ),
    ("notifications-paymentUnreachable.jsonl", 21): (
        ("f09facf2b8f5b694", "resolved", {"A": 0.01666638889351844, "B": 0}),
        ("4396dcd5ddc23476", "resolved", {"A": 0.01666638889351844, "B": 0}),
        ("4bde20aac01f95a2", "resolved", {"A": 0.02083298611689805, "B": 0}),
        ("b3587dd72657d226", "resolved", {"A": 0.02499958334027766, "B": 0}),
    ),
    ("notifications-paymentUnreachable.jsonl", 23): (
        ("6cd7e206a0716d2d", "resolved", {"A": 0.08333125005208204, "B": 0}),
        ("5e8d72dc87b1ff35", "firing", {"A": 0.16666250010416409, "B": 1}),
        ("8e2d9556f6c757b5", "resolved", {"A": 0.08749781255468614, "B": 0}),
    ),
    ("notifications-paymentUnreachable.jsonl", 24): (
        ("5e8d72dc87b1ff35", "firing", {"A": 0.16666250010416409, "B": 1}),
    ),
    ("notifications-paymentUnreachable.jsonl", 26): (
        ("6cd7e206a0716d2d", "resolved", {"A": 0, "B": 0}),
        ("5e8d72dc87b1ff35", "resolved", {"A": 0, "B": 0}),
        ("8e2d9556f6c757b5", "resolved", {"A": 0, "B": 0}),
    ),
    ("notifications-emailMemoryLeak.jsonl", 57): (
        ("391dc40ca1dfd1a3", "resolved", {"A": 55042048, "B": 55042048, "C": 0}),
    ),
    ("notifications-emailMemoryLeak.jsonl", 62): (
        ("90ec22b91f46a6ce", "resolved", {"A": -1, "B": -1}),
    ),
    ("notifications-emailMemoryLeak.jsonl", 63): (
        ("3253da2ba16cb0cb", "resolved", {"A": 0, "B": 0}),
    ),
    ("notifications-cartFailure.jsonl", 1): (
        ("bddc72414d172719", "firing", {"A": 5, "B": 1}),
    ),
    ("notifications-cartFailure.jsonl", 6): (
        ("5de6002ca2547b11", "firing", {"A": 1, "B": 1}),
    ),
}


@pytest.mark.parametrize(
    "key", sorted(SC31_KNOWN_ANSWERS), ids=[f"{k[0]}:{k[1]}" for k in sorted(SC31_KNOWN_ANSWERS)],
)
def test_c3_sc31_known_answers(key):
    name, line_no = key
    envelope = _capture_row(name, line_no)
    source = ji.sanitize_notification(wire(envelope["body"])).source
    assert source is not None

    expected = sorted(
        (
            fingerprint,
            status,
            tuple(sorted((ref_id, _oracle_number(v)) for ref_id, v in values.items())),
        )
        for fingerprint, status, values in SC31_KNOWN_ANSWERS[key]
    )
    got = [(alert.fingerprint, alert.status, alert.values) for alert in source.alerts]
    assert got == expected


# === C4: goldens ===============================================================


GOLDENS = {
    ("notifications-paymentUnreachable.jsonl", 1): (
        "0dd74a18eb42deb3bcbdcda622b156df45c85021550cff705a672e626f528da4",
        "5deaf914a2a751fefe64e9b9077fdadad2f5fe11c224ba5451d6d66bb6c7876e",
        "f346b9f748cae4aa07850b2b28916197174af887bcec71eff5629a741a021290",
        "b4f1f3da5cc53679caca4f1632c891e15d415437514bbaa4c9341d4526680e82",
    ),
    ("notifications-paymentUnreachable.jsonl", 16): (
        "db9eea9713d51f6eb11f3a029fd496aa37949124a9dced0308a2e5d96d193157",
        "5deaf914a2a751fefe64e9b9077fdadad2f5fe11c224ba5451d6d66bb6c7876e",
        "1637469fe9cd721ee9b61f382cdd7b89a3e907319afcd48551b67edc80ba7a66",
        "94dc7ed163d2f5a206e4af81d7d1ba21ac2a7edd24bd450059cf0e1059c07709",
    ),
    ("notifications-paymentUnreachable.jsonl", 21): (
        "cd2f543c48a81816a7d4fb4cbafdff69df45c94cce0b5ff54056a2a20e1839ea",
        "9d37267f6830d441f2c6ce82698704b397a29c16eb135973907fa2fa38045ce4",
        "f28976b66615201a67ca06a8c1845be6a80d7c3702befc2f7ee045aa6c397d99",
        "dffbf0e8ea48512fbe05e39cbfccd63f8a5c16b9a6844607342a3f524014fd24",
    ),
    ("notifications-emailMemoryLeak.jsonl", 57): (
        "547b68200de70cf41fc33bec3de8ac64ec27547b9778d47f10c6966a0e106424",
        "bd3c8b5e393bb0a691b49c6ac0ee7e2a2d60e035d1b73f0d7671338a97b2b2b6",
        "350dcade09681a629f7e4f32acd243b3f69592e836359a2d2bf34ab762e59560",
        "4f5c8754f674ed912ef635f7a024c5236c8eee346e9051e8577422f608b9f6ed",
    ),
}
FIXTURE_GOLDENS = {
    "notification-firing.json": (
        "8384bd0bc8a9e5680014ee5389312298742b665701fc847d14b9de7a4abba5d4",
        "aa57d128272b37ba89511a41b61e587aa198e2676d80f71925332c0d582bb7f8",
        "6edd2da5b2d84802d63b6ab3cf663804e6e0e0f550c31f4e0c1df53f45067339",
        "a99b74e0622bbf52ab6f66f38af0034e030e8b301bd0a399b97e7931f81f262d",
    ),
    "notification-resolved.json": (
        "ca471928e4c96cb292cdacdbb1124846c1667b9e54f9138b152888de1b05c3cf",
        "aa57d128272b37ba89511a41b61e587aa198e2676d80f71925332c0d582bb7f8",
        "d0b46f6b0352fbd887d8196473f833da2c473e63bc9fbd6640a4f74b8f04009f",
        "107b7990e93f96f157da3e1ca394fd0697020a1d94647a7cf30d91b5fe8963f6",
    ),
}


@pytest.mark.parametrize(
    "key", sorted(GOLDENS), ids=[f"{k[0]}:{k[1]}" for k in sorted(GOLDENS)],
)
def test_c4_capture_goldens(key):
    body_digest_g, source_group_g, source_digest_g, dedupe_key_g = GOLDENS[key]
    envelope = _capture_row(*key)
    raw = wire(envelope["body"])
    source = ji.sanitize_notification(raw).source
    assert source is not None

    assert source.body_digest == body_digest_g
    assert source.source_group == source_group_g
    assert js.source_digest(source) == source_digest_g
    assert js.dedupe_key(source) == dedupe_key_g

    # Independent recomputation: no reliance on journal_source's own digests.
    assert hashlib.sha256(b"rj.body.v1\x00" + raw).hexdigest() == body_digest_g
    plain = _independent_source_json(source)
    assert _independent_tagged_digest("rj.source.v1", plain) == source_digest_g
    rows = [[a["fingerprint"], a["status"], a["values"]] for a in plain["alerts"]]
    assert _independent_tagged_digest("rj.dedupe-key.v1", rows) == dedupe_key_g


@pytest.mark.parametrize("filename", sorted(FIXTURE_GOLDENS))
def test_c4_fixture_goldens(filename):
    body_digest_g, source_group_g, source_digest_g, dedupe_key_g = FIXTURE_GOLDENS[filename]
    raw = (FIXTURES / filename).read_bytes()
    source = ji.sanitize_notification(raw).source
    assert source is not None

    assert source.body_digest == body_digest_g
    assert source.source_group == source_group_g
    assert js.source_digest(source) == source_digest_g
    assert js.dedupe_key(source) == dedupe_key_g
    assert hashlib.sha256(b"rj.body.v1\x00" + raw).hexdigest() == body_digest_g


E1_CANONICAL_JSON = (
    b'{"alerts":[{"fingerprint":"5e8d72dc87b1ff35","starts_at":"2026-09-17T21:56:20Z",'
    b'"status":"firing","values":{"A":"0.11440082443757411","B":"1"}}],'
    b'"body_digest":"0dd74a18eb42deb3bcbdcda622b156df45c85021550cff705a672e626f528da4",'
    b'"provenance":{"kind":"http","line":null,"path":"/notification"},'
    b'"source_group":"5deaf914a2a751fefe64e9b9077fdadad2f5fe11c224ba5451d6d66bb6c7876e",'
    b'"truncated_alerts":0}'
)
E2_CANONICAL_JSON = (
    b'{"alerts":[{"fingerprint":"5e8d72dc87b1ff35","starts_at":"2026-09-17T21:56:20Z",'
    b'"status":"firing","values":{"A":"0.1999991666701389","B":"1"}},'
    b'{"fingerprint":"6cd7e206a0716d2d","starts_at":"2026-09-17T21:58:30Z",'
    b'"status":"resolved","values":{"A":"0.09999958333506945","B":"0"}},'
    b'{"fingerprint":"8e2d9556f6c757b5","starts_at":"2026-09-17T21:58:20Z",'
    b'"status":"resolved","values":{"A":"0.09999958333506945","B":"0"}}],'
    b'"body_digest":"db9eea9713d51f6eb11f3a029fd496aa37949124a9dced0308a2e5d96d193157",'
    b'"provenance":{"kind":"http","line":null,"path":"/notification"},'
    b'"source_group":"5deaf914a2a751fefe64e9b9077fdadad2f5fe11c224ba5451d6d66bb6c7876e",'
    b'"truncated_alerts":0}'
)


def test_c4_e1_e2_full_canonical_json():
    source1 = ji.sanitize_notification(
        wire(_capture_row("notifications-paymentUnreachable.jsonl", 1)["body"])
    ).source
    source2 = ji.sanitize_notification(
        wire(_capture_row("notifications-paymentUnreachable.jsonl", 16)["body"])
    ).source
    assert canonical_json(js.source_to_json(source1), ascii_only=True) == E1_CANONICAL_JSON
    assert canonical_json(js.source_to_json(source2), ascii_only=True) == E2_CANONICAL_JSON


# === C5: legacy fixtures =======================================================


def test_c5_legacy_fixtures_admitted_and_keyed():
    firing = ji.sanitize_notification((FIXTURES / "notification-firing.json").read_bytes())
    repeat = ji.sanitize_notification(
        (FIXTURES / "notification-firing-repeat.json").read_bytes()
    )
    resolved = ji.sanitize_notification((FIXTURES / "notification-resolved.json").read_bytes())
    for outcome in (firing, repeat, resolved):
        assert outcome.refusal is None

    assert firing.source == repeat.source
    assert js.dedupe_key(firing.source) == (
        "a99b74e0622bbf52ab6f66f38af0034e030e8b301bd0a399b97e7931f81f262d"
    )
    assert js.dedupe_key(resolved.source) == (
        "107b7990e93f96f157da3e1ca394fd0697020a1d94647a7cf30d91b5fe8963f6"
    )
    legacy_group = "aa57d128272b37ba89511a41b61e587aa198e2676d80f71925332c0d582bb7f8"
    assert firing.source.source_group == legacy_group
    assert resolved.source.source_group == legacy_group


# === C6: exact-byte digest =====================================================


def test_c6_exact_byte_forms_same_key_distinct_digests():
    body = _capture_row("notifications-paymentUnreachable.jsonl", 1)["body"]
    compact = wire(body)
    forms = {
        "compact": compact,
        "pretty": json.dumps(body, indent=2).encode(),
        "trailing_newline": compact + b"\n",
        "leading_space": b" " + compact,
    }
    outcomes = {label: ji.sanitize_notification(raw) for label, raw in forms.items()}
    for label, outcome in outcomes.items():
        assert outcome.refusal is None, (label, outcome.refusal)

    sources = list(outcomes.values())
    base = sources[0].source
    for outcome in sources[1:]:
        source = outcome.source
        assert source.alerts == base.alerts
        assert source.source_group == base.source_group
        assert source.truncated_alerts == base.truncated_alerts
        assert js.dedupe_key(source) == js.dedupe_key(base)

    digests = {outcome.source.body_digest for outcome in sources}
    assert len(digests) == 4


# === C7: permutation ===========================================================


@pytest.mark.parametrize("name,line_no,envelope", MULTI_ALERT_CAPTURES, ids=MULTI_ALERT_IDS)
def test_c7_permutation_changes_only_body_digest(name, line_no, envelope):
    base_body = envelope["body"]
    base_source = ji.sanitize_notification(wire(base_body)).source
    assert base_source is not None

    shuffled = copy.deepcopy(base_body)
    random.Random(f"{name}:{line_no}").shuffle(shuffled["alerts"])
    for alert in shuffled["alerts"]:
        if alert.get("values"):
            alert["values"] = dict(reversed(list(alert["values"].items())))

    shuffled_source = ji.sanitize_notification(wire(shuffled)).source
    assert shuffled_source is not None

    replaced = dataclasses.replace(shuffled_source, body_digest=base_source.body_digest)
    assert replaced == base_source
    assert shuffled_source.body_digest != base_source.body_digest
    assert js.dedupe_key(shuffled_source) == js.dedupe_key(base_source)


def test_c7_multi_alert_capture_count_is_22():
    assert len(MULTI_ALERT_CAPTURES) == 22


# === C8: allowlist ==============================================================


READ_TOP_KEYS = frozenset({"groupKey", "truncatedAlerts", "alerts"})
READ_ALERT_KEYS = frozenset({"fingerprint", "status", "startsAt", "values"})


def test_c8_allowlist_ignored_fields_never_change_the_record():
    envelope = _capture_row("notifications-paymentUnreachable.jsonl", 16)
    base_body = envelope["body"]
    base_source = ji.sanitize_notification(wire(base_body)).source
    assert base_source is not None

    variants = 0
    for key in base_body:
        if key in READ_TOP_KEYS:
            continue
        for mutate in (
            lambda b, k=key: b.pop(k),
            lambda b, k=key: b.__setitem__(k, {"x": [1, None, "CANARY"]}),
        ):
            mutated = copy.deepcopy(base_body)
            mutate(mutated)
            source = ji.sanitize_notification(wire(mutated)).source
            variants += 1
            assert source is not None, key
            replaced = dataclasses.replace(source, body_digest=base_source.body_digest)
            assert replaced == base_source, key

    for key in base_body["alerts"][0]:
        if key in READ_ALERT_KEYS:
            continue
        for mutate in (
            lambda a, k=key: a.pop(k),
            lambda a, k=key: a.__setitem__(k, 12345),
        ):
            mutated = copy.deepcopy(base_body)
            for alert in mutated["alerts"]:
                mutate(alert)
            source = ji.sanitize_notification(wire(mutated)).source
            variants += 1
            assert source is not None, key
            replaced = dataclasses.replace(source, body_digest=base_source.body_digest)
            assert replaced == base_source, key

    assert variants == 40


# === C9: legacy subset ==========================================================


def test_c9_legacy_subset_every_admitted_body_passes_validate_notification():
    bodies = [wire(envelope["body"]) for _, _, envelope in CAPTURE_CASES]
    bodies.append((FIXTURES / "notification-firing.json").read_bytes())
    bodies.append((FIXTURES / "notification-firing-repeat.json").read_bytes())
    bodies.append((FIXTURES / "notification-resolved.json").read_bytes())

    payment1 = _capture_row("notifications-paymentUnreachable.jsonl", 1)["body"]
    compact = wire(payment1)
    bodies += [json.dumps(payment1, indent=2).encode(), compact + b"\n", b" " + compact]

    for name, line_no, envelope in MULTI_ALERT_CAPTURES:
        shuffled = copy.deepcopy(envelope["body"])
        random.Random(f"{name}:{line_no}").shuffle(shuffled["alerts"])
        for alert in shuffled["alerts"]:
            if alert.get("values"):
                alert["values"] = dict(reversed(list(alert["values"].items())))
        bodies.append(wire(shuffled))

    for raw in bodies:
        validate_notification(raw)  # must not raise


def test_c9_duplicate_key_body_is_legacy_valid_but_refused_here():
    body = _capture_row("notifications-paymentUnreachable.jsonl", 1)["body"]
    raw = wire(body)
    duplicated = raw.replace(b'"cascade":"otel-demo"', b'"cascade":"otel-demo","cascade":"x"', 1)
    assert duplicated != raw

    validate_notification(duplicated)  # legacy validator accepts it (last value wins)
    outcome = ji.sanitize_notification(duplicated)
    assert outcome.source is None
    assert outcome.refusal.code == "ingress_json_invalid"


# === C10: journal seam ==========================================================


@pytest.mark.skipif(
    not journal_store.no_ckpt_supported(),
    reason="needs sqlite3.Connection.setconfig and SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE (Py >= 3.12)",
)
def test_c10_journal_seam_results_sequence(tmp_path):
    directory = tmp_path / "journal"
    directory.mkdir(mode=0o700)
    journal = rj.create_recovery_journal(directory)
    try:
        inputs = [
            (FIXTURES / "notification-firing.json").read_bytes(),
            (FIXTURES / "notification-firing-repeat.json").read_bytes(),
            (FIXTURES / "notification-resolved.json").read_bytes(),
            wire(_capture_row("notifications-paymentUnreachable.jsonl", 1)["body"]),
            wire(_capture_row("notifications-paymentUnreachable.jsonl", 2)["body"]),
        ]
        results = []
        for raw in inputs:
            outcome = ji.sanitize_notification(raw)
            assert outcome.source is not None
            receipt = journal.admit(outcome.source)
            results.append(receipt.result)
        assert results == [
            "admitted", "suppressed", "pending_reduced", "admitted", "pending_reduced",
        ]
    finally:
        journal.close()
