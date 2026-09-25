"""The historical container and compose, checked as archived configuration.

Nothing here builds an image. These drive the three committed files — the
Dockerfile, `docker-compose.yml` and `.env.example` — against the code and the
rules they once served: the historical configuration parser, git's own ignore rules, and the redaction the log
formatter applies to anything credential-shaped.

Checks that need a running container remain archived and permanently skipped.
The former DEMO_CONTAINER live opt-in cannot enable them.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import urllib.request
from pathlib import Path

import pytest
import yaml

from grafana_jsm_sandbox.__main__ import (
    HOST_VARIABLE,
    PORT_VARIABLE,
    RUN_TIMEOUT_VARIABLE,
    RUNS_DIRECTORY_VARIABLE,
    SKILL_DIRECTORY_VARIABLE,
    Settings,
)
from grafana_jsm_sandbox.forwarder import ENVIRONMENT_VARIABLES
from grafana_jsm_sandbox.log_formatter import redact
from grafana_jsm_sandbox.run_spawner import ANTHROPIC_TOKEN_VARIABLE, TRUST_STORE_VARIABLES
from tests.conftest import REPOSITORY, compose, needs_the_stack_up

COMPOSE_FILE = REPOSITORY / "docker-compose.yml"
DOCKERFILE = REPOSITORY / "Dockerfile"
DOCKER_IGNORE = REPOSITORY / ".dockerignore"
ENV_EXAMPLE = REPOSITORY / ".env.example"
"""The four committed files that describe the container, all read as text."""

ENV_FILE = ".env"
"""What compose reads the demo's credentials from, and what git must never take."""

RUNS_PATTERN = "runs/"
"""What must stay ignored: each Run's working directory, and the Notification in it."""

DEMO_SERVICE = "demo"
"""The container the Run happens in. Grafana's contact point will name it."""

LGTM_SERVICE = "lgtm"
"""The published Grafana stack the Alert fires from."""

TRAFFIC_SERVICE = "traffic"
"""The synthetic traffic. Stopping it fires the Alert; starting it resolves it (story 55)."""

PROVISIONING = REPOSITORY / "grafana" / "provisioning" / "alerting"
"""The contact point, the notification policy and the alert rule, in this repo (story 53)."""

GRAFANA_ALERTING_PROVISIONING = "/otel-lgtm/grafana/conf/provisioning/alerting"
"""Where Grafana in the published image reads alerting provisioning from."""

GRAFANA_PORT = 3000
"""Where the presenter watches the Alert fire, on the laptop."""

RECEIVER_PORT = 8080
"""What the contact point names and what the replay script posts at by default."""

CREDENTIALS = (*ENVIRONMENT_VARIABLES.values(), ANTHROPIC_TOKEN_VARIABLE)
"""Credentials named by the historical configuration parser, never loaded on startup."""

SETTINGS_VARIABLES = (
    *CREDENTIALS,
    HOST_VARIABLE,
    PORT_VARIABLE,
    RUNS_DIRECTORY_VARIABLE,
    SKILL_DIRECTORY_VARIABLE,
    RUN_TIMEOUT_VARIABLE,
)
"""Every variable the process reads at all, which is what the example must list."""


def env_example() -> dict[str, str]:
    """The committed example read the way compose reads an env file."""
    variables = {}
    for line in ENV_EXAMPLE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, value = line.partition("=")
        variables[name.strip()] = value.strip()
    return variables


COMPOSE = yaml.safe_load(COMPOSE_FILE.read_text())
"""The committed compose file, read once."""


def service(name: str) -> dict:
    return COMPOSE["services"][name]


def published_ports(name: str) -> set[int]:
    """The laptop-side ports a service publishes.

    Compose's short form is `"host:container"`, optionally with an address in
    front. A bare `"container"` publishes nothing to the laptop and so counts for
    nothing here.
    """
    mappings = (str(mapping).split(":") for mapping in service(name).get("ports", []))
    return {int(parts[-2]) for parts in mappings if len(parts) > 1}


def git_ignores(path: str) -> bool:
    return (
        subprocess.run(["git", "check-ignore", "-q", path], cwd=REPOSITORY, check=False).returncode
        == 0
    )


def test_the_committed_example_remains_parseable_as_historical_configuration():
    """The old placeholders remain syntactically valid; launch is disabled."""
    settings = Settings.from_environment(env_example())

    assert settings.credential.site_url.startswith("https://")
    assert settings.credential.email
    assert settings.credential.api_token
    assert settings.anthropic_token


@pytest.mark.parametrize("variable", CREDENTIALS)
def test_the_example_names_every_credential_the_demo_needs(variable):
    assert variable in env_example()


@pytest.mark.parametrize("variable", SETTINGS_VARIABLES)
def test_the_example_names_every_variable_the_process_reads(variable):
    """Named, not necessarily set: the ones with a working default are commented out."""
    assert variable in ENV_EXAMPLE.read_text()


