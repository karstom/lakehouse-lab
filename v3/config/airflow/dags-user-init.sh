#!/bin/sh
# One-shot `airflow-dags-user` (compose/airflow.yaml): prepare the user-DAG volume
# (CONTRACT Phase 4, "user DAGs").
#
# The volume holds one folder per user, <username>/. JupyterHub creates a user's folder
# (owner 1000:100, the workspace user) just before that user's workspace starts, and mounts
# only that folder into the workspace (config/jupyterhub/jupyterhub_config.py). No workspace
# mounts the top directory, so it belongs to root, mode 0755: Airflow (uid 50000) reads it,
# nobody else writes it. Folders inside are left alone.
#
# The marker file tells the hub that this lab runs Airflow (profiles engineer/full): compose
# also creates the volume on `core` (for the hub's own mount), where no DAG folder is given.
# Idempotent.
set -eu

dir=${1:?usage: dags-user-init.sh DIR}

chown 0:0 "$dir"
chmod 0755 "$dir"
marker="$dir/.lab-user-dags"
# Older installs let every engineer write the top directory: never write through a link.
if [ -L "$marker" ] || { [ -e "$marker" ] && [ ! -f "$marker" ]; }; then
  rm -rf "$marker"
fi
if [ ! -f "$marker" ]; then
  echo "User DAG folders are served to workspaces (see config/airflow/dags-user-init.sh)." > "$marker"
fi
chmod 0644 "$marker"
echo "dags-user: $dir is owned by root, mode 0755; marker $marker present"
