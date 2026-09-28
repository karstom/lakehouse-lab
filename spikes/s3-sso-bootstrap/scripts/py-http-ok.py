"""Healthcheck for Python images without curl. usage: py-http-ok.py <url>"""
import sys
import urllib.request

try:
    urllib.request.urlopen(sys.argv[1], timeout=5)
except Exception:  # noqa: BLE001
    sys.exit(1)
