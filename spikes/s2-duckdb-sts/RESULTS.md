# Spike S-2 — DuckDB via STS-vended credentials

**Date:** 2026-09-25 · **Server:** $LAB_SERVER · **Project:** `v3-s2` · **ADR:** 006 · **Open question:** OQ-1

**Result: PASS.** `./test.sh` passed C0 through C3 and exited 0. It was run twice on the server: a fresh run, then an idempotent re-run against the existing stack.
DuckDB 1.5.5 uses the iceberg extension to ATTACH Lakekeeper's REST catalog. It reads the table Spark wrote using only the
temporary STS credentials that Lakekeeper vends from SeaweedFS 4.47, and it can also INSERT, UPDATE and DELETE with them.
**OQ-1 is answered "yes"**, and neither fallback is needed. The fallbacks were therefore not exercised (see below).

## What was built

S-2 has its own stack. It copies what it needs from S-1 and leaves S-1's files and the running `v3-s1` stack untouched.

| Service | Image | Limits | Notes |
|---|---|---|---|
| postgres | `postgres:${POSTGRES_VERSION}` | 1g / 1 | Lakekeeper DB |
| seaweedfs | `chrislusf/seaweedfs:${SEAWEEDFS_VERSION}` | 2g / 2 | `-s3.iam.config` holds the STS block, role `LakekeeperVended` and policy `WarehouseReadWrite` (the same template as S-1) |
| lakekeeper-migrate / lakekeeper | `quay.io/lakekeeper/catalog:${LAKEKEEPER_VERSION}` | 512m / 1 each | allow-all authz |
| bootstrap *(one-shot, profile `jobs`)* | seaweedfs image | 512m / 1 | `bootstrap/bootstrap.sh`, copied unchanged from S-1. The storage profile has `sts-enabled: true` and `sts-role-arn`, plus remote signing |
| spark-job *(one-shot, profile `jobs`)* | `v3-s1/spark:…` (build context `../s1-catalog-storage/spark`, reused, not rebuilt) | 3g / 2 | `local[2]` with no master or worker. Writes `s2.events` through remote signing |
| duckdb | `v3-s2/duckdb:${DUCKDB_VERSION}` from `python:${PYTHON_IMAGE_TAG}` | 2g / 2 | `pip install duckdb==1.5.5`. The `iceberg`, `httpfs` and `avro` extensions are installed at build time. Idles with `sleep infinity`; the scripts are mounted at `/opt/s2` |

The limits total 9.5 GB including the one-shots, against a 16 GB cap. Measured idle RSS is about 200 MB. There are no host ports.
**Extra pin** (`versions.local.env`): `PYTHON_IMAGE_TAG=3.12.14-slim-bookworm` (already on the server, and it matches `AIRFLOW_PYTHON=3.12`).
DuckDB extension builds follow `DUCKDB_VERSION`: iceberg `45163a28`, httpfs `827222f`, avro `f9d5902`.

## Pass criteria

