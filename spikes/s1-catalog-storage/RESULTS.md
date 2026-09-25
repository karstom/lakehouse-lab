# Spike S-1 — Catalog + storage (Lakekeeper + SeaweedFS + Spark 4.1 + Trino)

**Date:** 2026-09-25 · **Server:** $LAB_SERVER · **Project:** `v3-s1` · **ADRs:** 001, 002, 003, 006

**Result: PARTIAL. Criterion 3 is not met for Trino.** C1, C2, C3a (no static keys) and C4 pass.
C3b ("storage access is via Lakekeeper remote signing") passes for Spark and **fails for Trino**. Trino 483
has no S3 remote-signing support (jar evidence below). It reads and writes through **table-scoped STS credentials vended
by Lakekeeper** (SeaweedFS `AssumeRole`). `./test.sh` reports `C3b FAIL` and `OVERALL: PARTIAL` and **exits 2**
(0 means all pass, 2 means only C3b failed with everything else passing, 1 means any other failure). An earlier round reported "4/4 PASS" and exited 0 here.
That was wrong, and test.sh now asserts remote signing separately for each engine.

Repair-round run (2026-09-25, on the running stack): `C1 pass, C2 pass, C3a pass, C3b fail, C4 pass`, `EXIT=2`.

## What was built

| Service | Image (all from `versions.env`) | Limits | Notes |
|---|---|---|---|
| postgres | `postgres:${POSTGRES_VERSION}` | 1g / 1 cpu | Lakekeeper DB |
| seaweedfs | `chrislusf/seaweedfs:${SEAWEEDFS_VERSION}` | 2g / 2 | `weed server` all-in-one (master+volume+filer+S3), `-s3.iam.config` for STS |
| lakekeeper-migrate | `quay.io/lakekeeper/catalog:${LAKEKEEPER_VERSION}` | 512m / 1 | `migrate`, one-shot |
| lakekeeper | same | 512m / 1 | `serve`, `AUTHZ_BACKEND=allowall` |
| bootstrap | seaweedfs image (has `weed shell` + `curl`) | 512m / 1 | `bootstrap/bootstrap.sh`, one-shot, idempotent |
| spark-master / spark-worker | `v3-s1/spark` built from `apache/spark:${SPARK_IMAGE_TAG}` | 1g/1, 3g/4 | Iceberg jars baked in at build time (`spark/Dockerfile`, `spark/fetch-jars.sh`) |
| spark-job | same image, profile `jobs` | 2g / 2 | `spark-sql -f` driver, run with `compose run --rm` |
| trino | `trinodb/trino:${TRINO_VERSION}` | 4g / 4 | catalog `lakehouse` = Iceberg REST → Lakekeeper |

Total limits: 14.5 GB, counting the one-shot services (the cap is 16 GB). Measured idle RSS is about 1.3 GB (Trino 770 MB, Spark 400 MB, others under 80 MB each).
No host ports. No extra version pins (`versions.local.env` is empty).

**Secrets:** `gen-secrets.sh` generates `secrets/` once. It is gitignored and not rsynced. Files:
`pg.env` for Postgres and Lakekeeper, `s3-admin.env` for the SeaweedFS admin keys, and `seaweedfs-iam.json` for the STS signing key.
Only the one-shot `bootstrap` container receives `s3-admin.env`. It creates the SeaweedFS identity
(`s3.configure`), creates the bucket (`s3.bucket.create`), and passes the keys to Lakekeeper once as the warehouse
storage credential. After that, only SeaweedFS and Lakekeeper hold static keys (ADR-006, HARD RULE 7).

## Pass criteria