def test_the_example_carries_placeholders_rather_than_anyone_s_credential():
    """Nothing in it is credential-shaped, by the same rule that keeps the log clean."""
    for name, value in env_example().items():
        assert redact(value) == value, f"{name} looks like a real credential"


def test_git_never_takes_the_env_file_compose_reads():
    assert git_ignores(ENV_FILE)


def test_git_never_takes_a_run_s_working_directory():
    assert git_ignores(RUNS_PATTERN)


def test_the_build_context_carries_neither_the_env_file_nor_a_past_run():
    ignored = DOCKER_IGNORE.read_text().split()

    assert ENV_FILE in ignored
    assert RUNS_PATTERN in ignored


def test_the_demo_takes_its_credentials_from_the_ignored_env_file():
    demo = service(DEMO_SERVICE)

    assert ENV_FILE in _as_list(demo["env_file"])
    assert not set(demo.get("environment", {})) & set(CREDENTIALS)


def test_a_misconfigured_demo_is_not_restarted_into_a_crash_loop():
    """The Receiver refuses to start and names the missing variable. Once (story 47)."""
    assert "restart" not in service(DEMO_SERVICE)


def test_no_service_is_handed_the_docker_socket():
    for name, definition in COMPOSE["services"].items():
        for volume in definition.get("volumes", []):
            assert "docker.sock" not in str(volume), f"{name} mounts the docker socket"
        assert not definition.get("privileged"), f"{name} is privileged"


def test_grafana_and_the_receiver_answer_the_laptop():
    assert GRAFANA_PORT in published_ports(LGTM_SERVICE)
    assert RECEIVER_PORT in published_ports(DEMO_SERVICE)


def test_the_receiver_listens_where_the_published_port_leads():
    """The port compose publishes is the port the process is told to bind."""
    settings = Settings.from_environment(env_example())

    assert settings.port == RECEIVER_PORT
    assert PORT_VARIABLE not in service(DEMO_SERVICE).get("environment", {})


def test_every_service_shares_the_one_network():
    """The contact point names `demo`, traffic names `rolldice`, rolldice names `lgtm`."""
    networks = COMPOSE["networks"]
    assert len(networks) == 1

    only = next(iter(networks))
    for name, definition in COMPOSE["services"].items():
        assert _as_list(definition.get("networks", [])) == [only], f"{name} is off the network"


def test_grafana_reads_its_alerting_provisioning_from_this_repo():
    """Story 53: `grafana/docker-otel-lgtm` is a reference; this repo mounts its own files over the sample."""
    mounts = [str(volume).split(":") for volume in service(LGTM_SERVICE).get("volumes", [])]
    alerting = [parts for parts in mounts if parts[1] == GRAFANA_ALERTING_PROVISIONING]

    assert len(alerting) == 1, f"{LGTM_SERVICE} mounts {mounts}"
    source, _, *options = alerting[0]
    assert (REPOSITORY / source).resolve() == PROVISIONING
    assert options == ["ro"], "Grafana reads the files; it does not get to change them"
    assert {path.name for path in PROVISIONING.glob("*.yaml")} == {
        "contact-point.yaml",
        "notification-policy.yaml",
        "alert-rule.yaml",
    }


def test_stopped_traffic_stays_stopped():
    """The presenter's one action is `docker compose stop traffic`; nothing may undo it."""
    assert "restart" not in service(TRAFFIC_SERVICE)


def test_the_container_ends_as_a_user_who_is_not_root():
    """Read off the Dockerfile, so the default run says it even with no stack up.

    `TestAStackThatIsUp` asks the running container the same question properly.
    """
    assert run_user() != "root"


def test_the_image_is_built_holding_no_credential():
    """No credential variable is so much as named in the build, let alone given a value."""
    for line in DOCKERFILE.read_text().splitlines():
        for variable in CREDENTIALS:
            assert variable not in line, f"{variable} is named in the Dockerfile"


@needs_the_stack_up
class TestAStackThatIsUp:
    """With `docker compose up -d` already done, the two things the demo depends on."""

    def test_the_health_endpoint_answers_the_laptop(self):
        assert _get(f"http://localhost:{RECEIVER_PORT}/health") == 200

    def test_the_health_endpoint_answers_from_inside_the_network(self):
        """What Grafana's contact point will do, from the container that will do it."""
        answered = compose(
            "exec",
            "-T",
            LGTM_SERVICE,
            "curl",
            "-fsS",
            f"http://{DEMO_SERVICE}:{RECEIVER_PORT}/health",
        )

        assert answered.returncode == 0, answered.stderr

    def test_the_receiver_runs_as_a_user_who_is_not_root(self):
        who = compose("exec", "-T", DEMO_SERVICE, "id", "-u")

        assert who.stdout.strip() != "0"

    def test_a_run_would_find_the_tools_it_is_allowed_to_use(self):
        for tool in ("claude", "jira-as"):
            found = compose("exec", "-T", DEMO_SERVICE, "sh", "-c", f"command -v {tool}")
            assert found.returncode == 0, f"{tool} is not on the Run's PATH"


