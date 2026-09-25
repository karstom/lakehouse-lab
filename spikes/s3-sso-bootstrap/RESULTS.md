# S-3 Results: SSO bootstrap (Keycloak → JupyterHub, Superset, Airflow 3, Trino, Lakekeeper)

**Verdict: PASS.** All four pass criteria hold on $LAB_SERVER (project `v3-s3`), 2026-09-25.
`./test.sh` goes from `down -v` to all checks green in about 2.5 minutes (131 s to healthy, then
the browser tests). A second run (`FAST=1 ./test.sh`) also passes, so the test is idempotent. The stack is still running.

## What was built

| Piece | Image / pin | Notes |
|---|---|---|
| Caddy | `caddy:${CADDY_VERSION}` | Only published port: `18443`. `local_certs` (internal CA), one site per subdomain. Has network **aliases** for every `*.LAB_DOMAIN` name, so containers resolve the public hostnames straight to Caddy and the issuer URL is the same string for browsers and services |
| trust-init | same Caddy image | One-shot container. Waits for Caddy's root CA and writes `caddy-root.crt` + `ca-bundle.crt` (system CAs + Caddy root) into a `trust` volume that every service mounts read-only |
| Postgres | `postgres:${POSTGRES_VERSION}` | One DB and owner each for keycloak, superset, airflow and lakekeeper (`postgres/init-dbs.sh`) |
| Keycloak | `quay.io/keycloak/keycloak:${KEYCLOAK_VERSION}` | `start --import-realm`, `KC_HOSTNAME=https://auth.${LAB_DOMAIN}:${LAB_PORT}`, `KC_PROXY_HEADERS=xforwarded` |
| Realm template | `keycloak/realm-lakehouse.json` | Realm `lakehouse`. Groups `lab-admin/engineer/analyst/viewer`. 5 OIDC clients (4 confidential, Lakekeeper public+PKCE), each with a `groups` mapper and an audience mapper. Redirect URIs and secrets are Keycloak **`${ENV}` placeholders** resolved at import. Airflow client roles `Viewer/User/Op/Admin/SuperAdmin`, assigned through group `clientRoles`. 5 seeded users: alice=lab-admin, eddie=engineer, anna=analyst, victor=viewer, sam=viewer (used to test group changes) |
| JupyterHub | `v3-s3/jupyterhub` = hub `${JUPYTERHUB_VERSION}` + `oauthenticator==${OAUTHENTICATOR_VERSION}` | GenericOAuthenticator, `auto_login`, `manage_groups`, `admin_groups={lab-admin}`. No spawner (S-4's job) |
| Superset | `v3-s3/superset` = `${SUPERSET_VERSION}` + authlib + psycopg2-binary + `superset_config.py` | FAB `AUTH_OAUTH` provider `keycloak`, `AUTH_ROLES_MAPPING`, `AUTH_ROLES_SYNC_AT_LOGIN`, `ENABLE_PROXY_FIX`. `start.sh` runs `db upgrade` + `init` and then serves. No local admin user |
| Airflow | `v3-s3/airflow` = `${AIRFLOW_VERSION}-python${AIRFLOW_PYTHON}` + `apache-airflow-providers-keycloak==${AIRFLOW_PROVIDERS_KEYCLOAK_VERSION}` | `KeycloakAuthManager`. The `airflow-init` one-shot runs `db migrate` and then the provider's own `airflow keycloak-auth-manager create-all` (skipped if it already ran). `airflow-api` runs `api-server --proxy-headers` |
| Trino | `trinodb/trino:${TRINO_VERSION}` | `http-server.process-forwarded=true`, OAuth2 web UI, `oauth2-jwk.http-client.trust-store-path=/trust/caddy-root.crt` (PEM) |
| Lakekeeper | `quay.io/lakekeeper/catalog:${LAKEKEEPER_VERSION}` | `migrate` one-shot + `serve`. `OPENID_PROVIDER_URI` = Keycloak realm, `OPENID_AUDIENCE=lakekeeper`, UI client `lakekeeper` |
| tester (profile `test`) | `v3-s3/tester` = Playwright `${PLAYWRIGHT_IMAGE_TAG}` | **Host-networked**, so it comes in through the published port 18443 like a real browser. It imports Caddy's root into Chromium's NSS store with `certutil`, the same way a user would. No `--ignore-certificate-errors` |

Extra pins are in `versions.local.env`: `OAUTHENTICATOR_VERSION=17.4.0`,
`AIRFLOW_PROVIDERS_KEYCLOAK_VERSION=0.10.0`, `AUTHLIB_VERSION=1.8.0`,
`PSYCOPG2_BINARY_VERSION=2.9.9` (Superset 6.1.0's own pin), `PLAYWRIGHT_VERSION=1.63.0`,
`PLAYWRIGHT_IMAGE_TAG=v1.63.0-noble`.
Non-version settings are in `lab.env` (`LAB_DOMAIN`, `LAB_PORT`, `KC_ADMIN_USER`).
`gen-secrets.sh` creates `.secrets.env` (random hex values, git-ignored, never synced).
`dc.sh` is the only way compose gets called; it fixes `-p v3-s3` and passes all 4 env files.

Resources: `mem_limit`/`cpus` are set on every container, 11.1 GB of limits in total. Measured
use at idle: ~2.4 GB (Trino 730 MB, Keycloak 565 MB, Superset 510 MB, Airflow API 270 MB,
Postgres 207 MB, Hub 126 MB, Lakekeeper 25 MB, Caddy 19 MB).

## Pass criteria

| # | Criterion | Result | Evidence (`test.sh` output, `out/results.json`, `out/*.png`) |
|---|---|---|---|
| 1 | `down -v` → fully up, no manual steps | **PASS** | `docker compose up --wait` came up healthy in **131 s**. One-shots `trust-init`, `airflow-init` and `lakekeeper-migrate` exited 0. Issuer `https://auth.<lab-ip>.sslip.io:18443/realms/lakehouse` served from the imported template. All 6 subdomains verify against Caddy's root only (`curl --cacert`) |
| 2 | One Keycloak login reaches all five apps | **PASS** | In one browser context, alice saw the Keycloak password form **once**. After that: Hub `/hub/home` shows `alice`. Superset `/api/v1/me/` → `alice`. Airflow `/api/v2/dags` → 200. Trino `/ui/api/stats` → 200. Lakekeeper UI made Bearer calls to `/management/v1/*` (200) and `whoami` → `Alice Admin`, `oidc~<sub>` |
| 3 | Group → role differs for admin vs viewer (Superset, Airflow) | **PASS** | Superset: alice `[Admin]`, victor `[Gamma]`. Airflow: alice `POST /api/v2/pools` → 201, victor → **403** (both can `GET /api/v2/dags` → 200). Bonus, JupyterHub: `/hub/admin` alice 200, victor 403 |
| 4 | Group change in Keycloak shows up on next login | **PASS** | sam's group was set through the Keycloak admin REST API to viewer → lab-admin → viewer, with a fresh login each time. Superset `[Gamma]→[Admin]→[Gamma]`. Airflow create-pool `403→201→403`. Hub admin `403→200→403`. Demotion is picked up too, not only promotion |

Per app: all 5 apps authenticate through Keycloak with no clicks after the single password entry.
The one exception is Lakekeeper, whose UI shows a **"Sign In" button** first (a UI design choice; with a live Keycloak session one click is enough).

## Surprises / gotchas (each one cost an iteration)

1. **Every service needs the internal CA, and each one reads it differently.** This matters for OQ-3 and Phase 1:
   - Python `requests`/authlib (Superset) and python-keycloak (Airflow) use `REQUESTS_CA_BUNDLE`.
   - **JupyterHub/oauthenticator uses Tornado's *pycurl* client, which ignores `SSL_CERT_FILE`.** It fails with
     `HTTP 599: server certificate verification failed. CAfile: none`. Fix: `http_request_kwargs = {"ca_certs": ...}`.
   - Trino reads the PEM through `oauth2-jwk.http-client.trust-store-path`. No keytool is needed.
   - Lakekeeper (rustls-native-certs) honours `SSL_CERT_FILE`.
   - Playwright: Chromium reads NSS, but its `APIRequestContext` runs in Node and needs `NODE_EXTRA_CA_CERTS` as well.
2. **Trino 483 rejects `http-server.authentication.oauth2.groups-field`** ("was not used"). Trino
   group mapping (for file-based access control) has to come from a group provider in Phase 1. The web-UI login works without it.
3. **The Airflow Keycloak auth manager authorizes through Keycloak Authorization Services (UMA)**, not token
   claims. Its model (scopes, resources, `Allow-<Role>` role policies, permissions) is created by the provider
   CLI `create-all`, which **cannot be run twice** (it POSTs scopes without `skip_exists`), so
   `ensure_keycloak_authz.py` skips it when the `MENU` scope already exists. The realm template sets the
   client's resource server to `decisionStrategy: AFFIRMATIVE` (otherwise the ReadOnly and Admin permissions
   on the same scope would both have to grant). `create-all` needs Keycloak **admin** credentials, so only the
   one-shot `airflow-init` gets them (blanked on `airflow-api`).
4. In Airflow, **viewer still sees the "Admin" menu** (read-only), because the provider's `ReadOnly` permission grants
   `GET/MENU/LIST` on every resource. Writes are denied (403). If "viewer" should not browse
   connections/config, Phase 1 needs a custom permission set.
5. Superset: FAB also keeps the registration role (`Public`, no permissions) next to the mapped role.
   Harmless; the test compares mapped roles.
6. Lakekeeper: the first OIDC user lands on `/ui/bootstrap` (catalog not bootstrapped, `is-instance-admin: false`).
   Authentication works; **catalog bootstrap/instance-admin assignment is a separate bootstrap-job step** (S-1/Phase 1).
   Group → Lakekeeper permission mapping was not attempted (OQ-5).
7. Keycloak returns `400 missingNormalization` for `//realms/...` (a trailing slash on the base URL). Build admin URLs carefully.
8. JupyterHub has no healthcheck by default, so `up --wait` reported it ready before the hub was listening.
   Added a `/hub/health` check.
9. Behind Caddy, JupyterHub sees `X-Forwarded-Proto: https,http` (configurable-http-proxy appends to it). This was harmless here.
10. Wildcard redirect URIs (`https://<svc>.${LAB_DOMAIN}:${LAB_PORT}/*`) kept the spike simple. Phase 1 should
    list the exact callback paths: `/hub/oauth_callback`, `/oauth-authorized/keycloak`,
    `/auth/login_callback`, `/oauth2/callback`, `/ui/callback`.

## OQ-3: trusting Caddy's internal CA, and is plain HTTP viable?

Evidence (`tester/oq3_probe.py`, run by `test.sh`):
```
OQ3 http://catalog.<lab-ip>.sslip.io:18080/ {'secureContext': False, 'cryptoSubtle': False}
OQ3 http://catalog.lab.localhost:18080/          {'secureContext': True,  'cryptoSubtle': True}
OQ3 untrusted CA: Page.goto: net::ERR_CERT_AUTHORITY_INVALID at https://catalog.<lab-ip>.sslip.io:18443/ui/
```
Trino with `X-Forwarded-Proto: http` → `303 /ui/static/disabled.html` (the web UI turns itself off without HTTPS).

**Plain HTTP on `<ip>.sslip.io` is not viable.** It is not a browser secure context, so `crypto.subtle`
is missing, and browser-side PKCE (Lakekeeper UI, and the Lab Console planned as a PKCE public client) cannot work. The Trino web UI
disables itself. Keycloak with `sslRequired=external` would also refuse HTTP from non-private client IPs.
Secure-only cookies (`__Secure-Trino-OAuth2-Token`, Airflow `secure` cookies) break too. HTTP stays an
option only for `*.localhost`, which browsers treat as secure. This confirms the current OQ-3 lean.

**What a beginner has to do (remote server, internal CA):**
1. Get the root: the installer should copy `caddy_data:/caddy/pki/authorities/local/root.crt` to
   `./lakehouse-root-ca.crt` and print instructions (this spike: `./dc.sh exec caddy cat /data/caddy/pki/authorities/local/root.crt`).
2. Import it once per client machine:
   - Windows: double-click the file, then Install → Local Machine → "Trusted Root Certification Authorities" (or `certutil -addstore -f ROOT lakehouse-root-ca.crt`). Chrome and Edge pick it up. Current Firefox also uses the OS store (enterprise roots).
   - macOS: `sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain lakehouse-root-ca.crt`.
   - Linux: Chrome/Chromium use `certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n lakehouse -i lakehouse-root-ca.crt` (what the tester does). Firefox has its own store (Settings → Certificates → Import). CLI tools use `update-ca-certificates`.
   - Laptop CLI clients (trino CLI, dbt, Python) additionally need `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE` or a JVM truststore.
3. That is about 1 file and 1 command or dialog per machine, which is OK for a lab, but it is the kind of step beginners get wrong.

**Implications:**
- **The Caddy CA must be persistent.** It is generated into `caddy_data` on first start, so `down -v` or a volume wipe creates
  a *new* root and every browser has to re-trust. In V3, `caddy_data` must be a protected named volume, never wiped by upgrades (see
  REG_UPGRADE_VOLUME_DATA_LOSS). Better still, the installer generates the root once into a `certs/` directory and gives it to Caddy (`pki` config),
  so it survives reinstalls. The root is valid 10 years; intermediates renew automatically.
- Recommended defaults: `lab.localhost` for single machines (the internal CA still needs trust for HTTPS, but HTTP-on-localhost
  is a valid fallback). For remote servers, internal CA plus a documented import step, and **a real domain with ACME when the server is public**.
  sslip.io hostnames for *public* IPs can get Let's Encrypt certs via HTTP-01. For private IPs like this one they cannot.
- Containers never need browser-style trust as long as the `trust` volume pattern (or talking to Keycloak's internal HTTP port) is used.
  An untested alternative: back-channel calls to `http://keycloak:8080` with Keycloak's fixed `KC_HOSTNAME`. That removes the per-service CA
  plumbing, but not every client lets the discovery URL differ from the issuer (Lakekeeper and Trino validate the issuer).

## Implications for the ADRs

- **ADR-004 (Keycloak): confirmed.** One templated realm JSON with `${ENV}` placeholders, imported by `start --import-realm`, gives
  zero-click bootstrap, including users, groups, clients, secrets and Airflow client roles. The remaining non-declarative step is
  Airflow's UMA model, which needs admin creds and the provider CLI. Options: keep it as a bootstrap-job step as here, or export the
  resulting `authorizationSettings` into the realm template (fully declarative, but must be regenerated whenever the provider version changes).
  Lakekeeper's catalog bootstrap is another bootstrap-job step. `provision-user.sh` becomes "create user + put in group" through the admin REST API,
  as the C4 test already does.
- **ADR-005 (Caddy subdomains): confirmed**, with the network-alias trick: Caddy carries every public hostname as a Docker network alias, so the
  issuer URL is identical inside and outside without hairpin NAT. Needed per service: Superset `ENABLE_PROXY_FIX`, Airflow `--proxy-headers` +
  `[api] base_url`, Trino `process-forwarded`, Keycloak `KC_PROXY_HEADERS=xforwarded`, Lakekeeper `BASE_URI`.
- **ADR-009:** Airflow 3.3 + keycloak provider 0.10.0 works. Its role model is UMA permissions, not claim mapping, and viewer
  can browse admin menus read-only. Superset 6.1 needs authlib + psycopg2 baked in (the image is lean; it runs Python 3.10 in `/app/.venv`).
- **ADR-012:** 6 extra pins, listed above, should move into `versions.env`.
- **Architecture §3 table:** the Trino "group-based access rules" line needs a group provider. `groups-field` is gone in Trino 483.
- **ADR-015 (CI):** `test.sh` is a good model for the CI bootstrap test. Headless Chromium + NSS import + a host-networked driver runs in about 2.5 minutes from scratch.

## How to run

```
rsync -a --delete --exclude .secrets.env --exclude out spikes/s3-sso-bootstrap spikes/versions.env $LAB_SERVER:lakehouse-v3/spikes/
ssh $LAB_SERVER 'cd lakehouse-v3/spikes/s3-sso-bootstrap && ./test.sh'        # full: down -v -> up -> tests
ssh $LAB_SERVER 'cd lakehouse-v3/spikes/s3-sso-bootstrap && FAST=1 ./test.sh' # test the running stack
# teardown (lead): ./dc.sh --profile test down -v
```
Browser access for a person: import `out/caddy-root.crt` and open `https://<svc>.<lab-ip>.sslip.io:18443`
(svc = auth, jupyter, superset, airflow, trino, catalog). User passwords are `LAB_USER_PASSWORD` in the server's `.secrets.env`.
