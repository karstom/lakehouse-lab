"""Build-time only: download the Iceberg Spark runtime and the Iceberg AWS bundle into the
Spark jars dir and verify each against its pinned sha256 (versions.env / .pins).

Usage: fetch-jars.py JARS_DIR SPARK_VERSION SCALA_BINARY_VERSION ICEBERG_VERSION \
                     RUNTIME_DIGEST AWS_BUNDLE_DIGEST
Digests are 'sha256:<hex>'. The Spark minor (4.1) is derived from SPARK_VERSION, so the only
pins are the ones in versions.env (INV_SPARK_VERSION_ALIGNMENT, WATCH_ICEBERG_VERSION_SITES).
"""
import hashlib
import os
import sys
import urllib.request

MAVEN = "https://repo1.maven.org/maven2/org/apache/iceberg"


def fetch(jars_dir, artifact, version, digest):
    algo, _, want = digest.partition(":")
    if algo != "sha256" or len(want) != 64:
        raise SystemExit(f"bad digest for {artifact}: {digest!r} (want sha256:<64 hex>)")
    url = f"{MAVEN}/{artifact}/{version}/{artifact}-{version}.jar"
    dest = os.path.join(jars_dir, f"{artifact}-{version}.jar")
    h = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as r, open(dest + ".part", "wb") as f:
        while chunk := r.read(1 << 20):
            h.update(chunk)
            f.write(chunk)
    if h.hexdigest() != want:
        os.unlink(dest + ".part")
        raise SystemExit(f"sha256 mismatch for {url}: got {h.hexdigest()}, pinned {want}")
    os.replace(dest + ".part", dest)
    print(f"fetched {os.path.basename(dest)} (sha256 ok)")


def main():
    jars_dir, spark, scala, iceberg, runtime_digest, bundle_digest = sys.argv[1:7]
    spark_minor = ".".join(spark.split(".")[:2])
    fetch(jars_dir, f"iceberg-spark-runtime-{spark_minor}_{scala}", iceberg, runtime_digest)
    fetch(jars_dir, "iceberg-aws-bundle", iceberg, bundle_digest)


if __name__ == "__main__":
    main()