def _as_list(value) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


def _get(url: str) -> int:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status


# --- The image carries only what a Run needs (ticket 01 of hardened-demo-image) ---


def dockerfile_instructions(dockerfile: Path = DOCKERFILE) -> list[str]:
    """A Dockerfile's instructions, continuation lines joined and comments dropped."""
    instructions: list[str] = []
    for raw in dockerfile.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if instructions and instructions[-1].endswith("\\"):
            instructions[-1] = instructions[-1][:-1] + " " + line
        else:
            instructions.append(line)
    return instructions


def build_argument_default(name: str, dockerfile: Path = DOCKERFILE) -> str:
    """What `ARG <name>=<default>` in a Dockerfile falls back to when compose passes nothing."""
    for instruction in dockerfile_instructions(dockerfile):
        if instruction.startswith(f"ARG {name}="):
            return instruction.partition("=")[2].strip()
    raise AssertionError(f"{dockerfile.name} declares no ARG {name}")


def test_the_image_is_built_from_the_slim_official_node_image_at_a_pinned_tag():
    """A build on another laptop must produce the image that was rehearsed (story 24)."""
    base = build_argument_default("BASE_IMAGE")
    repository, _, tag = base.partition(":")

    assert repository == "node", f"the base is {base}, not the official Node image"
    assert re.fullmatch(r"\d+\.\d+\.\d+-\w+-slim", tag), f"{tag} is not a pinned slim tag"
    assert "FROM ${BASE_IMAGE}" in dockerfile_instructions(), "the build argument is not used"


ESCALATION_TOOLS = ("sudo", "docker", "docker.io", "docker-ce", "gh", "git", "curl", "jq")
"""What the old base image carried and a Run must not find (stories 9 and 14)."""

PACKAGES_A_RUN_NEEDS = {"ca-certificates", "python3", "python3-venv"}
"""Everything the distribution may add to the base image: TLS roots, and a Python to run
the Receiver and hold jira-as."""


def run_instructions(dockerfile: Path = DOCKERFILE) -> list[str]:
    return [line for line in dockerfile_instructions(dockerfile) if line.startswith("RUN ")]


def run_commands(dockerfile: Path = DOCKERFILE) -> list[list[str]]:
    """Every shell command the RUN instructions chain, each as its words."""
    return [
        command.split()
        for instruction in run_instructions(dockerfile)
        for command in re.split(r"&&|;", instruction[len("RUN ") :])
    ]


def apt_packages() -> set[str]:
    """Every package name an `apt-get install` in the Dockerfile asks for."""
    packages: set[str] = set()
    for words in run_commands():
        if words[:2] == ["apt-get", "install"]:
            packages |= {word for word in words[2:] if not word.startswith("-")}
    return packages


def run_user() -> str:
    """The account the Dockerfile's last USER names: the Receiver's, and so every Run's."""
    users = [
        line.split(maxsplit=1)[1] for line in dockerfile_instructions() if line.startswith("USER ")
    ]
    assert users, "the Dockerfile never switches user"
    return users[-1]


def useradd_arguments() -> list[str]:
    """What the Dockerfile's useradd was given for the user the container ends as."""
    for words in run_commands():
        if words[:1] == ["useradd"] and words[-1] == run_user():
            return words[1:]
    raise AssertionError(f"{run_user()} is not created by a useradd in the Dockerfile")


def test_no_line_of_the_build_installs_an_escalation_tool():
    """The default run says it with no stack up; `TestAStackThatIsUp` asks the container."""
    for instruction in run_instructions():
        words = set(re.split(r"[\s=\"']+", instruction))
        assert not words & set(ESCALATION_TOOLS), f"an escalation tool is installed: {instruction}"


def test_the_distribution_adds_nothing_but_tls_roots_and_a_python():
    assert apt_packages() <= PACKAGES_A_RUN_NEEDS, f"{apt_packages() - PACKAGES_A_RUN_NEEDS} too"


def test_claude_code_and_jira_as_are_pinned():
    """A rebuild on demo day must not ship a Transcript shape nothing has ever seen."""
    for argument in ("CLAUDE_CODE_VERSION", "JIRA_AS_VERSION"):
        assert re.fullmatch(r"\d+\.\d+\.\d+", build_argument_default(argument)), argument


def test_the_user_the_container_ends_as_was_created_by_this_dockerfile():
    """Not inherited from a base image whose groups and sudoers nobody here wrote (story 14)."""
    assert run_user() in useradd_arguments()


ENTRYPOINT = REPOSITORY / "docker" / "entrypoint.sh"
"""What the container starts: default refusal or explicit command pass-through."""

