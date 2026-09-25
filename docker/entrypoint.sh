#!/bin/sh
# The historical demo image no longer starts a credentialed Receiver or
# writes Claude onboarding state by default. An explicitly supplied command
# remains available for local inspection; it receives no startup mutation.
set -eu

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

printf '%s\n' 'legacy_launch_disabled' >&2
exit 1
