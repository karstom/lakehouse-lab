#!/bin/sh
# One-shot `airflow-dags-user` (compose/airflow.yaml): make the user-DAG volume writable for
# workspaces (CONTRACT Phase 4, "user DAGs").
#
# Compose creates <project>_dags-user empty and owned by root. Workspaces run as jovyan
# (uid 1000, gid 100, images/workspace) and mount it read-write at ~/airflow-dags; Airflow
# (uid 50000) mounts it read-only and only needs to read it. So the volume's top directory
# belongs to the workspace user, mode 0755. Only that directory is changed: what users
# created inside is left alone. Idempotent.
set -eu

dir=${1:?usage: dags-user-init.sh DIR}
uid=${LAB_WORKSPACE_UID:-1000}
gid=${LAB_WORKSPACE_GID:-100}

chown "$uid:$gid" "$dir"
chmod 0755 "$dir"
echo "dags-user: $dir is owned by $uid:$gid, mode 0755"