TOOLS_THE_IMAGE_CARRIES = ("sh", "mkdir", "chmod", "python3")
"""Tools historically present in the image; current entrypoint uses only sh."""

def start_container_with(tmp_path, *command: str, existing: dict | None = None) -> tuple:
    """Run the entrypoint on a bounded PATH and return its result and config path."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in TOOLS_THE_IMAGE_CARRIES:
        found = shutil.which(tool)
        assert found, f"{tool} is not on this machine"
        (bin_dir / tool).symlink_to(found)
    config_dir = tmp_path / "claude"
    if existing is not None:
        config_dir.mkdir()
        (config_dir / ".claude.json").write_text(json.dumps(existing))

    started = subprocess.run(
        ["sh", str(ENTRYPOINT), *command],
        env={"PATH": str(bin_dir), "CLAUDE_CONFIG_DIR": str(config_dir), "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    return started, config_dir / ".claude.json"


def test_default_entrypoint_refuses_without_writing_onboarding(tmp_path):
    started, onboarding = start_container_with(tmp_path)
    assert started.returncode == 1
    assert started.stdout == ""
    assert started.stderr == "legacy_launch_disabled\n"
    assert not onboarding.exists()


def test_explicit_entrypoint_command_passes_through_without_onboarding(tmp_path):
    started, onboarding = start_container_with(
        tmp_path, "sh", "-c", "echo became the command",
        existing={"numStartups": 3, "hasCompletedOnboarding": False},
    )
    assert started.returncode == 0
    assert started.stdout.strip() == "became the command"
    assert json.loads(onboarding.read_text()) == {
        "numStartups": 3, "hasCompletedOnboarding": False,
    }


def test_the_healthcheck_needs_nothing_the_image_does_not_carry():
    """Compose must report the container healthy for the right reason (story 21): the slim
    image has no curl, so the check is Python's standard library asking the health endpoint."""
    check = service(DEMO_SERVICE)["healthcheck"]["test"]

    assert check[0] == "CMD"
    assert check[1] in TOOLS_THE_IMAGE_CARRIES, f"{check[1]} is not in the image"
    assert "curl" not in " ".join(check)
    assert f"http://localhost:{RECEIVER_PORT}/health" in " ".join(check)


# The image, asked directly (opt-in, like the rest of TestAStackThatIsUp).

NODE_READS_THE_OS_TRUST_STORE = (22, 15)
"""The first Node on which Claude Code reads the operating system trust store."""


@needs_the_stack_up
class TestTheImageCarriesOnlyWhatARunNeeds:
    """With `docker compose up -d` done, the claims the default run reads off the Dockerfile."""

    @pytest.mark.parametrize("tool", ESCALATION_TOOLS)
    def test_no_escalation_tool_is_on_a_runs_path(self, tool):
        found = compose("exec", "-T", DEMO_SERVICE, "sh", "-c", f"command -v {tool}")

        assert found.returncode != 0, f"{tool} is in the container at {found.stdout.strip()}"

    def test_there_is_no_docker_group_to_be_in(self):
        group = compose("exec", "-T", DEMO_SERVICE, "getent", "group", "docker")

        assert group.returncode != 0, group.stdout

    def test_node_is_new_enough_to_read_the_os_trust_store(self):
        version = compose("exec", "-T", DEMO_SERVICE, "node", "--version").stdout.strip()

        assert (
            tuple(int(part) for part in version.lstrip("v").split("."))
            >= NODE_READS_THE_OS_TRUST_STORE
        ), version


# --- A corporate CA is trusted through the build and every Run (ticket 02) ---

ROLLDICE_DOCKERFILE = REPOSITORY / "docker" / "rolldice" / "Dockerfile"
"""The other image this repo builds. Its build reaches PyPI through the same proxy."""

BOTH_DOCKERFILES = (DOCKERFILE, ROLLDICE_DOCKERFILE)

ROLLDICE_SERVICE = "rolldice"

EXTRA_CA_ARGUMENT = "EXTRA_CA_CERT"
"""The build argument naming a PEM file in the build context; the presenter's shell sets it."""

CERTIFICATES_DIRECTORY = "certs"
"""Where the presenter puts the corporate CA. Git takes nothing from it but the placeholder."""

PLACEHOLDER = f"{CERTIFICATES_DIRECTORY}/NO_EXTRA_CERTS"
"""The committed, intentionally empty file the argument defaults to (story 8)."""

SYSTEM_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"
"""Where update-ca-certificates writes, and so where every trust-store variable points."""

INSTALLED_CERTIFICATES = "/usr/local/share/ca-certificates"
"""Where a certificate must be put for update-ca-certificates to add it to the bundle.
Empty after a build with the placeholder."""

PACKAGE_INSTALLS = ("npm install", "pip install", "opentelemetry-bootstrap")
"""Every command in either build that reaches a registry over TLS (story 16)."""


