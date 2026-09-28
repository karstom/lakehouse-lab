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

Quiet hours for the local provider (Phase 6; `./lab ai quiet-hours HH:MM-HH:MM --tz Area/City`):
  LAB_AI_QUIET_HOURS  "HH:MM-HH:MM" (start inclusive, end exclusive; a start later than the
                      end crosses midnight, e.g. 22:00-07:00); empty or "off" = no quiet hours
  LAB_AI_QUIET_TZ     IANA time zone of that window (default: TZ, else UTC)
The window is written to state.json with the model names that reach the local provider
(`local`, and `lab-default` when it resolves to local). During the window the lab_hooks
pre-call hook refuses those models BEFORE routing, with `quiet_hours_message`; hosted models
and the mock are not affected. Times are wall-clock times in the zone, so the window follows
DST changes (a start or end that does not exist on a spring-forward day is simply reached at
the first wall-clock minute past it; on a fall-back day a window over the repeated hour lasts
an hour longer in real time).

Keys never appear in the rendered file: LiteLLM reads them through `os.environ/NAME`.
The YAML is written as JSON (JSON is YAML), so no YAML library is needed.
"""
import datetime
import json
import os
import re
import sys
import zoneinfo

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_MOCK_URL = "http://ai-mock:8000/v1"
PROVIDER_ORDER = ("mock", "local", "anthropic", "openai")
ALIAS = {"mock": "mock", "local": "local", "anthropic": "claude", "openai": "gpt"}
NOT_CONFIGURED = "AI isn't configured; ask your lab admin."
QUIET_RE = re.compile(r"^([01][0-9]|2[0-3]):([0-5][0-9])-([01][0-9]|2[0-3]):([0-5][0-9])$")
QUIET_TYPE = "ai_quiet_hours"


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


# ------------------------------------------------------------------ quiet hours (Phase 6)
def parse_quiet_hours(spec):
    """"HH:MM-HH:MM" -> (start minute, end minute) of the day; "" / "off" -> None.
    Raises ValueError for anything else, including an empty window (start == end)."""
    spec = (spec or "").strip()
    if spec.lower() in ("", "off", "none"):
        return None
    m = QUIET_RE.match(spec)
    if not m:
        raise ValueError(f"quiet hours {spec!r}: use HH:MM-HH:MM (24-hour clock), e.g. 22:00-07:00")
    start = int(m.group(1)) * 60 + int(m.group(2))
    end = int(m.group(3)) * 60 + int(m.group(4))
    if start == end:
        raise ValueError(f"quiet hours {spec!r}: start and end are the same; use 'off' for none")
    return start, end


def quiet_zone(name):
    """IANA zone name -> ZoneInfo. Raises ValueError for an unknown or malformed name."""
    name = (name or "").strip()
    if name.startswith(":"):
        name = name[1:]
    if not name or name.startswith("/") or ".." in name:
        raise ValueError(f"time zone {name!r}: use an IANA name such as America/New_York")
    try:
        return zoneinfo.ZoneInfo(name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError, OSError):
        raise ValueError(f"time zone {name!r} is unknown: use an IANA name such as America/New_York")


def quiet_until(now, window, tz):
    """When the quiet window that `now` falls in ends, as an aware datetime in `tz`, or None
    when `now` is outside the window. `now` is any aware datetime (injected: tests use a fixed
    clock), `window` is parse_quiet_hours' (start, end) and `tz` a tzinfo. Wall-clock
    comparison in `tz`: minute granularity, start inclusive, end exclusive."""
    if window is None:
        return None
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    start, end = window
    local = now.astimezone(tz)
    minute = local.hour * 60 + local.minute
    if start < end:
        if not start <= minute < end:
            return None
        day = local.date()
    else:                              # crosses midnight, e.g. 22:00-07:00
        if minute >= start:
            day = local.date() + datetime.timedelta(days=1)
        elif minute < end:
            day = local.date()
        else:
            return None
    return datetime.datetime.combine(day, datetime.time(end // 60, end % 60), tzinfo=tz)


def quiet_hours_message(until, spec, tz_name):
    return (f"The lab's local AI model is resting until {until.strftime('%H:%M')} {tz_name} "
            f"(quiet hours {spec}). Please try again after that; your lab admin can change "
            "this with './lab ai quiet-hours'.")


def quiet_hours_state(env):
    """-> {"window": "HH:MM-HH:MM", "tz": name} or None. Raises SystemExit on a bad setting
    (the gateway then does not start, so it cannot route to the local model by mistake)."""
    spec = (env.get("LAB_AI_QUIET_HOURS") or "").strip()
    try:
        window = parse_quiet_hours(spec)
        if window is None:
            return None
        tz_name = ((env.get("LAB_AI_QUIET_TZ") or "").strip() or (env.get("TZ") or "").strip()
                   or "UTC").lstrip(":")
        quiet_zone(tz_name)
    except ValueError as e:
        raise SystemExit(f"[ai-gateway] LAB_AI_QUIET_HOURS/LAB_AI_QUIET_TZ: {e}")
    return {"window": spec, "tz": tz_name}


def quiet_refusal(state, model, now):
    """The pre-call decision (lab_hooks): -> (message, seconds until the end) when `model`
    would reach the local provider during quiet hours, else None. Pure: `now` is injected."""
    qh = (state or {}).get("quiet_hours")
    if not qh or model not in ((state or {}).get("local_models") or []):
        return None
    tz = quiet_zone(qh["tz"])
    until = quiet_until(now, parse_quiet_hours(qh["window"]), tz)
    if until is None:
        return None
    # In UTC: subtracting two datetimes that share a tzinfo would ignore a DST change between.
    utc = datetime.timezone.utc
    seconds = max(1, int((until.astimezone(utc) - now.astimezone(utc)).total_seconds()))
    return quiet_hours_message(until, qh["window"], qh["tz"]), seconds


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
    quiet = quiet_hours_state(env)
    state = {"configured": bool(deps), "default_provider": default,
             "providers": [p for p in PROVIDER_ORDER if p in deps],
             "models": [m["model_name"] for m in model_list],
             "not_configured_message": NOT_CONFIGURED,
             # Model names that reach the local provider (quiet hours apply to these only).
             "local_models": [m["model_name"] for m in model_list
                              if m["model_info"]["lab_provider"] == "local"],
             "quiet_hours": quiet}
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
    if state["quiet_hours"]:
        qh = state["quiet_hours"]
        print(f"[ai-gateway] local model quiet hours: {qh['window']} {qh['tz']} (models refused "
              f"then: {', '.join(state['local_models']) or 'none now'})", flush=True)


if __name__ == "__main__":
    main(sys.argv)
