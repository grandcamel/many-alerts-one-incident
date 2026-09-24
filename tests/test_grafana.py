"""Archived Grafana stack checks; skipped with the retired demo launcher.

The contact point, the notification policy and the alert rule are files under
`grafana/provisioning/alerting`, mounted into the LGTM container. A typo there
makes Grafana skip the file and say so only in its own log, so nothing here
reads the files back: every check asks the running Grafana what it actually
took, through the same API the provisioning UI uses, and the last checks ask it
to run the rule's own query against the Prometheus it is wired to. All of it
needs the old stack up. The former `DEMO_CONTAINER` flag cannot enable these
checks after the executable was retired under ADRs 0011–0013.

The canned fixtures stand in for Grafana when it is uncooperative, so the last
check holds them to the Alert Grafana is provisioned to send: same receiver,
same rule title, same labels.
"""

from __future__ import annotations

import functools
import json
from urllib.parse import urlencode

import pytest

from grafana_jsm_sandbox.replay import laptop_url
from tests.conftest import compose, firing_notification, http_request, needs_the_stack_up

GRAFANA_HOST_PORT_VARIABLE = "GRAFANA_HOST_PORT"
"""What moves Grafana off a taken 3000 on the laptop; its port in the container stays 3000."""

RECEIVER_ON_THE_NETWORK = "http://demo:8080/notification"
"""The Receiver as Grafana must name it: by compose service name, not localhost."""

EVALUATION_INTERVAL = 10
"""Seconds between evaluations of the rule (story 54)."""

PENDING_PERIOD = "30s"
"""How long the rate must be zero before the Alert is Firing."""

REPEAT_INTERVAL = "1m"
"""How often a Firing Alert is sent again. Grafana's default is four hours."""

LONGEST_GROUP_WAIT = 30
"""Seconds. The first Notification must not wait longer than this behind group_wait."""

FIELD_MAPPING_LABELS = {"severity", "service"}
"""The rule labels the skill's field mapping reads (story 54)."""

TRAFFIC_SERVICE = "traffic"
"""The compose service whose absence fires the Alert."""

pytestmark = needs_the_stack_up


@pytest.fixture(scope="module")
def contact_point() -> dict:
    """The one contact point Grafana was provisioned with."""
    provisioned = [
        point for point in grafana("/api/v1/provisioning/contact-points") if point["uid"]
    ]
    assert len(provisioned) == 1, f"expected one provisioned contact point, got {provisioned}"
    return provisioned[0]


@pytest.fixture(scope="module")
def policy() -> dict:
    return grafana("/api/v1/provisioning/policies")


@pytest.fixture(scope="module")
def rule() -> dict:
    rules = grafana("/api/v1/provisioning/alert-rules")
    assert len(rules) == 1, f"expected one alert rule, got {[rule['title'] for rule in rules]}"
    return rules[0]


def test_the_contact_point_is_a_webhook_aimed_at_the_receiver(contact_point):
    assert contact_point["type"] == "webhook"
    assert contact_point["settings"]["url"] == RECEIVER_ON_THE_NETWORK
    assert not contact_point["disableResolveMessage"], "a Resolved must reach the Receiver too"


def test_every_alert_is_routed_to_that_contact_point(contact_point, policy):
    assert policy["receiver"] == contact_point["name"]
    assert not policy.get("routes"), "one route: everything goes to the Receiver"


def test_a_firing_alert_is_sent_again_every_minute_not_every_four_hours(policy):
    assert policy["repeat_interval"] == REPEAT_INTERVAL
    assert seconds(policy["group_wait"]) <= LONGEST_GROUP_WAIT


def test_the_rule_evaluates_every_ten_seconds_and_fires_after_thirty(rule):
    group = grafana(
        f"/api/v1/provisioning/folder/{rule['folderUID']}/rule-groups/{rule['ruleGroup']}"
    )

    assert group["interval"] == EVALUATION_INTERVAL
    assert rule["for"] == PENDING_PERIOD


def test_the_rule_labels_what_the_field_mapping_reads(rule):
    assert set(rule["labels"]) >= FIELD_MAPPING_LABELS
    assert rule["labels"]["service"] == "rolldice"


def test_the_rule_watches_a_metric_rolldice_really_exports(rule):
    """The rule's own query, run against the Prometheus the rule reads (story 55).

    An expression naming a metric the auto-instrumentation does not export
    returns nothing, evaluates to NoData, and never fires on the day.
    """
    query = next(query for query in rule["data"] if query["datasourceUid"] == "prometheus")
    answer = grafana(
        "/api/datasources/proxy/uid/prometheus/api/v1/query",
        data={"query": query["model"]["expr"]},
    )

    assert answer["data"]["result"], f"{query['model']['expr']!r} matches no series"


def test_the_rule_is_normal_while_traffic_flows(rule):
    assert compose_running(TRAFFIC_SERVICE), f"start {TRAFFIC_SERVICE} first"

    groups = grafana("/api/prometheus/grafana/api/v1/rules")["data"]["groups"]
    states = [
        provisioned["state"]
        for group in groups
        for provisioned in group["rules"]
        if provisioned["uid"] == rule["uid"]
    ]

    assert states == ["inactive"], f"the rule is {states}, not Normal"


def test_the_fixtures_describe_the_alert_grafana_is_provisioned_to_send(contact_point, rule):
    """The canned sequence must be the same Alert, or the fallback tells a different story."""
    notification = firing_notification()
    alert = notification["alerts"][0]

    assert notification["receiver"] == contact_point["name"]
    assert alert["labels"]["alertname"] == rule["title"]
    assert {label: alert["labels"][label] for label in rule["labels"]} == rule["labels"]


def grafana(path: str, data: dict[str, str] | None = None) -> dict | list:
    """One request at Grafana's API, JSON in and out. A POST when `data` is given."""
    if data is None:
        answer = http_request(grafana_url() + path)
    else:
        answer = http_request(
            grafana_url() + path,
            method="POST",
            data=urlencode(data).encode(),
            content_type="application/x-www-form-urlencoded",
        )
    assert answer.status == 200, f"{path} answered {answer.status}: {answer.body[:200]!r}"
    return json.loads(answer.body)


@functools.cache
def grafana_url() -> str:
    """Grafana on the laptop, where compose publishes it: anonymous admin, no login form.

    Worked out on first use rather than at import, because it reads `.env`: every
    suite collects this module, and a skipped check must never open that file, nor
    fail collection over a line in it.
    """
    return laptop_url(GRAFANA_HOST_PORT_VARIABLE, 3000)


def seconds(duration: str) -> int:
    """A Grafana duration such as `10s` or `1m`, in seconds."""
    units = {"s": 1, "m": 60, "h": 3600}
    return int(duration[:-1]) * units[duration[-1]]


def compose_running(service_name: str) -> bool:
    return service_name in compose("ps", "--services", "--filter", "status=running").stdout.split()
