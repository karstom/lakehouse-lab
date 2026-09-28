# Lakehouse Lab User Provisioning Examples

This guide provides example commands and sample `.env` entries for provisioning users with different roles in Lakehouse Lab.

---

## 1. Provisioning Users with `provision-user.sh`

The `scripts/provision-user.sh` script creates users across Superset, Airflow, MinIO, and JupyterHub.

**Usage:**
```bash
./scripts/provision-user.sh <username> <email> <password> <role>
```

**Roles:**
- `admin`   — Full admin access to all services
- `analyst` — Create/edit dashboards, run workflows, read/write data
- `viewer`  — View dashboards and data, read-only access

---

## 2. Example Commands

**Provision an Admin User:**
```bash
./scripts/provision-user.sh alice alice@company.com StrongAdminPass123 admin
```

**Provision an Analyst User:**
```bash
./scripts/provision-user.sh bob bob@company.com AnalystPass456 analyst
```

**Provision a Viewer User:**
```bash
./scripts/provision-user.sh carol carol@company.com ViewerPass789 viewer
```

---

## 3. Sample `.env` Entries for Each Role

**Admin Example:**
```
SUPERSET_ADMIN_USER=alice
SUPERSET_ADMIN_PASSWORD=StrongAdminPass123
AIRFLOW_ADMIN_USER=alice
AIRFLOW_ADMIN_PASSWORD=StrongAdminPass123
MINIO_ROOT_USER=alice
MINIO_ROOT_PASSWORD=StrongAdminPass123
JUPYTER_TOKEN=StrongAdminPass123
```

**Analyst Example:**
```
SUPERSET_ANALYST_USER=bob
SUPERSET_ANALYST_PASSWORD=AnalystPass456
AIRFLOW_ANALYST_USER=bob
AIRFLOW_ANALYST_PASSWORD=AnalystPass456
MINIO_ANALYST_USER=bob
MINIO_ANALYST_PASSWORD=AnalystPass456
JUPYTER_TOKEN=AnalystPass456
```

**Viewer Example:**
```
SUPERSET_VIEWER_USER=carol
SUPERSET_VIEWER_PASSWORD=ViewerPass789
AIRFLOW_VIEWER_USER=carol
AIRFLOW_VIEWER_PASSWORD=ViewerPass789
MINIO_VIEWER_USER=carol
MINIO_VIEWER_PASSWORD=ViewerPass789
JUPYTER_TOKEN=ViewerPass789
```

---

## 4. Best Practices

- Use strong, unique passwords for each user.
- Store `.env` files securely and never commit them to version control.
- Rotate credentials regularly (see credential rotation workflow).
- Remove users who no longer need access using the provisioning script with `--remove`.

---

For more details, see the main [README.md](../README.md) and [INSTALLATION.md](INSTALLATION.md).