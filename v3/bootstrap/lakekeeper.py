"""Lakekeeper: server bootstrap and the `lakehouse` warehouse (management API, internal URL).

Bootstrap authenticates as the service account of the confidential Keycloak client
`lakekeeper` (client credentials). That principal performs the one-time server bootstrap,
so it becomes Lakekeeper's first admin (operator).
"""
from . import web

LK = "http://lakekeeper:8181"
MGMT = f"{LK}/management/v1"

WAREHOUSE = "lakehouse"
BUCKET = "warehouse"
REGION = "us-east-1"
# SeaweedFS STS role (config/seaweedfs/iam.template.json). Its trust policy names only the
# SeaweedFS identity `lakekeeper`, whose keys are the warehouse storage credential below.
STS_ROLE_ARN = "arn:aws:iam::000000000000:role/LakekeeperVended"


def storage_profile():
    # S-1: SeaweedFS needs s3-compat + path-style. Remote signing serves Spark/PyIceberg;
    # STS vending serves Trino/DuckDB (ADR-006 as amended), table-scoped, <= 1 h.
    return {
        "type": "s3",
        "flavor": "s3-compat",
        "bucket": BUCKET,
        "key-prefix": WAREHOUSE,
        "endpoint": "http://seaweedfs:8333/",  # Lakekeeper stores it with the slash
        "region": REGION,
        "path-style-access": True,
        "remote-signing-enabled": True,
        "remote-signing-url-style": "path",
        "sts-enabled": True,
        "sts-role-arn": STS_ROLE_ARN,
        "sts-token-validity-seconds": 3600,
    }


class Client:
    def __init__(self, token):
        self.h = {"Authorization": f"Bearer {token}"}

    def get(self, path, **kw):
        return web.request("GET", MGMT + path, headers=self.h, **kw)[1]

    def call(self, method, path, body=None, **kw):
        return web.request(method, MGMT + path, headers=self.h, json_body=body, **kw)

    def ensure_bootstrapped(self):
        info = self.get("/info")
        if info.get("bootstrapped"):
            return False, info
        self.call("POST", "/bootstrap", {"accept-terms-of-use": True, "is-operator": True})
        print("[lakekeeper] server bootstrapped (operator = Keycloak client 'lakekeeper')")
        return True, self.get("/info")

    def whoami(self):
        return self.get("/whoami")

    def find_warehouse(self, name=WAREHOUSE):
        for wh in self.get("/warehouse").get("warehouses", []):
            if wh.get("name") == name:
                return wh
        return None

    def ensure_warehouse(self, access_key, secret_key):
        """Create the warehouse, or re-apply the storage profile only if it drifted.
        Returns 'created', 'updated' or 'unchanged'."""
        profile = storage_profile()
        cred = {"type": "s3", "credential-type": "access-key",
                "access-key-id": access_key, "secret-access-key": secret_key}
        wh = self.find_warehouse()
        if wh is None:
            self.call("POST", "/warehouse", {
                "warehouse-name": WAREHOUSE,
                "storage-profile": profile,
                "storage-credential": cred,
                "delete-profile": {"type": "hard"},
            })
            print(f"[lakekeeper] created warehouse {WAREHOUSE}")
            return "created", self.find_warehouse()
        current = wh.get("storage-profile") or {}
        drift = {k: (current.get(k), v) for k, v in profile.items() if current.get(k) != v}
        if not drift:
            return "unchanged", wh
        wid = wh.get("warehouse-id") or wh["id"]
        self.call("POST", f"/warehouse/{wid}/storage",
                  {"storage-profile": profile, "storage-credential": cred})
        print(f"[lakekeeper] warehouse {WAREHOUSE}: storage profile re-applied ({sorted(drift)})")
        return "updated", self.find_warehouse()
