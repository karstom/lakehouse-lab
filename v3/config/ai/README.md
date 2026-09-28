# AI gateway (Phase 5, GATEWAY)

The lab's model gateway: one place that holds provider keys and per-user budgets, so users
and workspaces never see a provider key (ADR-014, OQ-7, OQ-8). Profile `full` only.

```
workspace (user's virtual key) ──lab──> ai-frontdoor:4000 ──ai──> ai-gateway:4000 (LiteLLM) ──> local | anthropic | openai | mock
jupyterhub ──(AI_GATEWAY_HUB_TOKEN)──> ai-keys:8080 (broker) ──(master key, ai)──> ai-gateway admin API
```

`ai-gateway` is only on the `ai` network; workspaces are only on `lab`. The **AI front door**
(`bootstrap/ai_frontdoor.py`, service `ai-frontdoor`) is the only path between them and the
single source of truth for what a user key may call: `POST /v1/chat/completions`,
`POST /chat/completions`, `POST /v1/messages[?beta=true]`, `POST /v1/messages/count_tokens[?beta=true]`,
`POST /v1/embeddings`, `GET /v1/models`, `GET /v2/user/info` (own user, no query). Everything
else, notably `/health*` (it would call every model), `/model/info` and `/v1/model/info` (they
show each model's `api_base`), `/key/*`, `/user/*`, `/spend/*`, `/global/*`, `/config*` and the
admin UI, gets 403 without reaching the gateway. It also drops every request header but
`Authorization`, `Content-Type`, `Accept`, `User-Agent`, `anthropic-version`, `anthropic-beta`
(so no LiteLLM control or customer-id header), returns no `x-litellm-*` response header, caps
bodies (`LAB_AI_FRONTDOOR_MAX_BODY`, 16 MiB) and streams responses.

| Piece | Where | What |
|---|---|---|
| `ai-gateway` | `compose/ai.yaml`, `images/ai-gateway/`, this folder | LiteLLM proxy, built from PyPI without LiteLLM's proprietary enterprise package; config rendered at start by `render_config.py`; lab hooks in `lab_hooks.py` |
| `ai-gateway-db` | `init-db.sh` | one-shot: role + database `ai_gateway` in the shared Postgres (same pattern as `superset-db`); the gateway runs its own schema migrations |
| `ai-keys` | `bootstrap/ai_gateway.py` | key broker; the only holder of the master key besides the gateway |
| `ai-frontdoor` | `bootstrap/ai_frontdoor.py` | the only way workspaces reach the gateway; route allowlist |
| `ai-mock` | `tests/ai/mock_llm/` | deterministic mock model, tests only (`install.sh --ai-mock`) |

## Providers: off by default

| Provider | Enabled by | Setting |
|---|---|---|
| `local` | `./lab ai set-local URL` or `install.sh --ai-local-url URL` (asked on `full`) | `LAB_AI_LOCAL_URL`, `LAB_AI_LOCAL_MODEL` in `.env` |
| `anthropic`, `openai` | `./lab ai enable-hosted --provider … --key-file …` (admin) | `LAB_AI_ANTHROPIC_API_KEY` / `LAB_AI_OPENAI_API_KEY` in `.secrets.env` |
| `mock` | `install.sh --ai-mock` (tests) | `LAB_AI_MOCK=true` in `.env` |

Model names for clients: `lab-default` (mock, else local, else anthropic, else openai;
`LAB_AI_DEFAULT_PROVIDER` overrides), plus `local`, `claude`, `gpt`, `mock` for each enabled
provider. With **no provider**, the rendered model list is empty and every AI request is answered
`AI isn't configured; ask your lab admin.` (HTTP 503) before any routing: the gateway has nowhere
to send a request, so the lab makes no outbound AI call. `tests/ai/gateway-e2e.sh` proves it
(rendered config, the message, and a socket watch of the gateway).

`./lab ai set-local` checks a local server with `GET /health` and `GET /v1/models` only. Nothing
in the lab calls a model by itself: no background health checks, no retries, and nobody calls the
gateway's `/health` endpoint (it would send a request to every model); the container healthcheck
uses `/health/liveliness`.

## Quiet hours for the local model (Phase 6)

A local model server often runs on someone's own machine, whose fans should stay quiet at night.
`./lab ai quiet-hours 22:00-07:00 --tz America/New_York` sets a daily window (wall-clock time in
that zone; `--tz` defaults to `LAB_TZ`), `./lab ai quiet-hours off` removes it, and
`./lab ai quiet-hours` / `./lab ai status` show it (`quiet  22:00-07:00 America/New_York, local
model only (now: ...)`). Off by default; `install.sh` asks once, interactively, when a local URL is
set. The settings are `LAB_AI_QUIET_HOURS` and `LAB_AI_QUIET_TZ` in `.env`.

- During the window the gateway refuses every request for a model that reaches the `local`
  provider (`local`, and `lab-default` when it resolves to local) **before routing**, in the
  `lab_hooks` pre-call hook: HTTP 503, type `ai_quiet_hours`, a `Retry-After` header, and "The
  lab's local AI model is resting until 07:00 America/New_York (quiet hours 22:00-07:00). …". The
  Lab Assistant shows that sentence as is. Nothing is sent to the model server.
- Hosted providers (and the test mock) are not affected. `lab-default` is not re-routed to a
  hosted provider during quiet hours: choosing a hosted model is the user's (`claude`, `gpt`).
- Start inclusive, end exclusive, minute granularity; a start later than the end crosses midnight.
  DST: the window follows the wall clock (a spring-forward night is an hour shorter; a start
  inside the skipped hour begins at the first minute after it; on a fall-back night a window
  over the repeated hour lasts an hour longer). Tested with an injected clock in
  `tests/ai/test_quiet_hours.py`; the CLI in `tests/ai/test_lab_quiet_hours.py`.
- A bad setting stops the gateway at start (render_config exits), so it never routes to the
  local model by mistake; `./lab ai quiet-hours` validates both values before writing them.

## Budgets and keys

Each JupyterHub user is a gateway user with role `internal_user_viewer` (inference and their own
spend only; cannot create keys or change budgets) and a **per-user** budget:
`LAB_AI_USER_BUDGET_USD` (default 5) per `LAB_AI_BUDGET_DURATION` (default 30d), and
`LAB_AI_USER_RPM` requests per minute (default 30). The broker applies changed values to every lab
user when it starts. Past the budget, requests get: "Your AI budget for this period is used up. You
have used X of your Y USD AI budget. …" (HTTP 400).

Costs: hosted models use LiteLLM's bundled price map; `local` costs `LAB_AI_LOCAL_COST_PER_MTOK`
USD per million tokens (default 0: free, only the rate limit applies); `mock` costs
`LAB_AI_MOCK_COST_PER_MTOK` (default 1000, so tests overrun quickly).

Keys: the hub mints one on every spawn (`POST /v1/keys/mint`), which also deletes the user's
previous lab keys; spend and budget belong to the user, so rotating never resets them. Keys expire
after `LAB_AI_KEY_DURATION` (default 30d). The broker interface is documented at the top of
`bootstrap/ai_gateway.py`.

## LiteLLM: only open-source features (OQ-7)

LiteLLM is MIT-licensed except its `enterprise/` code and the `litellm-enterprise` package
(BerriAI Enterprise License: production use needs a subscription, redistribution is forbidden).
The upstream Docker image ships both, so the lab builds its own image from PyPI with
`images/ai-gateway/lock/requirements.txt`, which `relock.sh` generates **without**
`litellm-enterprise`; `verify.py` fails the build if any proprietary package or module is
present. Features the lab uses, all in the MIT part of LiteLLM 1.102.1 and exercised by the tests
without a license key:

| Feature | Used for |
|---|---|
| Proxy with a static `config.yaml` model list (OpenAI `/v1/chat/completions`, `/v1/embeddings`, `/v1/models`; Anthropic `/v1/messages`, translated to chat completions for OpenAI-compatible backends) | routing `lab-default`/`local`/`claude`/`gpt`/`mock` |
| Virtual keys with Postgres (`/key/generate`, `/key/list`, `/key/delete`, `/key/info`) | per-user keys |
| Internal users (`/user/new`, `/user/update`, `/user/info`, `/user/list`, `/user/delete`), role `internal_user_viewer` | per-user identity and least privilege |
| User `max_budget` + `budget_duration`, `rpm_limit`, spend tracking | budgets and rate limits |
| Per-deployment `input_cost_per_token`/`output_cost_per_token` | budgets on local and mock models |
| `CustomLogger` callbacks (`async_pre_call_hook`, `async_post_call_failure_hook`) | the "not configured" and budget messages; the end user of every call is set to the key's own user (a body `user` naming someone else is overwritten) |

Not used (enterprise-gated or not needed): the admin UI and its SSO (`DISABLE_ADMIN_UI=True`),
`admin_only_routes`, key-generation restrictions, guardrails, audit logs, tag/team budgets,
Prometheus metrics, pass-through endpoints, MCP gateway.

LiteLLM would otherwise fetch its model price map, Anthropic beta-header map and router presets
from GitHub at start; the image sets `LITELLM_LOCAL_MODEL_COST_MAP`,
`LITELLM_LOCAL_ANTHROPIC_BETA_HEADERS` and `LITELLM_LOCAL_AUTOROUTER_PRESETS` so it uses the
bundled copies, and `telemetry: false`. Prisma runs offline (`PRISMA_OFFLINE_MODE=true`, client and
engines generated at build time).

## Safety notes

- Provider keys are in `.secrets.env` (mode 600) and reach only the `ai-gateway` container.
- Tool outputs that reach a model (MCP servers, Phase 5) are untrusted input; the gateway does not
  make them safe. Prompts and responses are not stored (`store_prompts_in_spend_logs: false`,
  `turn_off_message_logging: true`); spend logs keep metadata only.
- Enabling a hosted provider sends users' questions and the lab data their tools return to that
  provider; `lab ai enable-hosted` says so and asks for confirmation.
