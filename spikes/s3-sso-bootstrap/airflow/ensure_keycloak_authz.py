"""Create the Airflow authz model in Keycloak once (scopes, resources, role policies, permissions).

Uses the provider's own CLI (`airflow keycloak-auth-manager create-all`). That CLI is not
re-runnable (it POSTs scopes without skip_exists), so we skip it when the model already exists.
"""
import os
import subprocess
import sys

from keycloak import KeycloakAdmin

admin = KeycloakAdmin(
    server_url=os.environ["AIRFLOW__KEYCLOAK_AUTH_MANAGER__SERVER_URL"],
    username=os.environ["KC_ADMIN_USER"],
    password=os.environ["KC_ADMIN_PASSWORD"],
    realm_name="lakehouse",
    user_realm_name="master",
    verify=True,
)
uuid = admin.get_client_id("airflow")
scopes = {s["name"] for s in admin.get_client_authz_scopes(uuid)}
if "MENU" in scopes:
    print("keycloak authz model already present; skipping create-all")
    sys.exit(0)
subprocess.run(
    ["airflow", "keycloak-auth-manager", "create-all",
     "--username", os.environ["KC_ADMIN_USER"], "--password", os.environ["KC_ADMIN_PASSWORD"]],
    check=True,
)
print("keycloak authz model created")
