"""Small HTTP helpers on urllib (stdlib only). Never logs request bodies or credentials."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request


class HTTPError(RuntimeError):
    def __init__(self, method, url, status, body):
        self.status = status
        self.body = body
        snippet = body[:300] if isinstance(body, str) else json.dumps(body)[:300]
        super().__init__(f"{method} {url} -> HTTP {status}: {snippet}")


def request(method, url, *, json_body=None, form=None, headers=None, data=None,
            expect=(200, 201, 204), timeout=30):
    """Returns (status, parsed JSON or text, response headers). Raises HTTPError on an
    unexpected status. `expect=None` accepts any status."""
    hdrs = dict(headers or {})
    body = data
    if json_body is not None:
        body = json.dumps(json_body).encode()
        hdrs.setdefault("Content-Type", "application/json")
    elif form is not None:
        body = urllib.parse.urlencode(form).encode()
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw, rh = r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        status, raw, rh = e.code, e.read(), dict(e.headers or {})
    text = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text) if text.strip() else None
    except ValueError:
        parsed = text
    if expect is not None and status not in expect:
        raise HTTPError(method, url, status, parsed if parsed is not None else "")
    return status, parsed, rh


def wait_for(url, *, timeout=180, ok=(200,)):
    """Poll a URL until it answers with one of `ok` (compose healthchecks cover most waits;
    this covers readiness that a healthcheck cannot see)."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            status, _, _ = request("GET", url, expect=None, timeout=5)
            if status in ok:
                return
            last = f"HTTP {status}"
        except OSError as e:  # connection refused, DNS, timeout
            last = str(e)
        time.sleep(2)
    raise RuntimeError(f"{url} not ready after {timeout}s ({last})")