def instruction_index(dockerfile: Path, *fragments: str) -> int:
    """Where the first instruction holding every fragment is, in build order."""
    for index, instruction in enumerate(dockerfile_instructions(dockerfile)):
        if all(fragment in instruction for fragment in fragments):
            return index
    raise AssertionError(f"{dockerfile.name} has no instruction holding {fragments}")


def environment_set_by(dockerfile: Path) -> dict[str, tuple[int, str]]:
    """Every `ENV name=value` in a Dockerfile: the variable, where it is set, and its value."""
    variables: dict[str, tuple[int, str]] = {}
    for index, instruction in enumerate(dockerfile_instructions(dockerfile)):
        if instruction.startswith("ENV "):
            for pair in instruction[len("ENV ") :].split():
                name, _, value = pair.partition("=")
                variables[name] = (index, value)
    return variables


def package_install_indexes(dockerfile: Path) -> list[int]:
    return [
        index
        for index, instruction in enumerate(dockerfile_instructions(dockerfile))
        if instruction.startswith("RUN ") and any(c in instruction for c in PACKAGE_INSTALLS)
    ]


@pytest.mark.parametrize("dockerfile", BOTH_DOCKERFILES, ids=lambda path: path.parent.name)
def test_both_builds_take_a_corporate_ca_and_default_to_the_committed_placeholder(dockerfile):
    """A build with no certificate named behaves exactly as before (story 8)."""
    assert build_argument_default(EXTRA_CA_ARGUMENT, dockerfile) == PLACEHOLDER
    assert f"COPY ${{{EXTRA_CA_ARGUMENT}}} " in " ".join(dockerfile_instructions(dockerfile))


def test_the_placeholder_is_committed_and_intentionally_empty():
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", PLACEHOLDER], cwd=REPOSITORY, check=False
    )

    assert tracked.returncode == 0, f"{PLACEHOLDER} is not in git"
    assert (REPOSITORY / PLACEHOLDER).stat().st_size == 0


@pytest.mark.parametrize("dockerfile", BOTH_DOCKERFILES, ids=lambda path: path.parent.name)
def test_the_certificate_is_trusted_before_anything_reaches_npm_or_pypi(dockerfile):
    """The build itself must work behind the intercepting proxy, not only the runtime (story 16)."""
    copied = instruction_index(dockerfile, "COPY", f"${{{EXTRA_CA_ARGUMENT}}}")
    installed = instruction_index(dockerfile, "RUN", "update-ca-certificates")
    installs = package_install_indexes(dockerfile)

    assert installs, f"{dockerfile.name} installs nothing over TLS; the check reads nothing"
    assert copied < installed < min(installs), dockerfile_instructions(dockerfile)


def test_the_demo_image_points_every_tls_client_at_the_system_bundle():
    """Set once, image-wide, before the installs that need them (story 17): Python's ssl
    module and the Forwarder's urllib, jira-as's requests, pip, and Claude Code."""
    variables = environment_set_by(DOCKERFILE)

    for name in TRUST_STORE_VARIABLES:
        assert name in variables, f"{name} is not set in the Dockerfile"
        index, value = variables[name]
        assert value == SYSTEM_BUNDLE, f"{name} is {value}"
        assert index < min(package_install_indexes(DOCKERFILE)), f"{name} is set after an install"


def test_the_rolldice_build_points_pip_at_the_system_bundle():
    """Its build's only TLS clients are pip and the bootstrap that runs pip."""
    index, value = environment_set_by(ROLLDICE_DOCKERFILE)["PIP_CERT"]

    assert value == SYSTEM_BUNDLE
    assert index < min(package_install_indexes(ROLLDICE_DOCKERFILE))


@pytest.mark.parametrize("name", (DEMO_SERVICE, ROLLDICE_SERVICE))
def test_compose_hands_the_presenters_certificate_to_both_builds(name):
    """From the shell, with the placeholder as the default, so the build command is the same
    on both laptops; and from the repo root, so the same path means the same file in both."""
    build = service(name)["build"]

    assert build["args"][EXTRA_CA_ARGUMENT] == f"${{{EXTRA_CA_ARGUMENT}:-{PLACEHOLDER}}}"
    assert (REPOSITORY / build["context"]).resolve() == REPOSITORY


def test_git_never_takes_a_certificate_but_does_take_the_placeholder():
    """A corporate artifact must not end up in a public repository (story 6)."""
    assert git_ignores(f"{CERTIFICATES_DIRECTORY}/corporate-root.crt")
    assert git_ignores(f"{CERTIFICATES_DIRECTORY}/anything-else-at-all")
    assert not git_ignores(PLACEHOLDER)


def test_the_build_context_admits_the_certificate_directory():
    for pattern in DOCKER_IGNORE.read_text().split():
        assert not pattern.lstrip("/").startswith(CERTIFICATES_DIRECTORY), pattern


