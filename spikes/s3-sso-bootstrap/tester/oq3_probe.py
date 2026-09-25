"""OQ-3 evidence (informational, not a pass criterion).

1. Without importing Caddy's root CA, Chromium rejects the lab's HTTPS pages.
2. Plain HTTP on <ip>.sslip.io is NOT a browser "secure context": no window.crypto.subtle,
   which OIDC PKCE in browser apps (e.g. the Lakekeeper UI) needs. *.localhost over HTTP is.
Runs without the NSS import that run.sh performs.
"""
import os

from playwright.sync_api import sync_playwright

D, P = os.environ["LAB_DOMAIN"], os.environ["LAB_PORT"]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    for origin in [f"http://catalog.{D}:18080/", "http://catalog.lab.localhost:18080/"]:
        # Served locally by the test itself; no traffic leaves the browser.
        pg.route(origin + "**", lambda r: r.fulfill(status=200, content_type="text/html", body="<p>probe</p>"))
        pg.goto(origin)
        print("OQ3", origin, pg.evaluate(
            "({secureContext: window.isSecureContext, cryptoSubtle: !!(window.crypto && window.crypto.subtle)})"))
    try:
        pg.goto(f"https://catalog.{D}:{P}/ui/")
        print("OQ3 untrusted CA: page loaded (unexpected)")
    except Exception as e:  # noqa: BLE001
        print("OQ3 untrusted CA:", str(e).splitlines()[0])
    b.close()