| # | Criterion | Result | Evidence (from `test.sh`) |
|---|---|---|---|
| 1 | Spark creates namespace + Iceberg table and inserts rows via REST | **PASS** | `S1_SPARK_COUNT 5`, `S1_SPARK_SNAPSHOTS 1`; Lakekeeper logged 10 distinct `/v1/aws/s3/sign` requests during the job |
| 2 | Trino reads, UPDATEs, DELETEs; Spark sees the new snapshots | **PASS** | Trino `count=5`, `UPDATE: 2 rows`, `DELETE: 2 rows`, then `3 rows, sum 305.0`. Spark then reads rows `1 click 100.0 / 2 click 200.0 / 5 buy 5.0` and snapshots `append(false) / overwrite(trino) / delete(trino)` |
| 3a | No static S3 keys in Spark/Trino config | **PASS** | test.sh greps the rendered `compose config` for the engine services, the mounted `spark-defaults.conf` in master and worker, Trino's `catalog/*.properties` and `config.properties`, and the container env. It found 0 key-like settings in 258 lines, and the admin key values do not appear |
| 3b | Storage access via Lakekeeper **remote signing** (all engines) | **FAIL** (Spark PASS, Trino FAIL) | Spark: 10 distinct `/v1/aws/s3/sign` requests per run, and `remote-signing` delegation returns `s3.remote-signing-enabled=true`, `s3.signer.uri`, and no keys. Trino: **0** sign requests. `test.sh` asserts `s2 > 0` and fails with "Trino 483 supports only vended-credentials" |
| 3c | *(fallback, informational)* Trino's vended STS credentials are table-scoped | **table-scoped** | `scope_probe.py` uses the vended creds (SigV4 + session token): own metadata GET 200, own-prefix PUT 200, sibling path `warehouse/lakehouse/not-this-table/` PUT **403**, `warehouse/outside-warehouse-prefix/` PUT **403**, bucket ListObjectsV2 **403** |
| 4 | `docker compose config -q` passes; versions only via variables | **PASS** | `config -q OK`; every `image:`/`FROM` is `${VAR}`; no `:latest`. Iceberg jar versions come from build args (`SPARK_VERSION` → minor `4.1` is derived in `fetch-jars.sh`) |

### Why Trino cannot remote-sign (3b): jar evidence
These were extracted from the `trinodb/trino:483` image in the running `v3-s1-trino-1` container with `jar xf`:
- `io.trino_trino-iceberg-483.jar`: the only access-delegation strings in `io/trino/plugin/iceberg/catalog/rest/IcebergRestCatalogPropertiesProvider.class`
  are `header.X-Iceberg-Access-Delegation` and `vended-credentials`. The header is set only when
  `iceberg.rest-catalog.vended-credentials-enabled=true`. No value requests `remote-signing`.
- `io.trino_trino-filesystem-s3-483.jar`: `S3FileSystemConfig$SignerType` offers only AWS SDK signers
  (`Aws4Signer`, `AwsS3V4Signer`, `Aws4UnsignedPayloadSigner`, `AsyncAws4Signer`, `EventStreamAws4Signer`).
- Neither jar contains `S3V4RestSigner` or `remote-signing`.
- The accepted `iceberg.rest-catalog.*` properties are `uri, prefix, warehouse, nested-namespace-enabled, security, session,
  *-timeout, vended-credentials-enabled, view-endpoints-enabled, case-insensitive-name-matching*, parent-namespace,
  http-headers, sigv4*`. None of them sets a signer URI.
- Behaviour: with remote signing only (`sts-enabled=false`), every Trino query fails with
  `IllegalStateException: Failed to initialize the vended credentials from the provided fileIoProperties`.
