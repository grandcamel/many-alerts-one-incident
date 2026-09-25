# ARCHIVAL chapter-one image. Its default entrypoint now refuses before
# onboarding, credential parsing, Receiver startup or Run launch. The comments
# below describe the former demo image, not a current ADR 0011-0013 runtime.
#
# The image carries what a Run needs and nothing else (ADR 0005): the slim official
# Node image plus the distribution's Python, Claude Code and jira-as at pinned
# versions, this package and the Skill, run by a non-root user created here. No
# sudo, no docker CLI or group, no gh, no git, no curl, no jq, no developer kit.
# The answer to "what else can a Run reach for" is `ls /usr/local/bin`.
#
# No bubblewrap, no sandbox package, no Docker socket. The boundary a Run runs
# inside is the container itself, the permission mode it is started with (ADR
# 0003) and the sentinel in its environment (ADR 0002), not anything installed here.
#
#     docker compose build
#     EXTRA_CA_CERT=certs/corporate-root.crt docker compose build    # behind a proxy
#
# The base is pinned to the tag the demo was rehearsed on. Node 22.15 or newer is
# required: that is the runtime from which Claude Code reads the operating system
# trust store, which the work laptop behind an intercepting proxy depends on.

ARG BASE_IMAGE=node:24.21.0-trixie-slim
FROM ${BASE_IMAGE}

ARG CLAUDE_CODE_VERSION=2.1.272
ARG JIRA_AS_VERSION=2.0.0

# One user, made here. The base image's `node` account goes, along with yarn,
# corepack and the base's own entrypoint, so that the only account and the only
# executables in the image are the ones this file put there.
RUN userdel -r node \
    && useradd --uid 1000 --user-group --create-home --shell /bin/bash demo \
    && rm -rf /opt/yarn* /usr/local/bin/yarn /usr/local/bin/yarnpkg \
        /usr/local/bin/corepack /usr/local/bin/docker-entrypoint.sh

# TLS roots, and a Python: the Receiver is standard library only, and jira-as is
# a Python CLI. python3-venv is what lets jira-as live in its own environment
# rather than in the distribution's site-packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

# An optional corporate CA, for a laptop behind an intercepting proxy such as
# Zscaler (ticket 02). The argument names a PEM file in the build context; the
# default is a committed placeholder that is intentionally empty, and with it the
# build is exactly the one above. A named certificate goes into the system trust
# store here, before anything below reaches npm or PyPI through that proxy, and a
# file that is not PEM stops the build now rather than as a TLS error three
# layers down.
ARG EXTRA_CA_CERT=certs/NO_EXTRA_CERTS
COPY ${EXTRA_CA_CERT} /tmp/extra-ca.crt
RUN if [ -s /tmp/extra-ca.crt ]; then \
        grep -q "BEGIN CERTIFICATE" /tmp/extra-ca.crt \
            || { echo "EXTRA_CA_CERT is not a PEM certificate" >&2; exit 1; }; \
        install -m 644 /tmp/extra-ca.crt /usr/local/share/ca-certificates/extra-ca.crt \
        && update-ca-certificates; \
    fi \
    && rm -f /tmp/extra-ca.crt

# Historical image-wide TLS bundle for installed clients. The former Receiver
# handed these five settings to each Run (ADR 0002); the disabled entrypoint
# now starts no Receiver or Run.
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

# The historical Transcript renderer was rehearsed with this pinned Claude
# Code version. The image still carries it for archival inspection; the
# disabled default entrypoint does not start it.
RUN npm install -g --allow-scripts="@anthropic-ai/claude-code" \
        "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm cache clean --force

# The historical Run's pinned jira-as. Its own venv kept dependencies out of
# the Receiver interpreter; this installed command is not current Run authority.
RUN python3 -m venv /opt/jira-as \
    && /opt/jira-as/bin/pip install --no-cache-dir "jira-as==${JIRA_AS_VERSION}" \
    && ln -s /opt/jira-as/bin/jira-as /usr/local/bin/jira-as

# /app was the Receiver's home and Run working-directory parent. Retain its
# historical ownership without enabling the retired entrypoint.
RUN mkdir -p /app/runs && chown -R demo:demo /app

WORKDIR /app
COPY --chown=demo:demo grafana_jsm_sandbox/ /app/grafana_jsm_sandbox/
COPY --chown=demo:demo skill/ /app/skill/
COPY --chown=demo:demo docker/entrypoint.sh /app/entrypoint.sh

# Historical Receiver directory settings. Credentials remain outside the
# image; the default entrypoint refuses before reading them.
ENV SKILL_DIRECTORY=/app/skill \
    RUNS_DIRECTORY=/app/runs \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER demo

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
