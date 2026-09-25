"""SeaweedFS: make sure the warehouse bucket exists (S3 API, admin identity)."""
from . import sigv4, web

S3 = "http://seaweedfs:8333"


def ensure_bucket(bucket, access_key, secret_key, region):
    """Returns True if the bucket was created."""
    url, h = sigv4.sign("HEAD", S3, f"/{bucket}", access_key=access_key,
                        secret_key=secret_key, region=region)
    status, _, _ = web.request("HEAD", url, headers=h, expect=None)
    if status == 200:
        return False
    if status != 404:
        raise RuntimeError(f"HEAD bucket {bucket}: HTTP {status}")
    url, h = sigv4.sign("PUT", S3, f"/{bucket}", access_key=access_key,
                        secret_key=secret_key, region=region)
    web.request("PUT", url, headers=h, data=b"", expect=(200,))
    print(f"[seaweedfs] created bucket {bucket}")
    return True


def anonymous_denied(bucket):
    """S3 auth must be on before anything else talks to SeaweedFS."""
    status, _, _ = web.request("GET", f"{S3}/{bucket}/", expect=None)
    return status in (401, 403)
