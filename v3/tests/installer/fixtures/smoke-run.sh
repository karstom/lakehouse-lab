#!/usr/bin/env bash
# Stand-in for tests/smoke/run.sh so 'lab test' can be exercised against the stub stack.
echo "stub smoke: cwd=$(pwd) args=$*"
exit "${STUB_SMOKE_EXIT:-0}"
