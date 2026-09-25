"""Is a Lakekeeper-vended STS credential scoped to its table, or bucket-wide?

Run inside any container on the v3-s1 network:  python3 - < scope_probe.py
1. Loads s1.events with X-Iceberg-Access-Delegation: vended-credentials (the same path Trino uses).
2. With those credentials (SigV4 + X-Amz-Security-Token, stdlib only), tries:
     own-read     GET the table's current metadata file            (must be allowed)
     own-put      PUT/DELETE a probe object under the table location (should be allowed)
     sibling-put  PUT/DELETE a probe object under a sibling table path in the same namespace
     outside-put  PUT/DELETE a probe object outside the warehouse key-prefix
     bucket-list  ListObjectsV2 at the bucket root
Prints one line per check: SCOPE <check> <HTTP status> <ALLOWED|DENIED>, then
SCOPE_VERDICT table-scoped|bucket-wide|broken. Credentials are never printed.
Probe objects are deleted immediately with the same credentials.
"""
import datetime
import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request

LK = "http://lakekeeper:8181/catalog/v1"


def http(method, url, headers=None, body=b""):
    req = urllib.request.Request(url, data=body if method in ("PUT", "POST") else None,
                                 method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def get_json(url, headers=None):
    code, body = http("GET", url, headers)
    assert code == 200, (url, code, body[:300])
    return json.loads(body)


c = get_json(f"{LK}/config?warehouse=lakehouse")
prefix = {**c["defaults"], **c["overrides"]}["prefix"]
t = get_json(f"{LK}/{prefix}/namespaces/s1/tables/events",
             {"X-Iceberg-Access-Delegation": "vended-credentials"})
cfg = dict(t.get("config", {}))
for sc in t.get("storage-credentials", []) or []:
    cfg.update(sc.get("config", {}))
AK, SK, TOK = cfg["s3.access-key-id"], cfg["s3.secret-access-key"], cfg["s3.session-token"]
ENDPOINT = cfg.get("s3.endpoint", "http://seaweedfs:8333").rstrip("/")
REGION = cfg.get("client.region") or cfg.get("s3.region") or "us-east-1"

table_loc = t["metadata"]["location"]           # s3://warehouse/lakehouse/<ns-id>/<table-id>
meta_loc = t["metadata-location"]
bucket, table_key = table_loc[len("s3://"):].split("/", 1)
ns_key = table_key.rsplit("/", 1)[0]
print("SCOPE info table-location", table_loc, "key-id-prefix", AK[:4])


def signed(method, key, query="", body=b""):
    now = datetime.datetime.now(datetime.timezone.utc)
    amzdate, date = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    host = urllib.parse.urlparse(ENDPOINT).netloc
    path = "/" + bucket + ("/" + urllib.parse.quote(key, safe="/~") if key else "/")
    payload = hashlib.sha256(body).hexdigest()
    hdrs = {"host": host, "x-amz-content-sha256": payload, "x-amz-date": amzdate,
            "x-amz-security-token": TOK}
    signed_names = ";".join(sorted(hdrs))
    canon = "\n".join([method, path, query,
                       "".join(f"{k}:{hdrs[k]}\n" for k in sorted(hdrs)), signed_names, payload])
    scope = f"{date}/{REGION}/s3/aws4_request"
    sts = "\n".join(["AWS4-HMAC-SHA256", amzdate, scope, hashlib.sha256(canon.encode()).hexdigest()])
    k = ("AWS4" + SK).encode()
    for part in (date, REGION, "s3", "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    sig = hmac.new(k, sts.encode(), hashlib.sha256).hexdigest()
    hdrs["Authorization"] = (f"AWS4-HMAC-SHA256 Credential={AK}/{scope}, "
                             f"SignedHeaders={signed_names}, Signature={sig}")
    del hdrs["host"]
    return http(method, ENDPOINT + path + (("?" + query) if query else ""), hdrs, body)


def report(name, code, body):
    ok = 200 <= code < 300
    err = "" if ok else " " + (body[:160].decode(errors="replace").replace("\n", " "))
    print(f"SCOPE {name} {code} {'ALLOWED' if ok else 'DENIED'}{err}")
    return ok


def put_delete(name, key):
    code, body = signed("PUT", key, body=b"s1 scope probe")
    ok = report(name, code, body)
    if ok:
        signed("DELETE", key)
    return ok


res = {}
res["own-read"] = report("own-read", *signed("GET", meta_loc.split("/", 3)[3]))
res["own-put"] = put_delete("own-put", f"{table_key}/scope-probe.txt")
res["sibling-put"] = put_delete("sibling-put", f"{ns_key}/not-this-table/scope-probe.txt")
res["outside-put"] = put_delete("outside-put", "outside-warehouse-prefix/scope-probe.txt")
res["bucket-list"] = report("bucket-list", *signed("GET", "", "list-type=2&max-keys=1"))

if not res["own-read"]:
    verdict = "broken"
elif res["sibling-put"] or res["outside-put"] or res["bucket-list"]:
    verdict = "bucket-wide"
else:
    verdict = "table-scoped"
print("SCOPE_VERDICT", verdict)
