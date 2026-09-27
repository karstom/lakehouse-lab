#!/bin/sh
# ai-gateway entrypoint: render the LiteLLM config from the environment (providers enabled by
# the admin, see render_config.py), then run the proxy. Everything the proxy reads is written
# fresh on each start into /tmp/lab-ai, so a changed provider setting only needs a recreate.
set -eu
run=/tmp/lab-ai
mkdir -p "$run"
cp /opt/lab/ai/lab_hooks.py "$run/lab_hooks.py"
python3 /opt/lab/ai/render_config.py "$run"
# One worker: the budget/rate-limit counters live in this process (no Redis in the lab).
exec litellm --config "$run/config.yaml" --host 0.0.0.0 --port 4000 --num_workers 1
