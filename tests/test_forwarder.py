"""The Forwarder holds the Jira credential; a Run only ever holds a sentinel."""

import http.client
import logging
import socket
from urllib.parse import urlsplit

import pytest

from grafana_jsm_sandbox.forwarder import (
    Forwarder,
    IncompleteJiraCredential,
    JiraCredential,
)
from tests.conftest import REAL_EMAIL, REAL_TOKEN, Response, basic_auth_header, http_request

SENTINEL = "sentinel-for-this-run"


def jira_request(forwarder, path="/rest/api/3/search", sentinel=SENTINEL, **kwargs):
    """One request as jira-as makes it: basic auth whose password is the sentinel."""
    auth = None if sentinel is None else (REAL_EMAIL, sentinel)
    return http_request(forwarder.url + path, basic_auth=auth, **kwargs)


def raw_request(forwarder, target, method="GET", sentinel=SENTINEL) -> Response:
    """One request down a bare connection, which follows no redirect and rewrites no target."""
    site = urlsplit(forwarder.url)
    connection = http.client.HTTPConnection(site.hostname, site.port, timeout=5)
    headers = {} if sentinel is None else {"Authorization": basic_auth_header(REAL_EMAIL, sentinel)}
    try:
        connection.request(method, target, headers=headers)
        answer = connection.getresponse()
        return Response(answer.status, answer.read(), dict(answer.getheaders()))
    finally:
        connection.close()


def test_request_with_the_active_sentinel_reaches_upstream_with_the_real_credential(
    forwarder, upstream
):
    forwarder.set_sentinel(SENTINEL)

    response = jira_request(forwarder)

    assert response.status == 200
    assert len(upstream.received) == 1
    forwarded = upstream.received[0]
    assert forwarded.basic_auth == (REAL_EMAIL, REAL_TOKEN)
    assert SENTINEL not in forwarded.headers.get("Authorization", "")
    assert forwarded.path == "/rest/api/3/search"


def test_request_without_the_active_sentinel_is_refused_and_never_reaches_upstream(
    forwarder, upstream
):
    forwarder.set_sentinel(SENTINEL)

    response = jira_request(forwarder, sentinel="a-guess")

    assert response.status == 401
    assert upstream.received == []


def test_request_with_no_credential_at_all_is_refused_and_never_reaches_upstream(
    forwarder, upstream
):
    forwarder.set_sentinel(SENTINEL)

    response = jira_request(forwarder, sentinel=None)

    assert response.status == 401
    assert upstream.received == []


def test_sentinel_of_a_finished_run_is_refused_once_it_is_cleared(forwarder, upstream):
    forwarder.set_sentinel(SENTINEL)
    assert jira_request(forwarder).status == 200

    forwarder.clear_sentinel()

    assert jira_request(forwarder).status == 401
    assert len(upstream.received) == 1


def test_sentinel_of_a_previous_run_is_refused_once_the_next_run_replaces_it(forwarder, upstream):
    forwarder.set_sentinel("sentinel-of-the-previous-run")
    forwarder.set_sentinel(SENTINEL)

    assert jira_request(forwarder, sentinel="sentinel-of-the-previous-run").status == 401
    assert jira_request(forwarder).status == 200
    assert len(upstream.received) == 1


def test_no_request_is_forwarded_before_any_run_has_registered_a_sentinel(forwarder, upstream):
    assert jira_request(forwarder).status == 401
    assert upstream.received == []


@pytest.mark.parametrize(
    "method,body",
    [
        pytest.param("GET", None, id="get"),
        pytest.param("POST", b'{"fields": {"summary": "rolldice is silent"}}', id="post-json"),
        pytest.param("PUT", b'{"transition": {"id": "31"}}', id="put-json"),
    ],
)
def test_method_path_and_body_reach_upstream_unchanged(forwarder, upstream, method, body):
    forwarder.set_sentinel(SENTINEL)

    jira_request(
        forwarder,
        path="/rest/api/3/issue/OPS-12?expand=transitions",
        method=method,
        data=body,
        content_type="application/json" if body else None,
    )

    forwarded = upstream.received[0]
    assert forwarded.method == method
    assert forwarded.path == "/rest/api/3/issue/OPS-12?expand=transitions"
    assert forwarded.body == (body or b"")
    if body:
        assert forwarded.headers["Content-Type"] == "application/json"


def test_upstream_status_headers_and_body_pass_back_unchanged(forwarder, upstream):
    upstream.status = 201
    upstream.body = b'{"key": "OPS-12"}'
    upstream.headers = {"Content-Type": "application/json", "X-AREQUESTID": "abc123"}
    forwarder.set_sentinel(SENTINEL)

    response = jira_request(forwarder, method="POST", data=b"{}", content_type="application/json")

    assert response.status == 201
    assert response.body == b'{"key": "OPS-12"}'
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["X-AREQUESTID"] == "abc123"


def test_an_upstream_error_passes_back_rather_than_becoming_a_forwarder_error(forwarder, upstream):
    upstream.status = 404
    upstream.body = b'{"errorMessages": ["Issue does not exist"]}'
    forwarder.set_sentinel(SENTINEL)

    response = jira_request(forwarder, path="/rest/api/3/issue/OPS-999")

    assert response.status == 404
    assert response.body == b'{"errorMessages": ["Issue does not exist"]}'


