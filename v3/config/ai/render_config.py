"""Render the ai-gateway's LiteLLM config from the environment (stdlib only; unit-tested in
tests/ai/test_render_config.py).

    python3 render_config.py OUT_DIR      -> OUT_DIR/config.yaml, OUT_DIR/state.json

Providers (CONTRACT Phase 5). A provider exists in the config ONLY when the admin enabled it;
with none enabled the model list is empty, so the gateway has nowhere to send a request and
makes no outbound AI call (the lab_hooks pre-call hook answers "AI isn't configured").

  local      LAB_AI_LOCAL_URL (.env; `./lab ai set-local`, installer --ai-local-url): any
             OpenAI-compatible server (llama.cpp llama-server, Ollama, vLLM).
             LAB_AI_LOCAL_MODEL (the id the server expects; default "local"),
             LAB_AI_LOCAL_API_KEY (optional, .secrets.env).
  anthropic  LAB_AI_ANTHROPIC_API_KEY (.secrets.env; `./lab ai enable-hosted`),
             LAB_AI_ANTHROPIC_MODEL (default below).
  openai     LAB_AI_OPENAI_API_KEY (.secrets.env; `./lab ai enable-hosted`),
             LAB_AI_OPENAI_MODEL (default below).
  mock       LAB_AI_MOCK=true (tests only; installer --ai-mock): tests/ai/mock_llm at
             LAB_AI_MOCK_URL.

Model names clients use (model_name in LiteLLM):
  lab-default  the lab's default provider: LAB_AI_DEFAULT_PROVIDER if set and enabled,
               else the first enabled of mock, local, anthropic, openai (mock first: it is
               only ever on in test installs; local before hosted: private data stays local).
  local, claude, gpt, mock
               each enabled provider under its own name.

Costs: hosted models use LiteLLM's bundled price map. `local` costs
LAB_AI_LOCAL_COST_PER_MTOK USD per million tokens (default 0: free, so only the rate limit
applies) and `mock` LAB_AI_MOCK_COST_PER_MTOK (default 1000, so budget tests overrun fast).

Keys never appear in the rendered file: LiteLLM reads them through `os.environ/NAME`.
The YAML is written as JSON (JSON is YAML), so no YAML library is needed.
"""
import json
import os
import sys

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_MOCK_URL = "http://ai-mock:8000/v1"
PROVIDER_ORDER = ("mock", "local", "anthropic", "openai")
ALIAS = {"mock": "mock", "local": "local", "anthropic": "claude", "openai": "gpt"}
NOT_CONFIGURED = "AI isn't configured; ask your lab admin."


def _truthy(v):
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def _cost(env, name, default):
    raw = (env.get(name) or "").strip()
    try:
        v = float(raw) if raw else float(default)
    except ValueError:
        raise SystemExit(f"[ai-gateway] {name}={raw!r} is not a number")
    if v < 0:
        raise SystemExit(f"[ai-gateway] {name} must be >= 0")
    return v / 1_000_000.0


def _url(env, name):
    u = (env.get(name) or "").strip().rstrip("/")
    if u and not (u.startswith("http://") or u.startswith("https://")):
        raise SystemExit(f"[ai-gateway] {name} must be an http(s) URL")
    return u


def deployments(env):
    """provider -> litellm_params (without secrets), for every enabled provider."""
    out = {}
    if _truthy(env.get("LAB_AI_MOCK")):
        c = _cost(env, "LAB_AI_MOCK_COST_PER_MTOK", 1000)
        out["mock"] = {"model": "openai/mock-model",
                       "api_base": _url(env, "LAB_AI_MOCK_URL") or DEFAULT_MOCK_URL,
                       "api_key": "none",
                       "input_cost_per_token": c, "output_cost_per_token": c}
    local = _url(env, "LAB_AI_LOCAL_URL")
    if local:
        c = _cost(env, "LAB_AI_LOCAL_COST_PER_MTOK", 0)
        out["local"] = {"model": "openai/" + ((env.get("LAB_AI_LOCAL_MODEL") or "").strip() or "local"),
                        "api_base": local,
                        "api_key": ("os.environ/LAB_AI_LOCAL_API_KEY"
                                    if (env.get("LAB_AI_LOCAL_API_KEY") or "").strip() else "none"),
                        "input_cost_per_token": c, "output_cost_per_token": c}
    if (env.get("LAB_AI_ANTHROPIC_API_KEY") or "").strip():
        out["anthropic"] = {"model": "anthropic/" + ((env.get("LAB_AI_ANTHROPIC_MODEL") or "").strip()
                                                     or DEFAULT_ANTHROPIC_MODEL),
                            "api_key": "os.environ/LAB_AI_ANTHROPIC_API_KEY"}
    if (env.get("LAB_AI_OPENAI_API_KEY") or "").strip():
        out["openai"] = {"model": "openai/" + ((env.get("LAB_AI_OPENAI_MODEL") or "").strip()
                                               or DEFAULT_OPENAI_MODEL),
                         "api_key": "os.environ/LAB_AI_OPENAI_API_KEY"}
    return out