| # | Criterion | Result | Evidence (from `test.sh`) |
|---|---|---|---|
| 0 | Compose valid, versions only via variables | **PASS** | `config -q OK`. Every `image:`/`FROM` is `${VAR}` and there is no `:latest` |
| 1 | Lakekeeper returns vended **temporary** credentials for the table load | **PASS** | `loadTable(s2.events)` with `X-Iceberg-Access-Delegation: vended-credentials` returns `s3.access-key-id ASIA…`, `s3.session-token` (1715-char JWT), `expiration-time` 3600 s ahead, `s3.endpoint http://seaweedfs:8333/`, `s3.path-style-access true`, `client.refresh-credentials-endpoint`, and a `storage-credentials` prefix equal to the table location. Lakekeeper logs `Fetching new STS credentials … for table <id> at location s3://warehouse/lakehouse/<id> with permissions ReadWriteDelete` |
| 2 | DuckDB reads with **only** the vended creds | **PASS** | The container has no `AWS_*`/S3 env and no `~/.aws`. The rendered compose config and env contain no key-like settings and no admin key values. `duckdb_secrets()` returns **0** secrets before ATTACH. After the read there is **1** secret, created by the extension: `provider=iceberg`, `persistent=False`, `scope=['s3://warehouse/lakehouse/<table-id>']`, key id `ASIA…`. `SELECT count(*), sum(amount)` returns `5 15.0`, matching what Spark wrote. **Negative control:** the same ATTACH with `ACCESS_DELEGATION_MODE 'none'` fails with `HTTP 403 … No credentials are provided`, and DuckDB even falls back to `warehouse.s3.amazonaws.com`, so every endpoint and credential it uses comes from the vended config |
| 3 | DuckDB write (INSERT) | **PASS** | `INSERT INTO lk.s2.events VALUES (100,'duck',1000.0)` gives `6 1015.0`. Spark then reads `100 duck 1000.0`, and the table has a second `append` snapshot (its `engine-name` is NULL, so DuckDB does not stamp one) |
| info | Scope of the vended creds | **table-scoped** | `scripts/scope_probe.py` (S-1's probe, run on `s2.events` in this stack): own read and own PUT return 200. The sibling path, the path outside the warehouse prefix and the bucket list each return 403 |
| info | DuckDB UPDATE / DELETE | **work** | `UPDATE … WHERE id=100` gives `(6, 1016.0)` and `DELETE … WHERE id=100` gives `(5, 15.0)`. DuckDB writes delete files and does not delete S3 objects, so Lakekeeper's `s3.delete-enabled=false` does not get in the way |

### The DuckDB session that works
```sql
LOAD httpfs; LOAD avro; LOAD iceberg;          -- pre-installed in the image
ATTACH 'lakehouse' AS lk (TYPE iceberg, ENDPOINT 'http://lakekeeper:8181/catalog', AUTHORIZATION_TYPE 'none');
-- ACCESS_DELEGATION_MODE defaults to 'vended_credentials'. No CREATE SECRET for S3 is needed or used.
SELECT * FROM lk.s2.events;
```
DuckDB reads `s3.endpoint`, `s3.path-style-access`, `s3.region` and the session token from the loadTable config, so the
client needs no S3 settings at all. This matters for the workspace image: the catalog URL (and, in Phase 1,
an OAuth2 token) is enough.

## Fallbacks (not needed, not exercised)
STS works, so neither fallback was built. For the record:
- (a) DuckDB through Trino: Trino in S-1 already uses the same vended STS path, so this fallback relies on the same mechanism
  and adds nothing.
- (b) A read-only scoped SeaweedFS key: this would put a static key in the workspace, which is exactly what ADR-006 removes. It is only worth keeping
  as a documented emergency option.

## Surprises
1. **Nothing had to be fought.** DuckDB 1.5.5 worked on the first try with the S-1 storage profile. The earlier worry
   (OQ-1: "reports of an incomplete STS implementation") does not apply to SeaweedFS 4.47 for `AssumeRole` with a session policy.
2. With allow-all authz, Lakekeeper vends **ReadWriteDelete** for every load. Read-only vending for `SELECT`-only
   principals needs real authz (OpenFGA, OQ-5) and was not tested.
3. Lakekeeper appears to cache STS credentials: the test made several loadTable calls but logged only 1 `Fetching new STS credentials`.
   A cache means fewer AssumeRole calls, but a revoked grant may stay usable until the cached credentials expire (at most 1 h).
4. The DuckDB secret is in-memory and scoped to the table prefix. Each table gets its own internal secret.
5. `SHOW ALL TABLES` lists the Iceberg table with column `__` / `UNKNOWN` until it is first read (lazy schema load). This is cosmetic.

## Not verified
- **Credential expiry and refresh.** No DuckDB session was kept past the 1 h token life. Lakekeeper advertises
  `client.refresh-credentials-endpoint`, but whether DuckDB's extension refreshes (or re-loads the table) in a long-lived notebook
  kernel is untested. Phase 1 should add a test with `sts-token-validity-seconds` set to about 120.
- OAuth2 (`AUTHORIZATION_TYPE 'oauth2'`) against Lakekeeper with Keycloak tokens. That belongs to S-3 and Phase 1.
- Scoping against a second real table (the probe uses a sibling path, as in S-1).

## Implications for the ADRs
- **ADR-006 → Accepted (for DuckDB).** Lakekeeper-vended SeaweedFS STS credentials work for DuckDB reads and writes (INSERT,
  UPDATE, DELETE). They are table-scoped and expire in 1 h or less. Combined with S-1's finding that Trino 483 cannot remote-sign, the proposed wording is:
  *Spark (and PyIceberg) use remote signing. Trino and DuckDB use vended table-scoped STS credentials. No engine holds
  static S3 keys.* SeaweedFS STS (the `-s3.iam.config` file with role, policy and signing key) is mandatory in core. Drop the ADR's
  "if not" fallback branch, or keep it only as a note.
- **OQ-1: closed, yes** on SeaweedFS 4.47 with Lakekeeper v0.13.6 and DuckDB 1.5.5.
- **ADR-007 (workspace):** pre-install the DuckDB `iceberg`/`httpfs`/`avro` extensions at image build time, with the extension builds
  tied to `DUCKDB_VERSION`. The only client config needed is the ATTACH line above plus auth, and no S3 settings.
- **ADR-012:** add `PYTHON_IMAGE_TAG` (or reuse the workspace base) if a standalone DuckDB/python image is kept.
- Follow-ups for Phase 1: an STS refresh test, read-only vending under OpenFGA, and a trust policy narrowed to the Lakekeeper identity (as in S-1).

## Files
`compose.yaml`, `versions.local.env`, `gen-secrets.sh`, `.gitignore`, `bootstrap/bootstrap.sh` (from S-1),
`seaweedfs/iam.template.json` (from S-1), `spark/{spark-defaults.conf,run-sql.sh}`, `sql/0{1,2}_*.sql`,
`duckdb/{Dockerfile,install-ext.py}`, `scripts/{probe_vended.py,duck_s2.py,duck_dml.py,scope_probe.py}`, `test.sh`.

The stack is left running (postgres, seaweedfs, lakekeeper, duckdb). Try it with
`docker compose -p v3-s2 --env-file ../versions.env --env-file versions.local.env exec duckdb python /opt/s2/duck_s2.py`.
Clean up with `docker compose -p v3-s2 down -v`.
