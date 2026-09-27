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
> Correction (repair round): `tests/ai/gateway-e2e.sh` step 3 ("local-via-mock") briefly
> configured the `local` provider, **pointed at the mock**, on `v3-p5`, `v3-p1` and `v3-p5h`.
> No request reached llama-server, but the owner's rule said not to configure the local
> provider at all. Step 3 is now opt-in; see [Repair round](#repair-round-quiet-hours-record-and-gateway-e2e-step-3-opt-in).
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
| 4. Real model (lead-run, after 07:00) | **Met (2026-09-27, 10:55–11:05 EDT).** Qwen3.8-27B (Q4_K_M) on llama.cpp via Lab Assistant → front door → gateway answered the exit question as alice with the correct tables and load times. It took two lead fixes the mock could not reveal; see "REAL-MODEL CHECK: results". |
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
| `v3-p5`: `tests/ai/gateway-e2e.sh` | **PASS**: mock mode (chat, Anthropic, embeddings, streaming, tool call, rotate, revoke, user-key restrictions, budget), no-provider mode with the socket watch (`outside: []`), local-provider path pointed at the mock (this step configured the `local` provider, pointed at `ai-mock`, for the step; see "Repair round") |
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
- **A workspace can reach the Docker host's LAN directly** (follow-up record 4;
  `WATCH_V3_WORKSPACE_LAN_EGRESS_BYPASSES_GATEWAY`). `lab` is not internal: workspaces need
  internet egress (pip, git). So a workspace can open a model server on the host's LAN IP
  (llama-server on `:9999` on the dev host) and bypass the gateway's keys, budgets and logs.
  The front door cannot help, because that traffic never touches it. It was **not** probed.
  The owner's options (details in CONTRACT Phase 5):
  1. give llama-server its own `--api-key`, set as `LAB_AI_LOCAL_API_KEY` for the gateway
     only (simplest; a workspace then gets 401);
  2. on the same host, an `INPUT`-chain rule dropping the `lab` bridge (`br-<id>`) to
     `:9999`. Container-to-host traffic is `INPUT`, not `DOCKER-USER`, and the `ai` bridge
     keeps access;
  3. for a model server on another LAN machine, a `DOCKER-USER` rule for the `lab` bridge;
  4. binding the server to `127.0.0.1` also shuts the gateway out, so it fits only if the
     lab does not use that server.
- **Gateway error texts are passed through.** The front door filters routes and headers,
  not response bodies. A provider error message that LiteLLM puts into a response body
  (e.g. a connection error to the local server) could still name that server's URL. Not
  seen with the mock.
- **`postgres` is also on the `ai` network**, which therefore exists in every profile. On
  `core` and `engineer` it holds only postgres. Adding the network recreated postgres once
  during the upgrade (clients restarted by compose, as designed).
- **Memory:** `full` gains 1 GiB (ai-gateway) + 64 MiB (ai-keys) + 64 MiB (ai-frontdoor) of limits, plus the 64 MiB
  mock on test installs and a 64 MiB one-shot. Measured by GATEWAY: gateway 545–610 MiB idle,
  about 880 MiB peak during its first migration.

## Follow-up: AI front door, end-user attribution, persona allowlist

A review after integration found three problems and one gap. All were fixed at the root and
verified on the dev host (mock backend only; the owner's llama-server got no request of
any kind, not even `/health`). Correction: `gateway-e2e.sh` step 3 did configure the `local`
provider, pointed at `ai-mock`, during these runs; see "Repair round" below.

### What was wrong

| # | Finding | Why it mattered |
|---|---|---|
| 1 | Workspaces called LiteLLM directly (`http://ai-gateway:4000` on `lab`). LiteLLM's MIT build has no `admin_only_routes`, so a user key could call `GET /health` and `/model/info`, `/v1/model/info`. Responses also carried `x-litellm-model-api-base` headers. | `/health` sends a real request to **every** configured model, with no budget charge: a free way to load the owner's GPU server. The model-info routes and headers reveal each deployment's `api_base`, e.g. the model server's host:port. |
| 2 | The end user in LiteLLM's spend logs came from the request body's `user` (or its customer-id headers). | Any user could attribute calls to anyone (`SpendLogs.end_user`, end-user spend rows). |
| 3 | Jupyter AI loads every persona under the `jupyter_ai.personas` entry point group. `jupyter-ai` depends on `jupyter_ai_acp_client`, which registers `claude-acp`, `codex-acp`, `copilot-acp`, `goose-acp`, `kilo-acp`, `kiro-acp`, `mistral-vibe-acp` and `opencode-acp`. The stock `jupyternaut` persona was offered too. | ACP agents talk to their own providers with their own logins. Jupyternaut takes any model string and API base. None of them is bound to the gateway, its budgets, the lab prompt or tutor mode. |
| 4 | `lab` is not an internal network. | A workspace can reach the Docker host's LAN IP directly, and so a model server listening there (see Known gaps). |