def default_provider(env, deps):
    want = (env.get("LAB_AI_DEFAULT_PROVIDER") or "").strip().lower()
    if want:
        if want not in PROVIDER_ORDER:
            raise SystemExit(f"[ai-gateway] LAB_AI_DEFAULT_PROVIDER={want!r}: use one of {', '.join(PROVIDER_ORDER)}")
        if want in deps:
            return want
        print(f"[ai-gateway] LAB_AI_DEFAULT_PROVIDER={want} is not enabled; using the first enabled one",
              file=sys.stderr)
    return next((p for p in PROVIDER_ORDER if p in deps), None)


def render(env):
    deps = deployments(env)
    default = default_provider(env, deps)
    timeout = int((env.get("LAB_AI_REQUEST_TIMEOUT") or "").strip() or 600)
    model_list = []
    if default:
        model_list.append({"model_name": "lab-default", "litellm_params": dict(deps[default], timeout=timeout),
                           "model_info": {"id": "lab-default", "lab_provider": default}})
    for p in PROVIDER_ORDER:
        if p in deps:
            model_list.append({"model_name": ALIAS[p], "litellm_params": dict(deps[p], timeout=timeout),
                               "model_info": {"id": ALIAS[p], "lab_provider": p}})
    config = {
        "model_list": model_list,
        "litellm_settings": {
            "telemetry": False,
            # Local servers reject OpenAI-only parameters; drop what a provider does not take.
            "drop_params": True,
            # Prompts and responses are not passed to logging callbacks (there are none).
            "turn_off_message_logging": True,
            "request_timeout": timeout,
            # Never resend a request by itself: a retry to a local GPU server is another full
            # inference, and a retry to a hosted provider costs money.
            "num_retries": 0,
            # Anthropic-format requests (/v1/messages, e.g. Claude Code) to an OpenAI-compatible
            # backend go through /chat/completions, which every local server implements (the
            # default, the Responses API, is not served by llama-server/Ollama/vLLM alike).
            "use_chat_completions_url_for_anthropic_messages": True,
            "callbacks": ["lab_hooks.proxy_handler_instance"],
        },
        "router_settings": {"num_retries": 0},
        "general_settings": {
            "master_key": "os.environ/LITELLM_MASTER_KEY",
            "database_url": "os.environ/DATABASE_URL",
            # Models come only from this file (the admin's settings), never from the DB/UI.
            "store_model_in_db": False,
            # No periodic calls to the providers (the lab never sends a request by itself).
            "background_health_checks": False,
            # Refuse requests when the DB is down instead of skipping budget checks.
            "allow_requests_on_db_unavailable": False,
            # Prompts and responses are not stored with the spend logs (metadata only).
            "store_prompts_in_spend_logs": False,
        },
    }
    state = {"configured": bool(deps), "default_provider": default,
             "providers": [p for p in PROVIDER_ORDER if p in deps],
             "models": [m["model_name"] for m in model_list],
             "not_configured_message": NOT_CONFIGURED}
    return config, state


def main(argv):
    if len(argv) != 2:
        raise SystemExit("usage: render_config.py OUT_DIR")
    out = argv[1]
    config, state = render(os.environ)
    with open(os.path.join(out, "config.yaml"), "w") as f:
        json.dump(config, f, indent=2, sort_keys=True)
    with open(os.path.join(out, "state.json"), "w") as f:
        json.dump(state, f, sort_keys=True)
    if state["configured"]:
        print(f"[ai-gateway] providers: {', '.join(state['providers'])}; lab-default -> "
              f"{state['default_provider']}; models: {', '.join(state['models'])}", flush=True)
    else:
        print("[ai-gateway] no AI provider enabled: the model list is empty and the gateway makes "
              "no outbound AI calls (enable one with ./lab ai set-local or ./lab ai enable-hosted)",
              flush=True)


if __name__ == "__main__":
    main(sys.argv)