def test_no_log_line_carries_the_real_token_the_sentinel_or_an_authorization_header(
    forwarder, upstream, caplog
):
    caplog.set_level(logging.DEBUG)
    forwarder.set_sentinel(SENTINEL)

    jira_request(forwarder, method="POST", data=b"{}", content_type="application/json")
    jira_request(forwarder, path="/rest/api/3/myself", sentinel="a-guess")

    assert "/rest/api/3/search" in caplog.text, "the Forwarder logged nothing to inspect"
    assert "/rest/api/3/myself" in caplog.text, "a refusal must be visible in the log"
    assert REAL_TOKEN not in caplog.text
    assert SENTINEL not in caplog.text
    assert "authorization" not in caplog.text.lower()


COMPLETE_ENVIRONMENT = {
    "JIRA_SITE_URL": "https://example.atlassian.net",
    "JIRA_EMAIL": REAL_EMAIL,
    "JIRA_API_TOKEN": REAL_TOKEN,
}


def test_credential_is_read_from_the_environment_of_the_owning_process():
    credential = JiraCredential.from_environment(COMPLETE_ENVIRONMENT)

    assert credential.site_url == "https://example.atlassian.net"
    assert credential.email == REAL_EMAIL
    assert credential.api_token == REAL_TOKEN


@pytest.mark.parametrize(
    "missing",
    [
        pytest.param(["JIRA_SITE_URL"], id="no-site-url"),
        pytest.param(["JIRA_EMAIL"], id="no-email"),
        pytest.param(["JIRA_API_TOKEN"], id="no-token"),
        pytest.param(["JIRA_EMAIL", "JIRA_API_TOKEN"], id="no-email-and-no-token"),
    ],
)
def test_startup_fails_with_a_message_naming_every_missing_variable(missing):
    environment = {
        name: value for name, value in COMPLETE_ENVIRONMENT.items() if name not in missing
    }

    with pytest.raises(IncompleteJiraCredential) as failure:
        JiraCredential.from_environment(environment)

    for name in missing:
        assert name in str(failure.value)
    for name in set(COMPLETE_ENVIRONMENT) - set(missing):
        assert name not in str(failure.value)


def test_an_empty_variable_counts_as_missing():
    with pytest.raises(IncompleteJiraCredential) as failure:
        JiraCredential.from_environment({**COMPLETE_ENVIRONMENT, "JIRA_API_TOKEN": ""})

    assert "JIRA_API_TOKEN" in str(failure.value)


def test_a_site_url_that_is_not_an_http_url_fails_at_startup():
    with pytest.raises(IncompleteJiraCredential) as failure:
        JiraCredential.from_environment(
            {**COMPLETE_ENVIRONMENT, "JIRA_SITE_URL": "example.atlassian.net"}
        )

    assert "JIRA_SITE_URL" in str(failure.value)


def test_forwarder_will_not_bind_anything_but_loopback():
    credential = JiraCredential.from_environment(COMPLETE_ENVIRONMENT)

    with pytest.raises(ValueError, match="loopback"):
        Forwarder(credential, host="0.0.0.0")


def test_forwarder_listens_on_loopback(forwarder):
    assert forwarder.url.startswith("http://127.0.0.1:")


def test_the_upstream_host_comes_from_configuration_and_never_from_the_request(forwarder, upstream):
    """A proxy-style absolute request target must not choose the Forwarder's upstream."""
    forwarder.set_sentinel(SENTINEL)

    response = raw_request(forwarder, "http://not-the-configured-site.invalid/rest/api/3/myself")

    assert response.status == 200
    assert upstream.received[0].path == "/rest/api/3/myself"


def test_a_redirect_is_handed_back_rather_than_followed_with_the_real_credential(
    forwarder, upstream
):
    upstream.status = 302
    upstream.body = b""
    upstream.headers = {"Location": "https://not-the-configured-site.invalid/"}
    forwarder.set_sentinel(SENTINEL)

    response = raw_request(forwarder, "/rest/api/3/search")

    assert response.status == 302
    assert response.headers["Location"] == "https://not-the-configured-site.invalid/"
    assert len(upstream.received) == 1


def test_an_unreachable_upstream_becomes_a_gateway_error_rather_than_a_dropped_connection():
    """A Run must get a status it can report, not a connection that closes on it."""
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        nothing_is_listening = f"http://127.0.0.1:{taken.getsockname()[1]}"

    forwarder = Forwarder(
        JiraCredential(site_url=nothing_is_listening, email=REAL_EMAIL, api_token=REAL_TOKEN)
    )
    forwarder.set_sentinel(SENTINEL)
    forwarder.start()
    try:
        response = jira_request(forwarder)
    finally:
        forwarder.stop()

    assert response.status == 502


def test_localhost_is_a_loopback_host_the_forwarder_will_bind(upstream):
    forwarder = Forwarder(
        JiraCredential(site_url=upstream.url, email=REAL_EMAIL, api_token=REAL_TOKEN),
        host="localhost",
    )

    assert forwarder.url.startswith("http://localhost:")
    forwarder.stop()


@pytest.mark.parametrize(
    "presented",
    [
        pytest.param("sentinel-with-an-accent-é", id="non-ascii"),
        pytest.param("", id="empty-password"),
        pytest.param("a password with spaces in it", id="password-with-spaces"),
    ],
)
def test_a_password_that_is_not_a_sentinel_at_all_is_refused(forwarder, upstream, presented):
    forwarder.set_sentinel(SENTINEL)

    response = jira_request(forwarder, sentinel=presented)

    assert response.status == 401
    assert upstream.received == []


def test_an_authorization_header_that_is_not_basic_auth_is_refused(forwarder, upstream):
    forwarder.set_sentinel(SENTINEL)

    response = http_request(
        forwarder.url + "/rest/api/3/myself",
        headers={"Authorization": f"Bearer {SENTINEL}"},
    )

    assert response.status == 401
    assert upstream.received == []
