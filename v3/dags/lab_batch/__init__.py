"""Helpers for the lab DAGs: the batch service identity and running jobs (ADR-017).

Every lab DAG acts as `lab-batch`, a Keycloak client-credentials account (bootstrap/
batch_client.py), never as the person who triggered it. Airflow's run records who triggered
it (dag_run.triggering_user_name); log_trigger() also writes it into the task log.

Tokens: `batch_token()` fetches a fresh access token from Keycloak's internal endpoint. Short
jobs (Trino queries, dbt, the notebook) get one right before they start. Spark does not take
a token at all: its session gets the client credential, so the Iceberg client and the S3
signer re-fetch tokens themselves for as long as the job runs.

Jobs run in the /opt/lab/jobs virtualenv (images/airflow), as subprocesses whose output is
streamed into the task log. Their scripts live in dags/jobs/ (ignored by the DAG parser).

Stdlib only: this module is imported when DAG files are parsed.
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

KC_TOKEN_URL = "http://keycloak:8080/realms/lakehouse/protocol/openid-connect/token"
JOBS_PYTHON = "/opt/lab/jobs/bin/python"
JOBS_BIN = "/opt/lab/jobs/bin"
DAGS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(DAGS_DIR, "jobs")
NOTEBOOKS_DIR = os.path.join(DAGS_DIR, "notebooks")
DATA_DIR = "/opt/lab/data"

# What every lab DAG shares: no schedule (they run when triggered), one run at a time.
DEFAULT_ARGS = {"owner": "lab", "retries": 0}
TAGS = ["lab", "lab-batch"]


def client_id():
    return os.environ.get("LAB_BATCH_CLIENT_ID", "lab-batch")


def _secret():
    s = os.environ.get("OIDC_CLIENT_SECRET_BATCH")
    if not s:
        raise RuntimeError("OIDC_CLIENT_SECRET_BATCH is not set (only the scheduler has it)")
    return s


def claims(token):
    """The token's claims (not verified: Trino and Lakekeeper verify it)."""
    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def batch_token():
    """A fresh client-credentials access token for lab-batch. Returns (token, claims)."""
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": client_id(),
        "client_secret": _secret(), "scope": "openid"}).encode()
    req = urllib.request.Request(KC_TOKEN_URL, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        tok = json.load(r)["access_token"]
    return tok, claims(tok)


def principal(c):
    """The Trino principal of a token (Trino's principal-field is preferred_username)."""
    return c.get("preferred_username") or f"service-account-{client_id()}"


def log_trigger(context):
    """Write who triggered the run, and as whom it acts, into the task log."""
    dr = context.get("dag_run")
    who = getattr(dr, "triggering_user_name", None) or "(scheduler)"
    print(f"[lab] run {dr.run_id if dr else '?'} triggered by {who}; acting as {client_id()}",
          flush=True)
    return who


def job_env(extra=None, with_secret=False):
    """Environment for a job subprocess. The client secret is passed only to jobs that must
    re-fetch tokens themselves (Spark); the others get a token."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("AIRFLOW") and k not in ("OIDC_CLIENT_SECRET_BATCH",)}
    env["PATH"] = f"{JOBS_BIN}:{env.get('PATH', '/usr/bin:/bin')}"
    env["PYTHONPATH"] = DAGS_DIR
    if with_secret:
        env["OIDC_CLIENT_SECRET_BATCH"] = _secret()
    env.update(extra or {})
    return env


def run_job(args, env, cwd=None):
    """Run a job command, streaming its output into the task log. Raises on failure."""
    print(f"[lab] $ {' '.join(args)}", flush=True)
    t0 = time.time()
    p = subprocess.Popen(args, env=env, cwd=cwd, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, bufsize=1)
    try:
        for line in p.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
        rc = p.wait()
    finally:
        # The task was stopped (marked failed, timed out, killed): stop the job too, so it does
        # not keep running (a Spark job would otherwise hold the shared cluster's cores).
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=60)
            except subprocess.TimeoutExpired:
                p.kill()
    print(f"[lab] exit {rc} after {time.time() - t0:.1f}s", flush=True)
    if rc != 0:
        raise RuntimeError(f"{args[0]} exited {rc}")
    return rc


def run_python_job(script, *args, env=None):
    return run_job([JOBS_PYTHON, os.path.join(JOBS_DIR, script), *args], env or job_env())
