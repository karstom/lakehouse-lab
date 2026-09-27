# V3 Phase 5 Results (context-aware AI assist)

> Integration report for Phase 5, built against the "Phase 5" section of `v3/CONTRACT.md`.
> Three workstreams (GATEWAY, WORKSPACE-AI, MCP+TESTS) built in parallel, each in its own
> dev-host project. The integrator then:
> - merged the pins and the cross-cutting patches;
> - upgraded the running Phase 4 install (`v3-p1`, `full`) in place;
> - ran a clean-room `full` install;
> - exercised, for the first time, the pieces no workstream could test alone (the hub-minted
>   key in check 18, and the Jupyter AI persona through the real gateway and mock model);
> - fixed what that exposed, then re-ran on the final tree;
> - tore down every test project.
>
> **Quiet hours were respected throughout.** No inference, completion, chat or embedding
> request was ever sent to the owner's llama-server. The integrator sent it **no request of
> any kind**, not even `/health` or `/v1/models`. Every model call in every test went to the
> deterministic mock model. The one real-model check is prepared for the lead in
> [REAL-MODEL CHECK](#real-model-check-lead-after-0700-americanew_york); it has **not** been run.
>
> Host names, IPs and domains of the dev host are left out on purpose.

## Exit criteria

| Criterion | Result |
|---|---|
| 1. Check 18 as **alice**: a scripted agent loop through the gateway and the MCP servers answers "Which tables feed the 'Revenue by region' dashboard, and when did each last load?"; names from Superset and dbt lineage, load times from Iceberg snapshots, checked against Trino | **Met** on the upgraded `v3-p1` and on the clean room `v3-p5` (see "Check 18 evidence"). The loop used alice's **hub-minted workspace key** (`gateway_key_source: workspace`). |
| 2. Check 18 as **victor**: only what he may read; refused calls, no leak | **Met** on both: alice's private draft dashboard refused, a write refused, 0 of alice's queries visible in `system.runtime.queries`, every load time he got is one he can read himself, no token in any output. |
| 3a. No provider enabled → no outbound AI calls (checked) | **Met.** After the plain upgrade (`./install.sh --non-interactive`, no AI flags) `v3-p1` had no provider: `lab ai status` showed `models: []`, and `tests/smoke/ai-no-provider.sh` passed. On the clean room, `tests/ai/gateway-e2e.sh` step 2 watched the gateway's sockets during start and requests: `outside: []`. |
| 3b. Budget overrun → error | **Met** in check 18 (`gateway_rules.budget`: first 200, second 400 "Your AI budget for this period is used up…") and in `gateway-e2e.sh`. The Jupyter AI persona now shows its friendly budget message for this wording (fixed during integration, see "Found and fixed"). |
| 3c. Tutor prompt carries the module's `tutor.md`; turning it off works | **Met.** Check 18 (`current_lesson`, `lab-ai prompt --module A1` with tutor on and off). Also through the **real** Jupyter AI persona → gateway → mock: the mock's recorded system prompt contains A1's `tutor.md` verbatim with tutor on and no tutor block with tutor off (integrator chat run). |
| 4. Real model (lead-run, after 07:00) | **Prepared, not run.** See the last section. |
| 5. Upgrade in place and clean install (`full`) pass all checks; Docker safety incl. docker-guard; non-v3 objects unchanged | **Met.** `v3-p1` upgrade: `LAB_SMOKE_LONG=1 ./lab test --tracks all` **SMOKE: PASS (18/18; profile full)**. Clean room `v3-p5`: install plus the same test **SMOKE: PASS (18/18)**, `gateway-e2e.sh` PASS, no-provider PASS. Check 11: 54/54 on both, guard forwarded the canonical body. Non-v3 containers, volumes and networks identical before and after (see "Docker safety"). |

## What was integrated

| Piece | Where |
|---|---|
| **ai-gateway**: LiteLLM 1.102.1 built from PyPI into our own image, **without** the proprietary `litellm-enterprise` package and `enterprise/` code (`verify.py` fails the build otherwise); own Postgres DB via the `ai-gateway-db` one-shot | `images/ai-gateway/`, `config/ai/`, `compose/ai.yaml` |
| **ai-keys**: key broker, the only holder of the master key besides the gateway. JupyterHub mints, rotates and revokes per-user keys through it with `AI_GATEWAY_HUB_TOKEN` | `bootstrap/ai_gateway.py` (runs on the bootstrap image) |
| **ai-mock**: deterministic mock model (OpenAI + Anthropic shapes, scripted tool calls), profile `ai-mock`, test installs only | `tests/ai/mock_llm/` |
| **Providers**: `local` (`--ai-local-url`, `lab ai set-local`), hosted (`lab ai enable-hosted`, admin, confirmation), mock (`--ai-mock`). All off by default | `installer/ai.sh`, `install.sh`, `lab` |
| **Workspace AI**: Jupyter AI 3.2 with its `jupyternaut` extra; default persona "Lab Assistant" (gateway only, user's own key, model `lab-default`); key minted at every spawn and revoked at stop; tutor mode from the image's pristine `tutor.md`; `lab-ai` CLI (`status`, `tutor on|off`, `prompt`, `install-claude-code`) | `images/workspace/lakehouse/ai*.py`, `bin/lab-ai`, `config/jupyter_server_config.py`, `config/jupyterhub/jupyterhub_config.py` |
| **Claude Code**: pinned (version + sha256 per platform) in `versions.env`; **only the pin** is in the image; downloaded to `~/.local` only when the user runs `lab-ai install-claude-code`, pointed at the gateway with the user's key | `images/workspace/lakehouse/ai_cli.py` |
| **MCP servers, acting as the user**: `lab-trino` (our wrapper), `lab-context`, official `dbt-mcp` on the user's project and on `analytics`; own venv `/opt/lakehouse/mcp/venv`; registry `/opt/lakehouse/mcp/servers.json` | `images/workspace/mcp/` |
| **Airflow as the user** (`airflow_runs`): plugin `lab_auth` exchanges a `jupyterhub`-azp Keycloak access token for an Airflow API JWT that carries it; Keycloak UMA still decides each request | `config/airflow/plugins/lab_auth.py`, mounted into `airflow-api` only |
| **Check 18** and the no-provider step | `tests/smoke/ai_check.py`, `ai_agent_probe.py`, `ai-no-provider.sh` |

### Integrator wiring

- `compose.yaml` includes `compose/ai.yaml` (before `compose/test.yaml`). Gateway services are
  `[full]`; `ai-mock` has its own profile, which `lab_compose` adds only when `.env` has
  `LAB_AI_MOCK=true`.
- Pins promoted to `versions.env` ("AI assist" section): LiteLLM, prisma-client-py, dbt-mcp,
  the MCP SDK, sqlglot, and Claude Code (version + sha256 per platform). `v3/.pins/` is gone.
- `images/workspace/Dockerfile`: WORKSPACE-AI's version (Claude Code pin, persona dist-info,
  `~/.local/bin` last on `PATH`) plus MCP+TESTS's two hunks (build args, `RUN … mcp/install.sh`).
- `compose/workspace.yaml`: workspace build args for the Claude Code pin and the MCP pins; hub
  environment `LAB_AI_KEYS_URL`, `AI_GATEWAY_HUB_TOKEN` (default empty, so `core`/`engineer`
  start), `LAB_AI_CONTEXT_TOKENS`. No `depends_on` on `ai-keys` (it exists only on `full`; the hub
  treats an unresolvable broker as "not configured").
- `compose/airflow.yaml`: the `lab_auth` plugin mount on `airflow-api` (config hash
  `config/airflow` already covers it, so an upgrade recreates the API server).
- `bootstrap/__main__.py`: **no AI step, by design** (documented in its docstring). The gateway
  DB is a postgres-image one-shot (the bootstrap image has no Postgres driver), and the admin
  side is the long-lived broker, which reconciles every lab user's budget at start. No new
  Keycloak client is needed.
- Secrets: the installer generates `AI_GATEWAY_MASTER_KEY` (`sk-` + hex), `AI_GATEWAY_SALT_KEY`,
  `AI_GATEWAY_DB_PASSWORD`, `AI_GATEWAY_HUB_TOKEN`; also added to `tools/compose-check.sh`'s
  fallback list, `tests/smoke/dev-env.sh`, and the CONTRACT secrets table (plus the optional,
  never-generated `LAB_AI_*_API_KEY`).
- docker-guard: **no change**. The key reaches the workspace only as container `Env`
  (`NAME=value`, already allowed), so the allowlist and check 11's 54 cases are unchanged
  (INV_V3_DOCKER_PROXY_PROJECT_SCOPE).
- CI: `v3-ci.yml` lint job runs `unittest discover -s v3/tests/ai`; `v3-images.yml` path
  filters include `v3/config/ai/**` (the gateway image's named context `config`, which
  `images_matrix.py` takes from the full-profile compose JSON: verified `ai-gateway
  config=v3/config/ai`); `v3-nightly.yml` installs `full` with `--ai-mock --ai-local-url none`,
  runs `tests/ai/gateway-e2e.sh` after the smoke test, and the no-provider step after
  `--no-ai-mock`. The PR matrix is unchanged (check 18 skips outside `full`).
- CONTRACT: secrets rows and a "Conventions added at Phase 5 integration" section.

## Decisions (with evidence)

### OQ-7: the gateway is LiteLLM, open-source part only

LiteLLM 1.102.1, built from PyPI into `lakehouse-lab/v3-ai-gateway`. The upstream image was
rejected because it ships `enterprise/` and `litellm-enterprise` (BerriAI Enterprise License:
no redistribution; our images are public). `relock.sh` writes the lock without that package
(it reported `excluded litellm-enterprise==0.1.67 (LicenseRef-Proprietary)`); the image installs
with `--no-deps`; `verify.py` fails the build if `litellm_enterprise` or `enterprise` is
importable. Recorded as `DEC_V3_AI_GATEWAY_LITELLM_OSS_BUILD`.

**Open-source features used** (all in LiteLLM's MIT part, exercised without a license key):

| Feature | Used for |
|---|---|
| Proxy with a static `config.yaml` model list: OpenAI `/v1/chat/completions`, `/v1/embeddings`, `/v1/models`; Anthropic `/v1/messages` (translated to chat completions for OpenAI-compatible backends) | routing `lab-default`, `local`, `claude`, `gpt`, `mock` |
| Virtual keys in Postgres (`/key/generate`, `/key/list`, `/key/delete`, `/key/info`) | per-user keys, minted per spawn |
| Internal users (`/user/new`, `/user/update`, `/user/info`, `/user/list`, `/user/delete`), role `internal_user_viewer` | per-user identity, least privilege (a user key gets 401 on every management route) |
| User `max_budget` + `budget_duration`, `rpm_limit`, spend tracking | budgets and rate limits |
| Per-deployment `input_cost_per_token` / `output_cost_per_token` | budgets on the local and mock models |
| `CustomLogger` callbacks (`async_pre_call_hook`, `async_post_call_failure_hook`) | the "AI isn't configured" and budget messages |

Not used: admin UI and its SSO (disabled), `admin_only_routes`, key-generation restrictions,
guardrails, audit logs, tag/team budgets, Prometheus metrics, pass-through endpoints, the MCP
gateway. The image uses LiteLLM's bundled cost map, Anthropic beta-header map and router presets
(no fetch from GitHub), telemetry off, Prisma offline. No retries and no background health
checks, so the lab never sends an extra request to a local GPU server or a paid provider; the
container healthcheck is `/health/liveliness` (the gateway's `/health` would call every model).

### OQ-9: Trino MCP is our own thin wrapper

Four community servers were evaluated (table in `images/workspace/mcp/README.md`); none both
uses the user's own JWT **and** enforces read-only access:

| Server | Why not |
|---|---|
| tuannvm/mcp-trino | service identity with `X-Trino-User` impersonation, not the user's token |
| weijie-tan3/trino-mcp | cannot pass the user's bearer token to Trino |
| mcp-trino-python | cannot pass the user's bearer token; not read-only |
| akko-mcp-trino | good AST read-only rule, but reads the JWT once at start (no refresh); beta |

`lab-trino` fetches the token from `lab_token()` on **every** call, allows only
SELECT/SHOW/DESCRIBE/EXPLAIN by a sqlglot AST rule (a write inside a CTE, a second statement and
`EXPLAIN ANALYZE` are refused), returns at most 200 rows, and passes `query_max_run_time` ≤ 30 s
to Trino. Evidence from check 18 (both runs): `writes_refused` create, insert, cte_write,
stacked, explain_analyze all true; `row_cap` 200 rows, truncated; the time limit stopped a query
("the query ran longer than 3s and Trino stopped it"; the check sets 3 s to keep host load short;
30 s is the code ceiling); `current_user` alice. Recorded in `DEC_V3_MCP_SERVERS_AS_USER`.

### Other decisions

- **Hosted off by default (OQ-8, as decided).** `install.sh --non-interactive` never enables a
  provider. Interactively on `full` it asks once for a local URL (default none). A stray
  `LAB_AI_MOCK`, `LAB_AI_LOCAL_URL` or `LAB_AI_*_API_KEY` in the shell is unset by
  `lab_settings`, so only the lab's files decide. `lab ai enable-hosted` warns that lab data goes
  to the provider and requires confirmation or `--yes`.
- **`lab-default` order:** mock (test installs only), then local, then anthropic, then openai;
  `LAB_AI_DEFAULT_PROVIDER` overrides. Local costs 0 USD by default (rate limit only); the mock
  costs 1000 USD per million tokens so budget tests overrun quickly.
- **Per-spawn key.** The hub mints at every spawn (which deletes the user's previous lab keys)
  and revokes at stop. Budget and spend belong to the gateway **user**, so rotation never resets
  them. A broker failure only sets `LAB_AI_STATUS`; a spawn never fails because of AI.
- **Persona:** Jupyter AI's `jupyternaut` extra with a subclassed "Lab Assistant" persona
  registered through a hand-written dist-info. Tutor mode (on by default) offers only read-only
  notebook tools plus the lab's MCP servers; tutor off gives Jupyter AI's normal toolset.
- **MCP venv:** dbt-mcp 2.4.0 pins `mcp==1.26.0` exactly, while jupyter-ai brings `mcp==1.30.0`,
  so the MCP servers run from their own venv.
- **Airflow as the user** needs the `lab_auth` plugin (the Keycloak auth manager mints API
  tokens only from a password). Unit tests added at integration:
  `tests/lint/test_airflow_lab_auth.py` (signature, issuer, `azp`, `typ`, expiry, missing
  claims, `alg: none`; skipped without PyJWT).
- **Check 18's "brain"** is a deterministic policy that reacts to the real tool results and
  drives the mock through its script API; the loop always requests model `mock` and checks
  `/v1/models` first.
- **Memory graph:** `DEC_V3_AI_GATEWAY_LITELLM_OSS_BUILD`, `DEC_V3_WORKSPACE_AI_PERSONA_KEY_PER_SPAWN`,
  `DEC_V3_MCP_SERVERS_AS_USER` (workstreams); `DEC_V3_PHASE5_INTEGRATION_WIRING` and `REG_V3_AI_CHECK18_SPEND_RESTORE_RACE` (integrator).

## Check 18 evidence

Upgraded `v3-p1`, `LAB_SMOKE_LONG=1 ./lab test --tracks all` (the clean room gave the same
result; its private-dashboard id and snapshot times differ):

| Item | alice | victor |
|---|---|---|
| Model / key | `mock` / **workspace key minted by the hub** | same |
| Turns, tool calls, time | 7 turns, 29 tool calls, 332 s | 7, 29, 325 s |
| Tools used | `superset_dashboard_datasets`, `get_lineage_dev`, `get_node_details_dev` (dbt-analytics), `table_last_snapshot`, `airflow_runs`, `trino_query` | same, plus refused calls |
| Dataset tables (Superset) | `analytics.dim_customers`, `analytics.fct_orders`, `analytics.revenue_by_region` | same (he may read them) |
| Upstream (dbt lineage) | `samples.customer`, `lineitem`, `nation`, `orders`, `region` via 5 `stg_*` views | same |
| Load times = Trino `$snapshots` max(`committed_at`), computed separately with the user's own token | all 8 equal | all 8 equal, each readable by victor |
| Denied | — | alice's private draft dashboard ("no dashboard … that you can see"), an INSERT |
| Leak checks | no JWT, user token or gateway key in any output | same; 0 of alice's queries in `system.runtime.queries`; private dashboard id absent |

Gateway rules (throwaway gateway user, admin key): `claude`, `gpt`, `local` refused with
"Invalid model name" (400) and the mock's request count stayed 14 → 14; budget: first call 200,
second 400 "Your AI budget for this period is used up…". Tutor: `current_lesson(A1)` carries
`/opt/lakehouse/tracks/analyst/A1-sql-basics/tutor.md`; `lab-ai tutor off|on` rc 0 with matching
status; `lab-ai prompt --module A1` contains "# A1 · SQL basics: tutor notes" only with tutor on.

**Persona through the real gateway (integrator run, both labs).** A headless login spawned alice
and victor; `ai_chat_probe.py` sent a chat message to the Lab Assistant inside each workspace:
- both workspaces had `LAB_AI_STATUS=ok`, `LAB_AI_MODEL=lab-default`, the gateway URL, a key, and
  `OPENAI_API_KEY` equal to the lab key; `lab-ai status` showed "AI: ready … your own key",
  budget, tutor on, the 4 MCP servers, Claude Code not installed;
- alice, tutor on, chat in `tracks/analyst/A1-sql-basics/`: the reply came from the mock through
  the gateway; the mock's recorded system prompt had the tutor block and A1's `tutor.md`
  **verbatim**, the untrusted-data rule, and only read-only tools (notebook read tools plus the
  lab MCP tools); alice's gateway spend rose;
- alice, `lab-ai tutor off`: no tutor block, no `tutor.md`, the safety rules still present;
- victor: a reply with his own key (his own spend rose).

## Found and fixed during integration

| Finding | Fix |
|---|---|
| **Check 18 left victor over budget.** After the run, victor's gateway spend was 18.69 (v3-p1) / 10.15 (clean room) of 5 USD, so his next real request was refused. The check lifted the budget, ran the loop, then restored budget **and spend** at once; LiteLLM writes spend to the database in batches, so the loop's last batch landed after the restore. | `ai_check.Gateway.restore_budget` now waits until the user's spend has stopped changing (`settle_spend`, 25 s quiet, ≤ 180 s), then restores, and reports the spend read back after one more batch interval (`[info] … spend now … (was …)`). |
| **The persona showed a raw LiteLLM error on a budget overrun** ("Error: litellm.BadRequestError: OpenAIException - Your AI budget … is used up …"). WORKSPACE-AI's mapping was written against its stand-in gateway's wording ("Budget has been exceeded"). | `lakehouse.ai.friendly_error` also recognizes the lab gateway's "used up" wording; unit test with the exact text the persona received. |
| `tests/smoke/ai-no-provider.sh` built its own compose command without `LAB_AUTH_URL`, which compose requires; it worked only when that variable was already exported (from `./lab`). The nightly calls it directly. | It now sources `installer/lib.sh` and calls `lab_settings`, the single place `LAB_AUTH_URL` is derived (INV_V3_PUBLIC_ORIGIN_SINGLE_SOURCE). Verified by calling it directly on `v3-p1` and in the clean room. |
| `tests/lint/test_images_matrix.py` (real-tree check) failed on the gateway image's named context `config`. | The test's full-profile fixture includes `ai-gateway` with `config=../../config/ai`; the real matrix from `compose-check.sh --profile full --json-out` resolves `ai-gateway config=v3/config/ai`. |

## Runs (dev host)

| Run | Result |
|---|---|
| **Upgrade `v3-p1`** (rsync of `v3/` without `.env`, `.secrets.env`, `state/`, `out/`; `./install.sh --non-interactive`, **no AI flags**) | rc 0 in 12 min 56 s (builds the gateway image and the new workspace image). Created `ai-gateway-db`, `ai-gateway`, `ai-keys`; recreated `jupyterhub` and `docker-proxy` (hub config hash), the Airflow services (`config/airflow` hash: the plugin), and the bootstrap-image services. |
| `v3-p1`: provider state after the plain upgrade | `.env` has no `LAB_AI_*`; `.secrets.env` has no provider key; `lab ai status`: `configured: false`, `models: []`; `tests/smoke/ai-no-provider.sh` **PASS** (every model name → 503 "AI isn't configured"). |
| `v3-p1`: mock for tests (`./install.sh --non-interactive --ai-mock --ai-local-url none`) | rc 0 in about 2 min; `.env`: `LAB_AI_MOCK=true`, `LAB_AI_LOCAL_URL=` (empty). |
| `v3-p1`: `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (18/18; profile full)**, 43 min. Check 11 54/54 (canonical body); 13 success (313 s run); 17 all 8 modules; 18 as above. |
| Clean room `v3-p5` (new dir; `--project-name v3-p5 --domain sslip --https-port 18543 --http-port 18180 --seed-test-users --profile full --ai-mock --ai-local-url none`) | install rc 0, 9 min 8 s |
| `v3-p5`: `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (18/18; profile full)**, 42 min |
| `v3-p5`: `tests/ai/gateway-e2e.sh` | **PASS**: mock mode (chat, Anthropic, embeddings, streaming, tool call, rotate, revoke, user-key restrictions, budget), no-provider mode with the socket watch (`outside: []`), local-provider path pointed at the mock |
| `v3-p5`: `./install.sh --non-interactive --no-ai-mock` then `ai-no-provider.sh` | **PASS** (mock container removed; every model → 503) |
| Persona chat through the real gateway (`v3-p1`, integrator harness) | env, alice tutor on/off PASS; victor's message refused: he was left over budget by check 18 (first finding above) |
| **Final tree** (the fixes above; both labs re-synced and re-installed, mock on): `LAB_SMOKE_ONLY=18 ./lab test`, then the persona chat run | `v3-p1` and `v3-p5`: install rc 0; **SMOKE: PASS (4/4)** on both (checks 1, 6, 11, 18); after check 18 every test user's spend was back where it started ("spend now 0.0 (was 0)" for alice and victor; the bug above is gone). Persona chat: env, tutor on (A1 `tutor.md` verbatim, read-only tools), tutor off, victor: **all PASS on `v3-p5`**; on `v3-p1` victor's reply arrived ("mock reply …") but the harness read his spend before the gateway's batch write (0 → 0; 0.333 a few seconds later), a harness timing issue, not a product one. With victor's budget set to 1e-6 the persona answered "You have used up your AI budget for now, so the gateway refused this request. …" (the fixed mapping). |
| `v3-p5`: `lab reset --yes` | rc 0; 0 `v3-p5` containers, volumes and networks left; 4 per-user home volumes deleted |

## Lint and unit tests (final tree)

- `unittest`: `tests/lint` 93 OK (9 new: `test_airflow_lab_auth.py`; the images-matrix fixture
  now includes `ai-gateway`); `tests/bootstrap` 68 OK; `tests/workspace` 62 OK; `tests/ai` 47 OK;
  `tests/smoke` 83 OK (2 skipped without sqlglot).
- `check_versions.py`, `check_compat.py`, `check_tracks.py`: OK.
- `shellcheck.sh` (55 files) and `actionlint.sh` (v3-ci, v3-images, v3-nightly): OK.
- `compose-check.sh` for `core`, `engineer` and `full`: OK (no `.pins` needed any more).
- `tests/installer/run.sh`: 328 passed, 0 failed.
- `core/scripts/consistency_check.sh`: 102 nodes, all references resolve.

## Docker safety

- Audit `~/lakehouse-v3/p5-int-audit/`, 04:46:54 to 06:29:22 UTC: the 11 non-v3 containers
  (name, image, creation time and running state), 22 volumes and 4 networks are **identical**
  before and after.
- Touched only `v3-p1` (upgraded, tested, left running) and `v3-p5` (created, tested, reset). The
  workstreams' `v3-p5-gateway`, `v3-p5-wsai` and `v3-p5-mcp` were already reset (0 objects left);
  no `v3p5*` test image tags remain. No `sudo`, no `prune`.
- docker-guard unchanged; check 11 54/54 with the canonical body on every run (4 runs).
- `v3-p1` is left running on the final tree, profile `full`, gateway configured with the **mock
  provider only** (`LAB_AI_MOCK=true`, `LAB_AI_LOCAL_URL` empty; `lab ai status`: local off, mock
  on, models `lab-default`, `mock`). Test users' gateway spend reset to 0. alice's and victor's
  workspaces from the last chat run are still running (their keys are revoked when they stop).

## Known gaps

- **The real-model exit (4) is not run** (quiet hours); see below. Tool calling through
  llama-server needs its OpenAI tool-call support (llama-server started with `--jinja`); if the
  Qwen model answers without calling tools, that is a llama-server setting, not a lab change.
- **Mock pricing is steep on purpose** (1000 USD per million tokens): one Lab Assistant message
  with its tools costs about 1.8 USD, so a 5 USD budget allows about three chat messages on a
  mock-enabled lab. Real installs never have the mock; `local` defaults to 0 USD.
- **Tutor off gives Jupyter AI's normal toolset**, which includes notebook editing and command
  execution tools; they run as the user in the user's own workspace. Whether Jupyter AI asks for
  approval before each such tool call was not tested here.
- **GitHub CI** has not run the new steps (nothing committed). `v3-nightly.yml` now runs check 18,
  `gateway-e2e.sh` and the no-provider step on `full`.
- **`WATCH_V3_WORKSPACE_IMAGE_TAG_SHARED_ACROSS_PROJECTS`** stays open: the clean room and
  `v3-p1` build the same `lakehouse-lab/v3-workspace` tag. Both were on the same tree here, so
  nothing diverged.
- **Memory:** `full` gains 1 GiB (ai-gateway) + 64 MiB (ai-keys) of limits, plus the 64 MiB
  mock on test installs and a 64 MiB one-shot. Measured by GATEWAY: gateway 545–610 MiB idle,
  about 880 MiB peak during its first migration.

## REAL-MODEL CHECK (lead, after 07:00 America/New_York)

Prepared, **not run**. Everything below runs on the dev host in the `v3-p1` directory
(`~/lakehouse-v3/p1-verify`). Only this section sends inference to llama-server.

**0. Time check (must print 07:00 or later):**

```bash
TZ=America/New_York date
```

**1. Switch `v3-p1` from the mock to the local server.** `lab-default` prefers the mock while it
is on, so turn it off first. `set-local` checks the server with `GET /health` and
`GET /v1/models` only, rewrites `localhost` to `host.docker.internal` for the gateway, and takes
the model id from `/v1/models`.

```bash
cd ~/lakehouse-v3/p1-verify
./install.sh --non-interactive --no-ai-mock
./lab ai set-local http://localhost:9999
./lab ai status        # expect: configured true, models [lab-default, local]
```

**2. Ground truth (from the lakehouse, no model involved).** As alice in her workspace terminal
(or Trino's UI), the newest snapshot of each table:

```bash
python3 - <<'EOF'
from lakehouse.clients import trino_connection  # uses alice's own token (lab_token)
cur = trino_connection().cursor()
for t in ["analytics.dim_customers", "analytics.fct_orders", "analytics.revenue_by_region",
          "samples.customer", "samples.lineitem", "samples.nation", "samples.orders", "samples.region"]:
    s, n = t.split(".")
    cur.execute(f'SELECT max(committed_at) FROM lakehouse.{s}."{n}$snapshots"')
    print(t, cur.fetchone()[0])
EOF
```

Expected answer: the dashboard's datasets are `lakehouse.analytics.dim_customers`,
`fct_orders` and `revenue_by_region`, fed through the `stg_*` views by
`lakehouse.samples.customer`, `lineitem`, `nation`, `orders`, `region`; the load times are the
values printed above.

**3a. Ask through the Lab Assistant (Jupyter AI), as alice.** Log in to `jupyter.` on port
18443 as alice. In a terminal: `lab-ai tutor off` and `lab-ai status` (expect "AI: ready").
Create a chat in the home folder (not under `tracks/`), and ask:

> Which tables feed the 'Revenue by region' dashboard, and when did each last load?

A correct, grounded answer names the tables above and the load times from step 2, and the chat
shows tool calls to `superset_dashboard_datasets`, dbt lineage and `table_last_snapshot`.

**3b. Or through Claude Code in alice's terminal** (downloads the pinned Claude Code from the
internet, user-initiated; it talks only to the lab gateway):

```bash
lab-ai install-claude-code --yes
claude -p "Which tables feed the 'Revenue by region' dashboard, and when did each last load? Use the lab's MCP tools." \
  --allowedTools "mcp__lab-context" "mcp__dbt-analytics" "mcp__lab-trino" --output-format text
```

**4. Record the evidence** (as the lead): the answer text, the ground truth from step 2, and the
gateway's view (`./lab logs --no-follow ai-gateway | tail -n 50`, and alice's budget use from `lab-ai status` in her terminal).

**5. Put `v3-p1` back to the test configuration** (mock on, no local provider):

```bash
./lab ai set-local none
./install.sh --non-interactive --ai-mock --ai-local-url none
./lab ai status        # expect: models [lab-default, mock]
```