### Fixes

- **Fix 1: `ai-frontdoor`, the only way from a workspace to the gateway**
  (`bootstrap/ai_frontdoor.py`: stdlib, on the bootstrap image like docker-guard, a
  `[full]` service in `compose/ai.yaml`).
  - **Networks.** A new `ai` network: `ai-gateway` is **only** there. `ai-frontdoor` and
    `ai-keys` are on `lab` + `ai`. `postgres` is also on `ai` (the gateway's DB). On test
    installs, `ai-mock` and the smoke driver are on `ai` too.
  - **Who else needs the gateway.** Nothing: no Superset, Airflow, Trino or hub
    configuration refers to it (grep). ai-keys reaches the admin API on `ai`, and the hub
    reaches ai-keys on `lab`. The broker now hands out `http://ai-frontdoor:4000` as
    `base_url`, so `LAB_AI_GATEWAY_URL`, `OPENAI_BASE_URL` and Claude Code's
    `ANTHROPIC_BASE_URL` all point at the front door.
  - **`ROUTES` is the single source of truth for what a user key may call.** It lists
    `POST /v1/chat/completions`, `POST /chat/completions`, `POST /v1/messages` and
    `POST /v1/messages/count_tokens` (query `beta=true` only), `POST /v1/embeddings`,
    `GET /v1/models`, and `GET /v2/user/info` (no query: the key's own user, no keys or
    teams). Everything else gets 403 before the gateway.
  - **Request checks.** The (method, path) match is exact and case-sensitive. The path may
    only contain `[A-Za-z0-9/_.-]` and no empty, `.` or `..` segment. Tricks are refused, not
    normalized, and the canonical target is forwarded. A `Bearer sk-…` key is required. A
    POST body needs one `Content-Length` and JSON, is capped at 16 MiB, and may not be
    chunked.
  - **Header allowlists in both directions.** No hop-by-hop or LiteLLM control or
    customer-id header goes in. Only `Content-Type`, `Cache-Control` and `Retry-After` come
    out.
  - **Streaming.** SSE is streamed as it arrives (re-chunked).
  - **lab-ai.** `lab-ai status` reads the budget from `GET /v2/user/info`, which replaces
    the two routes it tried before (`/user/info?user_id=…`, `/key/info`).
- **Fix 2: `config/ai/lab_hooks.py` `attribute_to_key_owner`.** It runs in
  `async_pre_call_hook`, which LiteLLM runs after `add_litellm_data_to_request`. It
  **overwrites** the body `user`, `user_api_key_dict.end_user_id`, and
  `user_api_key_end_user_id` in `metadata`/`litellm_metadata` (and the copied
  `user_api_key_auth`) with the key's `user_id`. A key without a user has it removed.
- **Fix 3: `lakehouse/ai_persona_manager.py` `LabPersonaManager`**, installed as
  `PersonaManagerExtension.persona_manager_class`.
  - It loads only `ALLOWED_PERSONAS = {"lab-assistant": "lakehouse.ai_persona:LabAssistant"}`,
    matched by entry point name **and** object reference, and no `.jupyter/personas` files.
    Its `default_persona_id` is the Lab Assistant.
  - **The Claude persona is not kept.** `claude-acp` runs Claude Code through the
    `claude-agent-acp` adapter, which is not installed and not pointed at the gateway.
    Claude Code in the lab stays the `lab-ai install-claude-code` CLI.
  - **Server log of a spawned workspace:** the 8 ACP personas and `jupyternaut` are "not
    offered in the lab", and "Initialized 1 AI personas".
- **Record 4:** documented, not changed (see Known gaps and CONTRACT Phase 5, "AI front
  door and workspace AI boundaries"). Watchlist `WATCH_V3_WORKSPACE_LAN_EGRESS_BYPASSES_GATEWAY`.
  Nothing probed the host's `:9999`.

### Where the allowlist comes from (real traffic, front door log on `v3-p1`)

| Client | Requests seen | Result |
|---|---|---|
| Jupyter AI Lab Assistant (check 18 chat + the persona harness: alice tutor on/off, victor) | `POST /v1/chat/completions` (streaming) | 200 |
| `lab-ai status` | `GET /v1/models`, `GET /v2/user/info` | 200 |
| MCP agent loop (check 18, alice and victor) | `GET /v1/models`, `POST /v1/chat/completions` | 200 (400 on the models the lab has not enabled, 401/503 in the e2e cases) |
| Claude Code 2.1.274 via `lab-ai install-claude-code` (throwaway gateway user, mock; `claude -p`) | `POST /v1/messages?beta=true` → 200; `HEAD /api/hello` (a connectivity ping) → 403 | Claude Code answered ("mock reply …", rc 0); the ping is not a gateway route (LiteLLM would 404) and stays refused. The test user, its key and the install were removed. |
| OpenAI-compatible clients, embeddings (gateway-e2e) | `POST /v1/embeddings` | 200 |

`POST /chat/completions` (base URL without `/v1`) and `POST /v1/messages/count_tokens` were
not seen in these runs. They are kept on purpose: the gateway serves both, they are
inference routes, and generic OpenAI clients and interactive Claude Code use them.

### Tests added

- `tests/ai/test_ai_frontdoor.py` (15 tests, stdlib):
  - the allowed routes, forwarded canonically, and 70+ refused (method, target) pairs:
    `/health*`, model info, key/user/spend/global/config/UI routes, other LiteLLM routes,
    wrong methods, case, `%`-encoding, `//`, `.`/`..`, trailing `/`, `;`, backslash,
    absolute-form, `*`, and query keys or values that are not allowed;
  - the key rules and the body rules;
  - header filtering both ways;
  - on real sockets against a fake gateway: denied routes never reach it; SSE arrives
    incrementally (first event < 250 ms of a 0.9 s stream); keep-alive after a streamed
    reply; an oversized body is refused unread; raw-socket tricks; gateway down gives 502;
    the allowlist equals the documented one.
- `tests/ai/test_render_config.py`: a spoofed `user` (both metadata slots) becomes the key
  owner; a key without a user drops it.
- `tests/ai/test_ai_gateway.py`: mint returns the front door URLs, never `ai-gateway`.
- `tests/workspace/test_lab_ai.py`:
  - the persona allowlist, with Jupyter AI stubbed: ACP personas, `jupyternaut` and a
    look-alike `lab-assistant` from another package are never imported; there are no local
    personas; the server config installs the manager;
  - `lab-ai` budget uses only `/v2/user/info`, which is in `ROUTES`.
- `tests/ai/gateway_e2e.py` (mock mode, user keys now through the front door):
  - 403 for 18 forbidden routes, including `/health`, `/health/liveliness`, `/model/info`,
    `/v1/model/info`, `/key/*`, `/user/*` and `/spend/logs`, and for 10 raw path tricks;
  - 401 without a key;
  - `/v1/models` works with no `x-litellm-*` header in the reply;
  - own budget works;
  - `/v1/messages?beta=true` works;
  - **spoofed `user` → the spend log's `user` and `end_user` are the key owner**;
  - chat, Anthropic, embeddings, streaming and the tool call all go through the front door.
- `tests/ai/gateway-e2e.sh` step 1b: from `jupyterhub`, which is only on `lab` like a
  workspace, `ai-gateway:4000` fails by name (gaierror) and by IP (timeout), and
  `ai-frontdoor:4000` connects.
- Smoke check 18 (still one check), from **inside alice's workspace**:
  - the environment points at the front door;
  - `ai-gateway:4000` fails by name and by its IP;
  - the front door connects;
  - her own key gets 403 on `/health`, `/model/info` and `/v1/model/info`, and 200 on
    `/v1/models`;
  - `tests/workspace/ai_chat_probe.py` on a new chat file shows the persona list
    `[LabAssistant]` only, and the Lab Assistant answers through the front door (mock).
  - `run.sh` mounts `tests/workspace` read-only at `/opt/tests-workspace`.

### Runs (dev host, mock provider only)

| Run | Result |
|---|---|
| Lint and unit tests (final tree) | `tests/lint` 93 OK, `tests/bootstrap` 68 OK, `tests/workspace` 66 OK (4 new), `tests/ai` 65 OK (18 new), `tests/smoke` 84 OK (2 skipped without sqlglot; 1 new); `check_versions`, `check_compat`, `check_tracks` OK; `shellcheck.sh` (55 files) and `actionlint.sh` OK; `compose-check.sh` core, engineer, full OK; `tests/installer/run.sh` 328 passed, 0 failed; `core/scripts/consistency_check.sh` all references resolve |
| **Upgrade `v3-p1`** in place (rsync without `.env`, `.secrets.env`, `state/`, `out/`; `./install.sh --non-interactive`) | rc 0 in about 7.5 min. The bootstrap and workspace images were rebuilt. Created `ai-frontdoor`. Recreated `ai-gateway` (now `ai` only), `ai-keys`, `ai-mock` and `postgres`: its dependents were restarted by compose (`depends_on … restart: true`, `REG_V3_POSTGRES_RECREATE_BREAKS_DB_CLIENTS_ON_UPGRADE`), and bootstrap was done. Still mock-only: `.env` `LAB_AI_MOCK=true`, `LAB_AI_LOCAL_URL=` (empty), no provider key; `lab ai status` models `[lab-default, mock]`. Networks: `ai-gateway` only `v3-p1_ai`; `ai-frontdoor`, `ai-keys`, `ai-mock`, `postgres` on `v3-p1_ai` + `v3-p1_lab`; `jupyterhub` `lab` + `hub-docker`. |
| `v3-p1`: `tests/ai/gateway-e2e.sh` | **PASS**: mock (24 checks, incl. the front door and the spoofed user), 1b network isolation, not-configured with the socket watch (`outside` empty), local-via-mock, restored (state `providers: [mock]`). **Correction:** step 3 (local-via-mock) configured the `local` provider, pointed at `ai-mock`, for about half a minute (09:59:44 UTC); see "Repair round" below. |
| `v3-p1`: `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (18/18; profile full)**, 10:05 to 10:54 UTC. Check 18's front-door evidence: `LAB_AI_GATEWAY_URL=http://ai-frontdoor:4000`; direct gateway by name "Temporary failure in name resolution", by IP "timed out"; `/health` 403, `/model/info` 403, `/v1/model/info` 403, `/v1/models` 200; persona list `[jupyter-ai-personas::lakehouse::LabAssistant]`; Lab Assistant reply "mock reply …" in 67.5 s. The gateway rules, both agent loops and tutor were unchanged. Spend restored (alice 0.0, victor 0.011). |
| `v3-p1`: persona chat harness (`ai_chat_probe.py` in alice's and victor's workspaces → front door → gateway → mock) | **0 failures**: env (gateway `http://ai-frontdoor:4000`, own key); `lab-ai status` "AI: ready", budget "0.0000 of 5.00" (read through `/v2/user/info`); tutor on (A1 `tutor.md` verbatim, read-only tools); tutor off (no tutor block, safety rules kept); victor's own key and spend. The workspace log: "Initialized 1 AI personas". (That harness reused chat files from the first integration run, whose saved user lists still name `JupyternautPersona`; this is why check 18 now always starts from a new chat file.) Test users' spend was put back afterwards (alice 0.0, victor 0.011). |
| Clean room `v3-p5h` (new dir; `--project-name v3-p5h --domain sslip --https-port 18543 --http-port 18180 --seed-test-users --profile full --ai-mock --ai-local-url none`) | install rc 0, 11:07 to 11:12 UTC (images already built from the same tree); `.env` `LAB_AI_MOCK=true`, `LAB_AI_LOCAL_URL=` |
| `v3-p5h`: `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (18/18; profile full)**, 11:12 to 11:39 UTC. Check 18 front door: all 8 sub-checks true (gateway by name "Temporary failure in name resolution", by IP "timed out"; 403/403/403 on `/health`, `/model/info`, `/v1/model/info`; persona list `[LabAssistant]`) |
| `v3-p5h`: `tests/ai/gateway-e2e.sh` | **PASS** (all steps, incl. 1b: from `jupyterhub` gaierror / timeout / connected). **Correction:** "all steps" includes step 3, which configured the `local` provider pointed at `ai-mock`; see "Repair round" below. |
| `v3-p5h`: `lab reset --yes` | rc 0; 0 `v3-p5h` containers, volumes, networks left; 4 per-user home volumes deleted |

**Docker safety.** Audit `~/lakehouse-v3/p5h-audit/`, 09:41 to 11:44 UTC: the 11 non-v3
containers (name, image, creation time, state), 22 volumes and 4 networks are **identical**
before and after. Touched only `v3-p1` (upgraded, tested, left running) and `v3-p5h`
(created, tested, reset). No `sudo`, no `prune`. docker-guard is unchanged: the workspace
spec did not change, and check 11 passed in both runs.

**State left behind.** `v3-p1` runs the final tree, profile `full`, **mock provider only**
(`LAB_AI_MOCK=true`, `LAB_AI_LOCAL_URL` empty, no provider key; models `lab-default`,
`mock`). Test users' spend is back where it was (alice 0.0, victor 0.011). alice's and
victor's workspaces from the persona harness are still running; their keys are revoked when
they stop. Claude Code was removed from alice's home after the traffic probe.

## Repair round: quiet-hours record and gateway-e2e step 3 opt-in

An adversarial verification of the follow-up found **no product defect**: the front door,
the end-user fix, the persona allowlist, the docs and the graph nodes all held. It found a
procedural one, and a wrong claim in the record.

### Correction to the quiet-hours record

The owner's rule for this work was: send llama-server nothing, never call the gateway's
`/health` with a local provider configured, and **do not configure the local provider at
all; use the mock provider only**. The follow-up's runs broke the last part as written:

- `tests/ai/gateway-e2e.sh` step 3 ("local-via-mock") recreates `ai-gateway` with
  `LAB_AI_LOCAL_URL=http://ai-mock:8000/v1` and `LAB_AI_LOCAL_MODEL=mock-model`. That
  **configures the `local` provider**, pointed at the mock (never at llama-server).
- It ran on `v3-p1` (09:59:44 UTC; `out/ai-e2e/recreate-local.log`, `local-via-mock.log`)
  and on `v3-p5h`. It also ran on `v3-p5` in the first integration run.
- Each time, step 4 put the gateway back on the lab's own settings (mock only). On `v3-p1`
  the gateway was recreated at 10:00:18 UTC with `LAB_AI_LOCAL_URL` empty.
- So the earlier statement that `LAB_AI_LOCAL_URL` stayed empty throughout was **wrong**.
  It was set to the mock's URL for about half a minute per run.
- What did hold: no request of any kind reached llama-server. Every backend was the mock.
  `/health` was only ever sent to the front door, which refused it (403) and did not forward
  it. The gateways saw only their healthcheck's `/health/liveliness`.

### Fix (at the root: the script)

- **Step 3 is opt-in:** `LAB_E2E_LOCAL_VIA_MOCK=1 tests/ai/gateway-e2e.sh`. By default the
  step prints `3. local provider path: SKIPPED (opt-in: …)`. It also deletes any stale
  `recreate-local.log` / `local-via-mock.log` in `out/ai-e2e/`, so old evidence does not
  look like this run's. Any value other than `0` or `1` is refused (exit 2) before
  anything runs. Without the switch, every `compose up` the script runs has an empty
  `LAB_AI_LOCAL_URL`: step 2 (no provider) and step 4 (the lab's own settings).
- **Mock-only lab required.** Steps 1 and 4 use the lab's own settings, so the script now
  reads the gateway's rendered `state.json` first. Unless `providers` is exactly `[mock]`,
  it stops before sending any request. So it cannot be pointed at a lab that has a real
  provider configured (e.g. during the REAL-MODEL CHECK).
- The script header and CONTRACT Phase 5 ("AI assist", tests bullet) document both.
- **CI:** `.github/workflows/v3-nightly.yml` is outside this round's scope (`v3/` only)
  and was not changed. So the nightly now **skips** step 3. To keep that coverage on
  runners, which have no model server, add `env: LAB_E2E_LOCAL_VIA_MOCK: "1"` to its
  "AI gateway end to end" step.
- **Test:** `tests/ai/test_gateway_e2e_script.py` (4 tests). It runs the real script
  against a fake `docker` on `PATH` (no daemon), which logs every call with the
  `LAB_AI_LOCAL_URL` it was given, and checks:
  - by default, exactly two `up` calls, both with an empty `LAB_AI_LOCAL_URL`, step 3
    reported skipped, and no `local-via-mock` run;
  - with the switch, `up` calls empty → `http://ai-mock:8000/v1` → empty, and a stray
    `LAB_AI_LOCAL_URL` in the caller's shell never leaks into them;
  - a bad switch value is refused before any call;
  - a lab whose state lists `["mock", "local"]` is refused before any request or `up`.
  Mutation check: with step 3 forced on, the default-run test fails.
- Graph: `REG_V3_GATEWAY_E2E_CONFIGURES_LOCAL_PROVIDER_BY_DEFAULT` (new);
  `DEC_V3_PHASE5_INTEGRATION_WIRING` updated.

### Runs (dev host; mock provider only, `local` never configured)

| Run | Result |
|---|---|
| Lint and unit tests (final tree) | `tests/lint` 93 OK, `tests/bootstrap` 68 OK, `tests/workspace` 66 OK, `tests/ai` 69 OK (4 new), `tests/smoke` 84 OK (2 skipped without sqlglot); `check_versions`, `check_compat`, `check_tracks` OK; `shellcheck.sh` (55 files) and `actionlint.sh` OK; `compose-check.sh --profile` core, engineer, full OK; `tests/installer/run.sh` 328 passed, 0 failed; `core/scripts/consistency_check.sh` 108 nodes, all references resolve |
| Precondition, 12:45 UTC | `v3-p1` `.env` `LAB_AI_MOCK=true`, `LAB_AI_LOCAL_URL=` (empty); gateway env `LAB_AI_LOCAL_URL` empty; state `providers: [mock]` |
| **Upgrade `v3-p1`** in place (rsync without `.env`, `.secrets.env`, `state/`, `out/`; `./install.sh --non-interactive`) | rc 0, 12:45:10 to 12:45:55 UTC (only test files and docs changed); compose recreated `trust-init`, `bootstrap` and `ai-keys`, nothing else; still mock-only; 36 containers healthy |
| `v3-p1`: `tests/ai/gateway-e2e.sh` (default, no switch), 12:46 to 12:51 UTC | **PASS**: mock (24 checks, incl. the front door and the spoofed user), 1b network isolation, not-configured with the socket watch (`outside` empty), **`3. local provider path: SKIPPED`**, restored (`providers: [mock]`). `out/ai-e2e/` has no `recreate-local.log` / `local-via-mock.log` (the stale ones from 09:59 were removed). |
| `v3-p1`: `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (18/18; profile full)**, 12:56 to 13:24 UTC. Check 18's front-door sub-checks all true: env `http://ai-frontdoor:4000`; direct gateway by name "Temporary failure in name resolution", by IP "timed out"; `/health` 403, `/model/info` 403, `/v1/model/info` 403, `/v1/models` 200; persona list `[jupyter-ai-personas::lakehouse::LabAssistant]`; the Lab Assistant answered "mock reply …" through the front door (39.9 s). Check 11: 54/54. |
| `v3-p1`: `ai_chat_probe.py` (Jupyter AI persona → front door → gateway → mock), alice and victor spawned by a headless login | **0 failures**, 13:25 to 13:28 UTC: env `gw=http://ai-frontdoor:4000`, own key; `lab-ai status` "AI: ready", budget "0.0000 of 5.00"; tutor on: reply "mock reply …", personas `[LabAssistant]` only, A1 `tutor.md` verbatim in the system prompt, read-only tools; tutor off: no tutor block, safety rule kept; victor: reply, personas `[LabAssistant]` only. Spend put back afterwards (alice 0.0, victor 0.011). |
| `v3-p1`: `tests/ai/gateway-e2e.sh` again with the spoof check's unique content, 13:30 to 13:34 UTC | **PASS** (step 3 skipped; spoofed user recorded as the key owner) |
| Clean room `v3-p5h` (**new** dir; `--project-name v3-p5h --domain sslip --https-port 18543 --http-port 18180 --seed-test-users --profile full --ai-mock --ai-local-url none`) | install rc 0, 13:29 to 13:33 UTC; `.env` `LAB_AI_MOCK=true`, `LAB_AI_LOCAL_URL=`; state `providers: [mock]` |
| `v3-p5h`: `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (18/18; profile full)**, 13:33 to 14:00 UTC; check 18 front door: all 8 sub-checks true (by name gaierror, by IP timeout; 403/403/403; `/v1/models` 200; persona list `[LabAssistant]`); check 11: 54/54 |
| `v3-p5h`: `tests/ai/gateway-e2e.sh` (default) | **PASS**, 14:00 to 14:04 UTC; step 3 SKIPPED; gateway env afterwards `LAB_AI_LOCAL_URL` empty; gateway log: 0 `/health` requests other than `/health/liveliness` |
| `v3-p5h`: `lab reset --yes` | rc 0; 0 `v3-p5h` containers, volumes, networks left; 4 per-user home volumes deleted |

**Quiet hours in this round.** The `local` provider was **never configured** on any
project. Nothing sent llama-server anything: no inference, no `/health`, no `/v1/models`.
The host's `:9999` was not probed. `v3-p1`'s `.env`, its gateway's environment and its
rendered state stayed mock-only the whole time (gateway recreated at 12:51 and 13:33 UTC by
the e2e restore step, both times with `LAB_AI_LOCAL_URL` empty). Its log since the upgrade has
0 matches for `9999`, `host.docker.internal` or `hosted_vllm`, and 0 `/health` requests other
than the healthcheck's `/health/liveliness`. The only `/health` requests were the
e2e and check-18 probes to the front door, all denied there (403) and never forwarded.

**Docker safety.** Audit `~/lakehouse-v3/p5r-audit/`, 12:45 to 14:05 UTC: the 11 non-v3
containers (name, image, creation time, state), 22 volumes and 4 networks are
**identical** before and after. Touched only `v3-p1` (upgraded, tested, left running) and
`v3-p5h` (created in the new dir `~/lakehouse-v3/p5r`, tested, reset). No `sudo`, no `prune`.

**State left behind.** `v3-p1` runs the final tree, profile `full`, **mock provider only**
(`LAB_AI_MOCK=true`, `LAB_AI_LOCAL_URL` empty, no provider key; models `lab-default`,
`mock`). Test users' spend is where it was (alice 0.0, victor 0.011). alice's and victor's
workspaces from the probe are still running; their keys are revoked when they stop.

### Notes (non-blocking, from the verification)

- **Mock response ids repeat.** The mock's response `id` is derived from the message
  content, so two users who send the same text get the same `request_id`, and LiteLLM
  keeps only the first spend-log row. User spend is still charged correctly. Any test that
  reads spend logs must send unique requests. `gateway_e2e.py`'s spoofed-user check was only
  unique through the per-run user that the gateway forwards; it now also puts that user
  into the message text (`spoof <user>`), so the row it looks for is always new.
- **Malformed request lines hold a thread.** HTTP/0.9 and other malformed request lines
  keep one front-door thread until the client disconnects or the 60 s socket timeout ends
  it. Nothing is forwarded, so this is not a bypass. It is a small resource cost per slow
  or broken client.
- **Persona manager override (own workspace only).** A user could set
  `PersonaManagerExtension.persona_manager_class` in their own `~/.jupyter` config and load
  other personas. That affects only their own workspace. It gives no route to the gateway
  beyond the front door, and no model access beyond the documented LAN egress gap (Known
  gaps). Not tested.

## REAL-MODEL CHECK (lead, after 07:00 America/New_York)

Prepared, **not run**. Everything below runs on the dev host in the `v3-p1` directory
(`~/lakehouse-v3/p1-verify`). Only steps 3a and 3b send inference to llama-server. **No
step calls `/health`**, neither the gateway's (the front door refuses it anyway: 403) nor
llama-server's (`set-local --no-probe`). The only metadata call to llama-server is
`GET /v1/models` in step 1. The Lab Assistant path is driven by
`tests/workspace/ai_chat_probe.py` (step 3a), the same probe check 18 runs against the mock.

**Do not run test suites while the local provider is configured** (between steps 1 and 5):
no `./lab test`, no `tests/ai/gateway-e2e.sh` (it refuses anyway: it runs only when the
gateway's providers are exactly `[mock]`). Tests belong before step 1 or after step 5.

**0. Time check (must print 07:00 or later):**

```bash
TZ=America/New_York date
```

**0b. Dry run on the mock (optional, before step 1).** The step 3a command with
`--chat real-model/dry-run.chat` must print `"ok": true` and a reply starting "mock reply".
That proves alice's server, the probe, the front door and the persona before any real
inference.

**1. Switch `v3-p1` from the mock to the local server.** `lab-default` prefers the mock while it
is on, so turn it off first. Take the model id from llama-server's model list (metadata only).
`set-local --no-probe` then skips its own `/health` check. It rewrites `localhost` to
`host.docker.internal` for the gateway (the gateway is on the `ai` network, whose bridge
reaches the host).

```bash
cd ~/lakehouse-v3/p1-verify
./install.sh --non-interactive --no-ai-mock
MODEL=$(curl -fsS --max-time 5 http://localhost:9999/v1/models | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"][0]["id"])')
./lab ai set-local http://localhost:9999 --model "$MODEL" --no-probe
./lab ai status        # expect: configured true, models [lab-default, local]
```

**2. Ground truth (from the lakehouse, no model involved).** As alice in her workspace terminal
(or Trino's UI), the newest snapshot of each table:

```bash
python3 - <<'PY'
from lakehouse.clients import trino_connection  # uses alice's own token (lab_token)
cur = trino_connection().cursor()
for t in ["analytics.dim_customers", "analytics.fct_orders", "analytics.revenue_by_region",
          "samples.customer", "samples.lineitem", "samples.nation", "samples.orders", "samples.region"]:
    s, n = t.split(".")
    cur.execute(f'SELECT max(committed_at) FROM lakehouse.{s}."{n}$snapshots"')
    print(t, cur.fetchone()[0])
PY
```

Expected answer: the dashboard's datasets are `lakehouse.analytics.dim_customers`,
`fct_orders` and `revenue_by_region`, fed through the `stg_*` views by
`lakehouse.samples.customer`, `lineitem`, `nation`, `orders`, `region`; the load times are the
values printed above.

**3a. The Lab Assistant (Jupyter AI persona → front door → gateway → llama-server), scripted
with `ai_chat_probe.py`.** Log in to `jupyter.` on port 18443 as alice once (browser), so her
server runs. In her terminal run `lab-ai tutor off` and `lab-ai status` (expect "AI: ready"
and the gateway `http://ai-frontdoor:4000`). Then, from the `v3-p1` directory on the host:

```bash
docker cp tests/workspace/ai_chat_probe.py v3-p1-ws-alice:/tmp/ai_chat_probe.py
docker exec v3-p1-ws-alice bash -c 'python3 /tmp/ai_chat_probe.py \
  --base "http://127.0.0.1:8888${JUPYTERHUB_SERVICE_PREFIX}" --token "$JUPYTERHUB_API_TOKEN" \
  --chat real-model/revenue.chat --timeout 900 --quiet-s 30 \
  --message "Which tables feed the '"'"'Revenue by region'"'"' dashboard, and when did each last load?"' \
  | tee ~/lakehouse-v3/p5-real-model-chat.json
```

The probe opens a new chat file through jupyterlab-chat's WebSocket, addresses the message to
the Lab Assistant and waits for its complete reply, so the request goes persona → front door
(`http://ai-frontdoor:4000`, alice's own key) → gateway → `local` → llama-server.
Expect `"ok": true`, `"personas": ["jupyter-ai-personas::lakehouse::LabAssistant"]` (the only
persona) and a reply that names the tables above with the load times from step 2. Open
`real-model/revenue.chat` in alice's JupyterLab to see the tool calls
(`superset_dashboard_datasets`, dbt lineage, `table_last_snapshot`). A reply that arrives in
pieces can end the probe early; raise `--quiet-s` then.

**3b. Or through Claude Code in alice's terminal** (downloads the pinned Claude Code from the
internet, user-initiated; it talks only to the lab's front door):

```bash
lab-ai install-claude-code --yes
claude -p "Which tables feed the 'Revenue by region' dashboard, and when did each last load? Use the lab's MCP tools." \
  --allowedTools "mcp__lab-context" "mcp__dbt-analytics" "mcp__lab-trino" --output-format text
```

**4. Record the evidence** (as the lead): the answer text (step 3a JSON or 3b output), the
ground truth from step 2, and the gateway's and front door's view
(`./lab logs --no-follow ai-gateway | tail -n 50`, `./lab logs --no-follow ai-frontdoor | tail -n 20`:
only `allow POST /v1/chat/completions` / `/v1/messages` lines expected), and alice's budget use
from `lab-ai status` in her terminal. Confirm that nothing called `/health` during the check
(only the container healthcheck's `/health/liveliness` may appear):

```bash
./lab logs --no-follow ai-frontdoor | grep -c ' /health'                       # expect 0
./lab logs --no-follow ai-gateway | grep -E '"(GET|POST) /health' | grep -vc liveliness  # expect 0
```

**5. Put `v3-p1` back to the test configuration** (mock on, no local provider):

```bash
./lab ai set-local none
./install.sh --non-interactive --ai-mock --ai-local-url none
./lab ai status        # expect: models [lab-default, mock]
```

## REAL-MODEL CHECK: results (lead, 2026-09-27)

Run from 10:46 to 11:10 EDT, after the owner's 07:00 quiet-hours limit.

- **0b. Dry run on the mock:** `ok: true`. The Lab Assistant, the only persona, answered
  "mock reply …".
- **1. Switch to local:** exposed **REG_V3_LAB_AI_STALE_EXPORT**. `lab ai set-local` wrote
  the URL to `.env`, but `ai_apply` ran compose with the stale exported empty value, so the
  gateway came up with no provider (fail-safe: no calls).
  - **Fix:** `ai_apply` re-reads `.env` (`lab_settings`) before compose.
  - **Regression test:** `set-local applies the new URL (no stale export)`. It fails without
    the fix and passes with it.
  - After the fix, the gateway reported `providers: local; lab-default -> local`.
- **2. Ground truth (Trino as alice, newest snapshot):**
  - analytics.dim_customers 2026-09-27 14:13:36.419 UTC
  - fct_orders 14:13:36.725
  - revenue_by_region 14:13:38.740
  - samples.* 2026-09-26 00:11:25–32
- **3a, first attempt:** llama-server returned 400 `unsupported content[].type`. The
  persona's LangChain agent sends typed content parts, including duplicate `tool_call` and
  reasoning blocks, on the round after a tool call. This is
  **REG_V3_AI_CONTENT_PARTS_LOCAL_SERVER**.
  - **Fix:** the gateway pre-call hook `normalize_content` keeps text and image parts, drops
    the duplicate structured parts and flattens all-text content to a string.
  - 72 AI unit tests pass.
  - The 400 is raised while the request is parsed, so it did negligible model work.
- **3a, second attempt:** `ok: true` in 159.5 s (reply in 69.4 s). The only persona was
  Lab Assistant.
  - **Tools called:** `superset_dashboard_datasets`, then `table_last_snapshot` for each
    table.
  - **Answer:** the three `lakehouse.analytics` datasets (`dim_customers`, `fct_orders`,
    `revenue_by_region`), last loaded 14:13:36 / 14:13:36 / 14:13:38 UTC. That matches the
    ground truth.
  - It also gave record counts (1,500 / 15,000 / 35) and noted the times are "as visible to
    you (alice)". It then offered to trace the upstream dbt lineage without being asked.
- **4. Evidence:**
  - 0 `/health` lines in the front door log.
  - 0 non-liveliness `/health` lines in the gateway log.
  - alice's budget: 0.3320 of 5.00 USD.
- **5. Restored:** `v3-p1` is mock-only again (`LAB_AI_MOCK=true`, `LAB_AI_LOCAL_URL`
  empty, gateway `providers: mock`).

**Lesson:** the mock accepts any request shape, so a real OpenAI-compatible server is the
only test for request-format compatibility. Keep a real-model smoke run (daytime only) as
part of each AI change.
