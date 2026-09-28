"""AWS Signature V4 for S3 requests (stdlib only), for the few SeaweedFS calls bootstrap makes."""
import datetime
import hashlib
import hmac
import urllib.parse


def sign(method, endpoint, path, *, access_key, secret_key, region="us-east-1",
         query="", body=b"", session_token=None, service="s3"):
    """Returns (url, headers) for a path-style request. `path` starts with '/'."""
    now = datetime.datetime.now(datetime.timezone.utc)
    amzdate, date = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    host = urllib.parse.urlparse(endpoint).netloc
    cpath = urllib.parse.quote(path, safe="/~")
    payload = hashlib.sha256(body).hexdigest()
    hdrs = {"host": host, "x-amz-content-sha256": payload, "x-amz-date": amzdate}
    if session_token:
        hdrs["x-amz-security-token"] = session_token
    names = ";".join(sorted(hdrs))
    canon = "\n".join([method, cpath, query,
                       "".join(f"{k}:{hdrs[k]}\n" for k in sorted(hdrs)), names, payload])
    scope = f"{date}/{region}/{service}/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amzdate, scope,
                         hashlib.sha256(canon.encode()).hexdigest()])
    k = ("AWS4" + secret_key).encode()
    for part in (date, region, service, "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    hdrs["Authorization"] = (f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
                             f"SignedHeaders={names}, Signature={sig}")
    del hdrs["host"]
    url = endpoint.rstrip("/") + cpath + (f"?{query}" if query else "")
    return url, hdrs
