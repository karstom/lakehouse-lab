# AI gateway (Phase 5, GATEWAY)

The lab's model gateway: one place that holds provider keys and per-user budgets, so users
and workspaces never see a provider key (ADR-014, OQ-7, OQ-8). Profile `full` only.

```
workspace (user's virtual key) ──> ai-gateway:4000 (LiteLLM) ──> local | anthropic | openai | mock
jupyterhub ──(AI_GATEWAY_HUB_TOKEN)──> ai-keys:8080 (broker) ──(master key)──> ai-gateway admin API
```

| Piece | Where | What |
|---|---|---|
| `ai-gateway` | `compose/ai.yaml`, `images/ai-gateway/`, this folder | LiteLLM proxy, built from PyPI without LiteLLM's proprietary enterprise package; config rendered at start by `render_config.py`; lab hooks in `lab_hooks.py` |
| `ai-gateway-db` | `init-db.sh` | one-shot: role + database `ai_gateway` in the shared Postgres (same pattern as `superset-db`); the gateway runs its own schema migrations |
| `ai-keys` | `bootstrap/ai_gateway.py` | key broker; the only holder of the master key besides the gateway |
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
| `CustomLogger` callbacks (`async_pre_call_hook`, `async_post_call_failure_hook`) | the "not configured" and budget messages |

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
