# Anti-Patterns

> Things the AI should **never** generate for this project. These prevent wasted
> correction cycles — the AI gets it right on the first attempt instead of
> generating wrong code that must be reviewed and rejected.
>
> These are different from Invariants:
> - **Invariants** = rules about how the code must behave at runtime
> - **Anti-patterns** = rules about what the AI should never write

---

<!-- Add your anti-patterns below. Use clear, imperative language. -->

## Debugging / Recurring-Bug Anti-Patterns

- **NEVER add the Nth place to set, preserve, or re-stamp the same derived flag** when `REGRESSED_N_TIMES ≥ 2`. More than ~2 write sites for a single derived value means the code should read the source of truth directly instead of maintaining a mirror. Each new write site is a future recurrence.

- **NEVER add belt-and-suspenders compensating guards** (a second unreliable check OR-ed in to paper over a first one you don't trust). If you don't trust check A, fix A — don't add check B to catch A's failures. Two unreliable checks in series fail in more ways than one reliable check.

- **NEVER fix a recurring regression without clearing the Root-Cause Gate** (`REGRESSED_N_TIMES ≥ 2`). Same-class patches (another guard, stamp, or preserve site for the same derived value) are banned until the three-question gate in `HOW_TO_UPDATE.md` is answered and the `root_cause` field is written to the node.

## Lakehouse Lab Anti-Patterns

- **NEVER write a credential literal** (`minio123`, `admin`, default tokens) in scripts, DAGs, notebooks, tests or compose defaults — read it from the environment populated by `.env` (INV_ENV_IS_CREDENTIAL_SOURCE).
- **NEVER write `$VAR` for a container-side variable inside a compose `command:`/`entrypoint:` block** — use `$$VAR`; run `docker compose config -q` after every compose edit (INV_COMPOSE_DOLLAR_ESCAPING).
- **NEVER add more inline bash logic to compose command blocks** — put it in a script under `scripts/` and mount it, so ShellCheck can see it (REG_COMPOSE_INLINE_SHELL).
- **NEVER `pip install pyspark`, or change pyarrow, in the Jupyter container** — the Spark-matched image's versions are authoritative (INV_SPARK_VERSION_ALIGNMENT).
- **NEVER bump one Iceberg/hadoop-aws/AWS SDK version string alone** — change all five sites in WATCH_ICEBERG_VERSION_SITES together.
- **NEVER add a new image with `:latest`** — pin a version tag (WATCH_UNPINNED_IMAGES).
- **NEVER emit notebooks, DAGs or Python from an unquoted heredoc**, and never duplicate a file that exists in `templates/` — copy the template (INV_TEMPLATES_ARE_REAL_FILES).
- **NEVER rename, add or remove a named volume in one place only** — compose `name:`, `create_named_volumes` and `migrate-to-named-volumes.sh` must change together (INV_VOLUME_NAMES_SINGLE_SOURCE).
- **NEVER use `sudo` in init scripts** — they already run as root and sudo is not installed (DEC_REMOVE_SUDO_DEPENDENCIES_FROM_ALPINE_6EF3).
- **NEVER add another copy of host-IP detection** — reuse `detect_host_ip` (WATCH_DUPLICATED_HOST_IP_DETECTION).

## V3 Anti-Patterns (from Phase 0 spikes)

- **NEVER write Spark `DROP TABLE … PURGE` against Lakekeeper** in V3 code or lessons. Spark deletes files on the client side after the catalog drop, and the signer rejects those requests. Use a plain `DROP` (DEC_V3_CATALOG_VENDED_STORAGE_ACCESS).
- **NEVER configure Trino for Iceberg remote signing, or give it static S3 keys.** Trino 483 only supports vended credentials; use `X-Iceberg-Access-Delegation: vended-credentials` through Lakekeeper.
- **NEVER put Caddy's internal CA in a volume that `down -v` or upgrades can wipe.** A new root makes every browser re-trust it (DEC_V3_KEYCLOAK_SSO_SUBDOMAINS).
- **NEVER rely on `SSL_CERT_FILE` for JupyterHub OAuthenticator.** It uses pycurl; pass the CA through `http_request_kwargs`.

<!-- EXAMPLES (delete these when you add real entries):

## Coding Anti-Patterns
- NEVER use `any` type in TypeScript — always use explicit types or `unknown`
- NEVER use string concatenation for SQL — always use parameterized queries
- NEVER import from internal paths of a package (e.g., `lib/internal/utils`) — use the public API only

## Testing Anti-Patterns
- NEVER generate mock data inline — always use the test fixture factory in `tests/fixtures/`
- NEVER skip error case tests — every function that can throw must have a failure test

## Architecture Anti-Patterns
- NEVER add direct database calls outside the data layer (`src/data/`)
- NEVER put business logic in API route handlers — delegate to service classes

-->