# The trust store, asked directly (opt-in, like the rest of TestAStackThatIsUp).

READ_THE_TRUST_STORE = f"""\
import hashlib, json, os, re, ssl
pem = re.compile(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", re.S)
def fingerprints(text):
    return sorted(hashlib.sha256(ssl.PEM_cert_to_DER_cert(c)).hexdigest() for c in pem.findall(text))
print(json.dumps({{
    "environment": {{name: os.environ.get(name) for name in {TRUST_STORE_VARIABLES!r}}},
    "bundle": fingerprints(open(os.environ["SSL_CERT_FILE"]).read()),
    "loaded": sorted(hashlib.sha256(der).hexdigest()
                     for der in ssl.create_default_context().get_ca_certs(binary_form=True)),
    "installed": sorted(os.listdir({INSTALLED_CERTIFICATES!r})),
}}))
"""
"""What the running container says about its trust store: the variables, the SHA-256
fingerprints in the bundle they name, the ones Python's default SSL context really loaded
from it, and whatever the build put where update-ca-certificates reads extras from."""


def named_certificate() -> Path | None:
    """The certificate the presenter's shell names for the build, or None for the placeholder.

    The same variable compose reads, so the check and the build cannot disagree.
    """
    named = os.environ.get(EXTRA_CA_ARGUMENT, "") or PLACEHOLDER
    return None if named == PLACEHOLDER else REPOSITORY / named


def fingerprints_of(certificate: Path) -> set[str]:
    """SHA-256 over the DER form of every certificate in a PEM file, as `openssl x509
    -fingerprint -sha256` would print them, without the colons."""
    blocks = re.findall(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
        certificate.read_text(),
        re.DOTALL,
    )
    return {hashlib.sha256(ssl.PEM_cert_to_DER_cert(block)).hexdigest() for block in blocks}


@pytest.fixture(scope="module")
def trust_store() -> dict:
    """The running container's answer, read once for the class below."""
    read = compose("exec", "-T", DEMO_SERVICE, "python3", "-c", READ_THE_TRUST_STORE)
    assert read.returncode == 0, read.stderr
    return json.loads(read.stdout)


@needs_the_stack_up
class TestTheTrustStoreOfAStackThatIsUp:
    """With `docker compose up -d` done: what the build put in the bundle, and whether the
    Python every Jira call and the healthcheck run on loads it (story 23)."""

    def test_every_tls_client_in_the_container_is_pointed_at_the_bundle(self, trust_store):
        assert trust_store["environment"] == dict.fromkeys(TRUST_STORE_VARIABLES, SYSTEM_BUNDLE)

    def test_python_loads_the_whole_bundle_the_variables_name(self, trust_store):
        assert trust_store["bundle"], "the bundle is empty"
        assert trust_store["loaded"] == trust_store["bundle"]

    def test_the_named_certificate_is_in_the_bundle_and_python_loads_it(self, trust_store):
        certificate = named_certificate()
        if certificate is None:
            pytest.skip(f"{EXTRA_CA_ARGUMENT} names no certificate; the placeholder was built")

        expected = fingerprints_of(certificate)
        assert expected, f"{certificate} holds no PEM certificate"
        assert expected <= set(trust_store["bundle"]), "the build did not install it"
        assert expected <= set(trust_store["loaded"]), "Python's default context did not load it"
        assert trust_store["installed"] == ["extra-ca.crt"]

    def test_a_build_with_the_placeholder_added_nothing(self, trust_store):
        if named_certificate() is not None:
            pytest.skip(f"{EXTRA_CA_ARGUMENT} names a certificate; it should be in the bundle")

        assert trust_store["installed"] == []


# --- The demo container runs the way Anthropic's deployment guide describes (ticket 03) ---

TEMP_DIRECTORY = "/tmp"
"""Where Claude Code keeps a Run's sockets and task files, and Python its temporary files."""

NO_NEW_PRIVILEGES = "no-new-privileges:true"
"""The security option under which no process in the container gains a privilege at exec."""

CAPABILITY_SETS = ("CapInh", "CapPrm", "CapEff", "CapBnd")
"""Four of the five masks /proc/self/status prints (the ambient set is empty whenever the
permitted set is); the bounding set is the one nothing can grow back."""

NO_CAPABILITIES = "0000000000000000"
"""An empty capability mask, as /proc/self/status prints one."""

APPLICATION_DIRECTORY = "/app"
"""The Run user's own directory in the image. Only a read-only root can refuse it a write."""


def run_user_id() -> int:
    """The uid the Dockerfile gives the account, which the tmpfs the user owns must name too."""
    arguments = useradd_arguments()
    return int(arguments[arguments.index("--uid") + 1])


