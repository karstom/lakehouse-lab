"""Airflow cluster policy for user DAGs (CONTRACT Phase 4, "E3 needs ... user DAGs").

Mounted at $AIRFLOW_HOME/config (compose/airflow.yaml), which Airflow puts on sys.path and
imports `airflow_local_settings` from, in the dag-processor (where import errors are recorded
and shown in the UI) and in the scheduler (which parses the file again to run a task).

User DAGs live in the shared volume `<project>_dags-user`: engineers and lab admins see it
read-write at ~/airflow-dags in their workspace, and Airflow sees it read-only at
<dags folder>/user/. The rules for a DAG defined in a file under that folder:

  * the file must be inside the author's own folder: user/<username>/...  (any depth);
  * its dag_id must start with  u_<username>_  (the folder name is the username).

A DAG that breaks a rule raises AirflowClusterPolicyViolation. Airflow then refuses the
whole file and lists it under "DAG Import Errors" with the message below, so the author sees
what to fix. DAGs outside user/ (the lab's own DAGs in v3/dags) are not affected, except that
the `u_` prefix is reserved for user DAGs.

The policy also sets the owner of every task in a user DAG to the username and adds the tag
`user:<username>`, so the UI's owner column and tag filter show whose DAG it is.

What this does NOT do (documented in the E3 lesson and PHASE4 results): every workspace runs
as the same Unix user, so a file system cannot keep engineers out of each other's folders,
and a user DAG runs with Airflow's own identity (lab-batch for data). Engineers and lab
admins are trusted with that; analysts and viewers never get the volume.
"""
import os
import re

try:  # Airflow's own exception type, so Airflow reports it as an import error
    from airflow.exceptions import AirflowClusterPolicyViolation
except ImportError:  # unit tests without Airflow installed
    class AirflowClusterPolicyViolation(Exception):
        pass

USER_DIR = "user"
USER_PREFIX = "u_"
# A folder name that can be a lab username and part of a dag_id ([A-Za-z0-9_.-] in Airflow).
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")


def _dags_folder():
    folder = os.environ.get("AIRFLOW__CORE__DAGS_FOLDER")
    if not folder:
        try:
            from airflow.configuration import conf
            folder = conf.get("core", "dags_folder")
        except Exception:  # noqa: BLE001 - no Airflow (unit tests)
            folder = "/opt/lab/dags"
    return os.path.normpath(os.path.abspath(folder))


def user_of(fileloc, dags_folder=None):
    """(is_user_file, username or None) for a DAG file path.

    The path is normalised but symlinks are NOT resolved: the rule is about where the file
    sits in the user folder, which is what the author sees in ~/airflow-dags."""
    root = os.path.join(dags_folder or _dags_folder(), USER_DIR)
    path = os.path.normpath(os.path.abspath(fileloc or ""))
    if os.path.commonpath([root, path]) != root:
        return False, None
    rel = os.path.relpath(path, root).split(os.sep)
    if len(rel) < 2:                     # directly in user/, not in a username folder
        return True, None
    return True, rel[0]


def check(dag_id, fileloc, dags_folder=None):
    """The username the DAG belongs to (None for a lab DAG), or raise the violation."""
    is_user, name = user_of(fileloc, dags_folder)
    if not is_user:
        if dag_id.startswith(USER_PREFIX):
            raise AirflowClusterPolicyViolation(
                f"DAG '{dag_id}': ids starting with '{USER_PREFIX}' are reserved for user DAGs "
                f"in ~/airflow-dags/<username>/.")
        return None
    where = os.path.basename(fileloc or "?")
    if name is None:
        raise AirflowClusterPolicyViolation(
            f"DAG '{dag_id}' in {where}: user DAG files must be inside your own folder, "
            f"~/airflow-dags/<your username>/, not directly in ~/airflow-dags/.")
    if not USERNAME_RE.match(name):
        raise AirflowClusterPolicyViolation(
            f"DAG '{dag_id}': '{name}' is not a username folder. Put your DAG files in "
            f"~/airflow-dags/<your username>/ (lower case, as you log in).")
    want = f"{USER_PREFIX}{name}_"
    if not dag_id.startswith(want) or len(dag_id) == len(want):
        raise AirflowClusterPolicyViolation(
            f"DAG '{dag_id}' in {name}/{where}: the dag_id of a DAG in {name}/ must start with "
            f"'{want}', for example '{want}my_pipeline'. Rename the dag_id and save the file.")
    return name


def _add_tag(dag, tag):
    tags = getattr(dag, "tags", None)
    if tags is None:
        dag.tags = {tag}
    elif hasattr(tags, "add"):
        tags.add(tag)
    elif tag not in tags:
        tags.append(tag)


def dag_policy(dag):
    name = check(dag.dag_id, getattr(dag, "fileloc", None))
    if name is None:
        return
    for t in getattr(dag, "tasks", ()):
        t.owner = name
    _add_tag(dag, f"user:{name}")
