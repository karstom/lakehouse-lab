# dags/user/ (mount point)

Inside the Airflow containers this directory is replaced by the shared volume
`<project>_dags-user` (compose/airflow.yaml, read-only there). It holds one folder per
user. Engineers and lab admins write their own DAGs into their folder from their workspace,
which mounts only that folder, at `~/airflow-dags/<username>/` (CONTRACT Phase 4, learning
module E3).

The directory must exist in the repository: `./dags` is bind-mounted read-only, and Docker
cannot create a mount point inside a read-only mount. Nothing placed here on the host is
visible to Airflow.