def run_user_home() -> str:
    """HOME for the Receiver and, through the account, for a Run that is handed no HOME: the
    entrypoint writes the onboarding flag there, Claude Code its configuration and Transcripts."""
    arguments = useradd_arguments()
    assert "--create-home" in arguments, "the home is not made by useradd"
    assert not {"--home-dir", "-d"} & set(arguments), "the home is not useradd's default"
    return f"/home/{run_user()}"


def runs_directory() -> str:
    """The parent of every Run's working directory, as the image tells the Receiver."""
    return environment_set_by(DOCKERFILE)[RUNS_DIRECTORY_VARIABLE][1]


def scratch_directories() -> tuple[str, str, str]:
    """Everything a container writes across three Runs, as `docker diff` lists it (story 19)."""
    return (TEMP_DIRECTORY, runs_directory(), run_user_home())


def tmpfs_mounts(name: str) -> dict[str, dict[str, str]]:
    """A service's tmpfs mounts: each path, with its mount options as a dict."""
    mounts: dict[str, dict[str, str]] = {}
    for entry in _as_list(service(name).get("tmpfs", [])):
        path, _, options = str(entry).partition(":")
        mounts[path] = {}
        for option in filter(None, options.split(",")):
            key, _, value = option.partition("=")
            mounts[path][key] = value
    return mounts


def memory_in_bytes(limit) -> int:
    """A compose memory limit (`2g`, `512m`, `1024`) in bytes, binary multiples as compose reads it."""
    if isinstance(limit, int):
        return limit
    match = re.fullmatch(r"(\d+)([bkmg]?)b?", str(limit).lower())
    assert match, f"{limit!r} is not a memory limit"
    return int(match[1]) * 1024 ** "bkmg".index(match[2] or "b")


def test_the_demo_drops_every_capability():
    """The guide's first flag (story 10). The Receiver binds an unprivileged port and needs none."""
    assert _as_list(service(DEMO_SERVICE)["cap_drop"]) == ["ALL"]


def test_no_process_in_the_demo_gains_a_privilege_at_exec():
    assert NO_NEW_PRIVILEGES in _as_list(service(DEMO_SERVICE)["security_opt"])


def test_the_demo_s_root_filesystem_is_read_only():
    assert service(DEMO_SERVICE)["read_only"] is True


def test_exactly_the_three_scratch_directories_are_writable_and_none_outlives_the_container():
    """The temp directory, the runs directory and the Run user's home, on tmpfs and nowhere
    else (story 19). No volume either, so a restart starts clean."""
    assert set(tmpfs_mounts(DEMO_SERVICE)) == set(scratch_directories())
    assert "volumes" not in service(DEMO_SERVICE)


def test_the_runs_directory_and_the_home_belong_to_the_run_user():
    """A tmpfs is root's and world-writable unless told otherwise; these two are the user's own,
    with the uid the Dockerfile gave the account and the group `--user-group` made for it."""
    uid = str(run_user_id())
    for directory in (runs_directory(), run_user_home()):
        options = tmpfs_mounts(DEMO_SERVICE)[directory]
        assert options.get("uid") == uid, f"{directory} is not the user's: {options}"
        assert options.get("gid") == uid, f"{directory} is not the user's group's: {options}"
        assert options.get("mode") == "0700", f"{directory} is not private: {options}"


def test_every_scratch_directory_is_sized():
    """A tmpfs is memory; unsized, each may grow to half the machine's (story 20)."""
    for directory, options in tmpfs_mounts(DEMO_SERVICE).items():
        assert re.fullmatch(r"\d+[kmg]", options.get("size", "")), f"{directory} is unsized"


PEAK_TASKS_IN_A_LIFECYCLE = 24
"""The most tasks (processes and threads) the container's cgroup held at any sample across the
three Runs of the end-to-end check, run under the limits and sampled every 0.7s (ticket 03)."""

PEAK_MEMORY_IN_A_LIFECYCLE = 227 * 1024**2
"""The cgroup's peak memory across the same three Runs, as the kernel reported it."""


def test_a_runaway_run_is_bounded_in_processes_memory_and_cpu():
    """Sized for three Runs in a row on a laptop (story 20): the process and memory limits have
    headroom over the measured peak, the CPU limit is a share of the laptop rather than a peak,
    and `TestTheBoundaryOfAStackThatIsUp` reads what the kernel then enforces."""
    demo = service(DEMO_SERVICE)

    assert isinstance(demo["pids_limit"], int)
    assert demo["pids_limit"] >= 4 * PEAK_TASKS_IN_A_LIFECYCLE
    assert memory_in_bytes(demo["mem_limit"]) >= 4 * PEAK_MEMORY_IN_A_LIFECYCLE
    assert float(demo["cpus"]) > 0


# The kernel, asked directly (opt-in, like the rest of TestAStackThatIsUp).

PROBED_DIRECTORIES = (APPLICATION_DIRECTORY, *scratch_directories())
"""One the user owns on the root filesystem, and the three scratch directories."""

