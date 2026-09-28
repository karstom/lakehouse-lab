"""Superset's REST API as YOU, from your workspace (analyst track, A4). Not a lesson.

Superset's login is a browser login through Keycloak. From a workspace the only credential is
your own login token (lakehouse.lab_token()), and the lab's Superset accepts it on its API:

    Authorization: Bearer <your token>

Superset then treats the request exactly like one from your browser: same user, same roles,
same data rules (every query still runs in Trino as you). Superset only knows you after your
first login in the browser, so open Superset once before using this.

    from superset_api import Superset
    ss = Superset()
    ss.me()                                  # {'username': 'anna', ...}
    ss.find("chart", slice_name="A4 Revenue by segment")

Writes (POST/PUT/DELETE) also need Superset's CSRF token; this client fetches it.
"""
import json
import os
import urllib.parse

import trackkit as tk


class SupersetError(tk.CheckError):
    pass


class NotLoggedIn(SupersetError):
    """Superset does not know this user yet, or refused the token."""


def rison_filters(filters, page_size=100, **extra):
    """Superset list `q` parameter (rison) with `eq` filters: [(col, value)]."""
    def val(v):
        if isinstance(v, bool):
            return "!t" if v else "!f"
        if isinstance(v, int):
            return str(v)
        s = str(v).replace("!", "!!").replace("'", "!'")
        return f"'{s}'"
    parts = [f"(col:{c},opr:{o},value:{val(v)})" for c, o, v in filters]
    q = f"(filters:!({','.join(parts)}),page:0,page_size:{page_size}"
    for k, v in extra.items():
        q += f",{k}:{v}"
    return q + ")"


class Superset:
    def __init__(self, base=None):
        import requests
        self.base = (base or tk.public_url("superset")).rstrip("/")
        self.s = requests.Session()
        self.s.verify = os.environ.get("SSL_CERT_FILE") or True
        self.csrf = None

    # ------------------------------------------------------------------ transport
    def _headers(self, write):
        import lakehouse
        h = {"Authorization": f"Bearer {lakehouse.lab_token()}", "Accept": "application/json",
             "Referer": self.base + "/"}
        if write:
            if self.csrf is None:
                r = self.s.get(self.base + "/api/v1/security/csrf_token/", headers=h, timeout=30)
                self._raise(r, "GET /security/csrf_token/")
                self.csrf = r.json().get("result") or ""
            h.update({"X-CSRFToken": self.csrf, "Content-Type": "application/json"})
        return h

    def _raise(self, r, what):
        if r.status_code in (401, 403) and ("/me" in what or "csrf" in what):
            raise NotLoggedIn(
                f"Superset refused your login token ({r.status_code} on {what}). Open "
                f"{self.base}/ in your browser and log in once, then try again.")
        if r.status_code >= 400:
            raise SupersetError(f"Superset {what}: HTTP {r.status_code}: {r.text[:300]}")

    def api(self, method, path, body=None, ok=(200, 201)):
        write = method != "GET"
        r = self.s.request(method, f"{self.base}/api/v1{path}", headers=self._headers(write),
                           data=json.dumps(body) if body is not None else None, timeout=120)
        if r.status_code not in ok:
            self._raise(r, f"{method} {path.split('?')[0]}")
        try:
            return r.json()
        except ValueError:
            return {}

    # ------------------------------------------------------------------ reads
    def me(self):
        return self.api("GET", "/me/").get("result") or {}

    def my_id(self):
        me = self.me()
        uid = me.get("id")
        if uid is None:
            raise NotLoggedIn("Superset did not return your user; log in to Superset once in the browser")
        return uid

    def list(self, kind, filters, columns=None):
        extra = {}
        if columns:
            extra["columns"] = "!(" + ",".join(columns) + ")"
        q = urllib.parse.quote(rison_filters(filters, **extra))
        return self.api("GET", f"/{kind}/?q={q}").get("result") or []

    def get(self, kind, oid):
        return self.api("GET", f"/{kind}/{oid}").get("result") or {}

    def owned(self, kind, name_col, name, uid):
        """Objects of `kind` named `name` that `uid` owns (Superset object names are not
        unique across users, so the owner decides which one is yours)."""
        out = []
        for o in self.list(kind, [(name_col, "eq", name)]):
            full = dict(o, **self.get(kind, o["id"]))    # list row + detail
            owners = {x.get("id") for x in full.get("owners") or []}
            if uid in owners:
                out.append(full)
        return out

    def my_datasets(self, schema, table, uid):
        out = []
        for d in self.list("dataset", [("table_name", "eq", table), ("schema", "eq", schema)]):
            full = self.get("dataset", d["id"])
            if uid in {x.get("id") for x in full.get("owners") or []}:
                out.append(full)
        return out

    def chart_data(self, chart_id):
        """The rows the saved chart shows (its saved query, run now, as you)."""
        body = self.api("GET", f"/chart/{chart_id}/data/?format=json&force=true")
        rows = []
        for q in body.get("result") or []:
            rows.extend(q.get("data") or [])
        return rows

    def dashboard_charts(self, dash_id):
        return self.api("GET", f"/dashboard/{dash_id}/charts").get("result") or []

    # ------------------------------------------------------------------ deletes (reset)
    def delete(self, kind, oid):
        self.api("DELETE", f"/{kind}/{oid}", ok=(200, 204, 404))