- Upstream: [trinodb/trino#21189 "Support remote-signing in Trino Iceberg connector"](https://github.com/trinodb/trino/issues/21189)
  tracks the feature. It has not shipped as of Trino 483. `versions.local.env` pins no newer Trino, because no released version has the feature.
  **Re-check #21189 when `TRINO_VERSION` is bumped.** If a release adds remote signing, drop `sts-enabled` for Trino
  and flip `trino_rs` in test.sh.

**Fallback in place:** `sts-enabled=true` on the same storage profile. Lakekeeper calls SeaweedFS STS `AssumeRole`
and gives Trino short-lived credentials. Those credentials are table-scoped (3c) and hold no static keys. This meets the *intent* of ADR-006,
but not its letter.

### Vended-credential scope (3c)
The `LakekeeperVended` role policy (`seaweedfs/iam.template.json`, `WarehouseReadWrite`) is bucket-wide
(`arn:aws:s3:::warehouse/*`). Even so, the credentials vended for `s1.events` are **denied** outside the table location:

```
SCOPE own-read 200 ALLOWED        (table metadata file)
SCOPE own-put 200 ALLOWED         (warehouse/lakehouse/<table-id>/scope-probe.txt, deleted right after)
SCOPE sibling-put 403 DENIED      (warehouse/lakehouse/not-this-table/…)
SCOPE outside-put 403 DENIED      (warehouse/outside-warehouse-prefix/…)
SCOPE bucket-list 403 DENIED      (ListObjectsV2 on warehouse/)
SCOPE_VERDICT table-scoped
```
The role policy allows all of those paths, so the 403s must come from the **session policy that Lakekeeper attaches
to `AssumeRole`**, and SeaweedFS 4.47 enforces it. The effective permission is (role policy ∩ session policy), which is the table
prefix. The role stays bucket-wide as a ceiling. The blast radius of one leaked vended token is therefore one table for at most 1 h
(`sts-token-validity-seconds`). A leak of the role itself would be bucket-wide, but only the Lakekeeper identity can
assume it once the trust policy is narrowed (see below).
Caveats: 3c tests a sibling *path* in the same namespace, not a second real table. The earlier `curl --aws-sigv4` 403 was a probe bug.
The stdlib SigV4 signer in `scope_probe.py`, which signs `x-amz-security-token`, works.

## Lakekeeper storage profile that SeaweedFS needed

```json
{ "type": "s3", "flavor": "s3-compat", "bucket": "warehouse", "key-prefix": "lakehouse",
  "endpoint": "http://seaweedfs:8333", "region": "us-east-1", "path-style-access": true,
  "remote-signing-enabled": true, "remote-signing-url-style": "path",
  "sts-enabled": true, "sts-role-arn": "arn:aws:iam::role/LakekeeperVended", "sts-token-validity-seconds": 3600 }
```
- `flavor: s3-compat` + `path-style-access: true` + `remote-signing-url-style: path`. SeaweedFS is addressed
  by service name, so virtual-host addressing is not possible.
- `region` is required, and any value works (`us-east-1`). Lakekeeper passes it to clients as `client.region`/`s3.region`.
  Spark needs no region setting of its own.
- `sts-enabled: true` needs `sts-role-arn`. Otherwise the default `flavor: aws` would try real AWS STS. `sts-endpoint` can be left out
  (the S3 endpoint is used).
- The storage credential is `credential-type: access-key` with the SeaweedFS admin identity (Read, Write, List, Tagging, Admin).
  Lakekeeper validates the profile on create and update by writing a test object (HTTP 201/200).
- Lakekeeper defaults `push-s3-delete-disabled` to `true`, so clients receive `s3.delete-enabled=false`.

SeaweedFS side (`seaweedfs/iam.template.json`, rendered to `secrets/seaweedfs-iam.json`, passed with `-s3.iam.config`):
an `sts` block (issuer and a base64 signing key), role `LakekeeperVended` (trust policy: `sts:AssumeRole`, Principal
`AWS:*`), and attached policy `WarehouseReadWrite` (Get/Put/Delete/List on `warehouse/*`). Without this file,
STS returns `ServiceUnavailable`. With it, `AssumeRole` signed by the admin key returns `ASIA…` credentials plus a JWT session
token, and the static `s3.configure` identity keeps working alongside it.

## Surprises
1. **`DROP TABLE … PURGE` from Spark breaks under remote signing.** Iceberg 1.11's Spark catalog deletes files
   on the client side after the catalog drop. Lakekeeper's signer then rejects the requests with `BadRequestException: Table does not exist or user
   does not have permission … at location s3://warehouse/…/metadata/…`. The failure was intermittent in `test.sh`: it happened only
   when the table already existed. The spike uses plain `DROP TABLE` (Lakekeeper handles the files). Lessons and docs must
   not teach `PURGE` from Spark.
2. **Trino cannot use remote signing** (see above). This means STS is needed in S-1 already, not only for DuckDB in S-2.
3. `LAKEKEEPER__PG_PORT` must be set explicitly when you use `PG_HOST_R/W` + `PG_USER/PASSWORD` instead of a URL
   ("A connection string or postgres port must be provided").
4. SeaweedFS enforces auth only after the first identity exists (anonymous `GET` returned 403 after `s3.configure`).
   Until the bootstrap runs, the bucket store is open. Phase 1 should start SeaweedFS with an identity config
   already in place.
5. SeaweedFS logs `Registered IAM gRPC service on filer (unauthenticated; set jwt.filer_signing.key in security.toml …)`.
   Phase 1 needs a `security.toml` with JWT keys before the stack runs on any shared network.
6. `weed shell` waits forever if the master is unreachable, so the bootstrap must run only after the S3 healthcheck passes.
7. Lakekeeper's `/v1/config` returns the warehouse `prefix` under `defaults`, not `overrides`.

## Not verified here
- Scoping against a second *real* table, and read-only scoping for `SELECT`-only principals. This needs non-allow-all authz, which belongs to S-2 or Phase 1.
- STS credential refresh after expiry (1 h) during long Trino queries. Lakekeeper advertises
  `client.refresh-credentials-endpoint`, but nothing here exercises it.
- The trust policy `Principal: AWS:*` is spike-grade. Scope it to the Lakekeeper identity. Optionally, narrow the role to
  `warehouse/lakehouse/*` as defence in depth.

## Implications for the ADRs
- **ADR-006, proposed amendment:** "remote signing for all engines" cannot be met with Trino 483. Proposed wording:
  *Spark and PyIceberg use Lakekeeper remote signing. Trino (and DuckDB, per S-2) use Lakekeeper-vended, table-scoped STS
  credentials (SeaweedFS `AssumeRole` + a Lakekeeper session policy, ≤1 h). No engine holds static S3 keys.* Consequences:
  SeaweedFS STS (IAM config file, role, signing key) becomes mandatory in the core profile, because Trino is core. The role's trust policy
  must name only the Lakekeeper identity. Revisit when trinodb/trino#21189 ships. S-1 shows STS works on SeaweedFS 4.47 and
  that SeaweedFS enforces the session policy (3c).
- **ADR-001:** SeaweedFS 4.47 is confirmed as a working Lakekeeper backend for both signing modes. Add to the ADR: the IAM/STS config file, the
  filer JWT `security.toml`, and "identity before first start".
- **ADR-002:** Lakekeeper 0.13.6 with allow-all authz works. The bootstrap uses the management API (`/management/v1/bootstrap`,
  `/warehouse`, `/warehouse/{id}/storage`), and the Phase 1 `bootstrap` job can reuse this flow.
- **ADR-003:** Spark 4.1.3 + `iceberg-spark-runtime-4.1_2.13:1.11.0` + `iceberg-aws-bundle:1.11.0` baked into the image
  works. It needs no `hadoop-aws` or AWS SDK jars, because S3FileIO comes from the aws-bundle. This retires the hadoop-aws
  entries of `WATCH_ICEBERG_VERSION_SITES`. Trino 483 Iceberg REST works, including UPDATE/DELETE.

## Files
`compose.yaml`, `versions.local.env`, `gen-secrets.sh`, `.gitignore`, `bootstrap/bootstrap.sh`,
`seaweedfs/iam.template.json`, `spark/{Dockerfile,fetch-jars.sh,spark-defaults.conf,run-sql.sh}`,
`trino/{jvm.config,catalog/lakehouse.properties}`, `sql/0{1,2,3}_*.sql`, `probe_catalog.py`, `scope_probe.py`, `test.sh`.

Run: see the header of `test.sh`. The stack is left running. Clean up with `docker compose -p v3-s1 down -v`.
