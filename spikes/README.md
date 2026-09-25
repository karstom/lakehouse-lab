# V3 Phase 0 Spikes

Throwaway stacks that validate V3 decisions before Phase 1 (see `docs/v3/ROADMAP.md`).
Spike code is kept for reference; Phase 1 rebuilds it properly.

## Layout

```
spikes/
  versions.env            # shared pins — read-only for spikes
  s1-catalog-storage/     # S-1  Lakekeeper + SeaweedFS + Spark 4.1 + Trino, remote signing
  s2-duckdb-sts/          # S-2  DuckDB via STS-vended credentials (builds on S-1)
  s3-sso-bootstrap/       # S-3  Keycloak realm import -> JupyterHub, Superset, Airflow 3, Trino, Lakekeeper
  s4-workspace-image/     # S-4  lakehouse-workspace image
```

Each spike directory contains: `compose.yaml` (and any Dockerfiles/config), a `test.sh`
that exits 0 only when the pass criteria are met, `versions.local.env` for extra pins
(if any), and `RESULTS.md`.

## Where spikes run

`$LAB_SERVER` is the Docker host the spikes ran on (a LAN machine reachable by passwordless ssh).
For S-3, set `LAB_DOMAIN` in `s3-sso-bootstrap/lab.env` to that host's IP with dashes, e.g. `10-0-0-5.sslip.io`.

On the shared server `$LAB_SERVER` (passwordless `ssh`), under `~/lakehouse-v3/spikes/<spike>/`.
Sync with `rsync -a --delete spikes/<spike>/ spikes/versions.env ...` — see each spike's `test.sh`.

## Hard rules (the server runs production workloads)

1. Compose project name **`v3-<spike>`** (e.g. `docker compose -p v3-s1 ...`). Never touch
   the `lakehouse-lab` project, its containers, networks, or `lakehouse-lab_*` volumes.
2. **No host ports**, except when a spike needs browser-style access: then only in
   **18000–18999**. Taken on the host: 22, 53, 111, 2049, 5432, 7077, 8080, 9000–9060, 11434.
3. **`mem_limit` and `cpus`** on every container. Total per spike ≤ 16 GB.
4. Cleanup only with `docker compose -p v3-<spike> down -v`. No `docker system prune`,
   no global `docker rm/rmi`, no `sudo`.
5. Versions only via `versions.env` / `versions.local.env` variables. No `:latest`.
6. No logic in compose `command:`/`entrypoint:` beyond invoking a script file.
7. Engines never get static S3 keys (ADR-006); only SeaweedFS admin and Lakekeeper's storage
   profile hold them.

## Shared hostname for SSO testing (S-3)

`LAB_DOMAIN=<lab-ip>.sslip.io`, Caddy on host port **18443** (HTTPS, Caddy internal CA).
Services: `https://<svc>.<lab-ip>.sslip.io:18443`. sslip.io resolves to $LAB_SERVER
from both browsers and containers, so the OIDC issuer URL is identical everywhere.