ASK_THE_KERNEL = f"""\
import json, os
def probe(directory):
    path = os.path.join(directory, "write-probe-%d" % os.getpid())
    try:
        open(path, "w").close()
        os.remove(path)
        return "accepted"
    except OSError as error:
        return error.strerror
def first(*paths):
    for path in paths:
        try:
            return open(path).read().strip()
        except OSError:
            continue
status = {{}}
for line in open("/proc/self/status"):
    name, separator, value = line.partition(":")
    if separator:
        status[name] = value.strip()
quota = first("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
period = first("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
print(json.dumps({{
    "capabilities": {{name: status[name] for name in {CAPABILITY_SETS!r}}},
    "no_new_privs": status.get("NoNewPrivs"),
    "writes": {{directory: probe(directory) for directory in {PROBED_DIRECTORIES!r}}},
    "pids_max": first("/sys/fs/cgroup/pids.max", "/sys/fs/cgroup/pids/pids.max"),
    "memory_max": first("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    "cpu_max": first("/sys/fs/cgroup/cpu.max") or (quota and period and quota + " " + period),
}}))
"""
"""What the running container's kernel says: the process's four capability masks, whether it can gain a privilege at exec, which directories accept a write, and the process,
memory and CPU limits its cgroup enforces (cgroup v2 first, v1 where that is what there is)."""

UNLIMITED = "max"
"""What cgroup v2 prints for a limit that is not set; v1 prints -1 or a number near 2**63."""


def enforced_processes(kernel: dict) -> int | None:
    """The cgroup's process limit, or None where there is none."""
    value = kernel["pids_max"]
    return None if value in (None, UNLIMITED) else int(value)


def enforced_memory(kernel: dict) -> int | None:
    """The cgroup's memory limit in bytes, or None where there is none."""
    value = kernel["memory_max"]
    return None if value in (None, UNLIMITED) or int(value) >= 2**62 else int(value)


def enforced_cpus(kernel: dict) -> float | None:
    """The cgroup's CPU limit as a count of CPUs, or None where there is none."""
    if not kernel["cpu_max"]:
        return None
    quota, period = kernel["cpu_max"].split()
    return None if quota == UNLIMITED or int(quota) < 0 else int(quota) / int(period)


def not_applied(control: str, enforced) -> str:
    """Why a declared limit is not the enforced one: this Compose is too old to have applied it.

    Compose 2.2 is the first to apply `pids_limit` and 2.17 the first to apply `cpus`; a
    current Docker Desktop applies both. Until then the runbook's pre-demo check names the
    `docker update` that applies them to the running container.
    """
    version = compose("version", "--short").stdout.strip()
    return f"{control} is declared but the kernel enforces {enforced!r}: Compose {version} did not apply it"


@pytest.fixture(scope="module")
def kernel() -> dict:
    """The running container's kernel's answer, read once for the class below."""
    asked = compose("exec", "-T", DEMO_SERVICE, "python3", "-c", ASK_THE_KERNEL)
    assert asked.returncode == 0, asked.stderr
    return json.loads(asked.stdout)


@needs_the_stack_up
class TestTheBoundaryOfAStackThatIsUp:
    """With `docker compose up -d` done: the controls the default run reads off the compose
    file, as the kernel of the machine giving the demo actually enforces them (story 23)."""

    def test_the_root_filesystem_refuses_a_write_even_where_the_user_owns_it(self, kernel):
        """/app is the Run user's own; only a read-only root can refuse it a write there."""
        assert kernel["writes"][APPLICATION_DIRECTORY] == "Read-only file system"

    @pytest.mark.parametrize("directory", scratch_directories())
    def test_each_scratch_directory_accepts_a_write(self, kernel, directory):
        assert kernel["writes"][directory] == "accepted"

    def test_no_capability_is_left_not_even_in_the_bounding_set(self, kernel):
        assert kernel["capabilities"] == dict.fromkeys(CAPABILITY_SETS, NO_CAPABILITIES)

    def test_no_process_can_gain_a_privilege_at_exec(self, kernel):
        assert kernel["no_new_privs"] == "1"

    def test_the_process_limit_is_the_one_compose_declares(self, kernel):
        declared = service(DEMO_SERVICE)["pids_limit"]

        assert enforced_processes(kernel) == declared, not_applied("pids_limit", kernel["pids_max"])

    def test_the_memory_limit_is_the_one_compose_declares(self, kernel):
        declared = memory_in_bytes(service(DEMO_SERVICE)["mem_limit"])

        assert enforced_memory(kernel) == declared, not_applied("mem_limit", kernel["memory_max"])

    def test_the_cpu_limit_is_the_one_compose_declares(self, kernel):
        declared = float(service(DEMO_SERVICE)["cpus"])

        assert enforced_cpus(kernel) == declared, not_applied("cpus", kernel["cpu_max"])
