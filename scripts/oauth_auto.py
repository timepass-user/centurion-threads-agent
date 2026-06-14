#!/usr/bin/env python3
"""Automated OAuth with HTTPS localhost server (Meta requires https redirect)."""
from __future__ import annotations

import re
import ssl
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from oauth_common import REDIRECT_URI, auth_url, exchange_code, update_env

APP_ID = sys.argv[1] if len(sys.argv) > 1 else ""
APP_SECRET = sys.argv[2] if len(sys.argv) > 2 else ""
PORT = 8765
REDIRECT_URI_HTTPS = f"https://localhost:{PORT}/callback"

CERT_DIR = Path(__file__).resolve().parent / ".certs"
captured_code: list[str] = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if "code=" in self.path:
            m = re.search(r"code=([^&]+)", self.path)
            if m:
                captured_code.append(m.group(1))
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<h1>Centurion authorized!</h1><p>Close this tab and return to terminal.</p>"
            )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        pass


def ensure_cert() -> tuple[Path, Path]:
    CERT_DIR.mkdir(exist_ok=True)
    cert, key = CERT_DIR / "localhost.pem", CERT_DIR / "localhost-key.pem"
    if not cert.exists():
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key), "-out", str(cert),
            "-days", "365", "-nodes", "-subj", "/CN=localhost",
        ], check=True)
    return cert, key


def main():
    if not APP_ID or not APP_SECRET:
        print("Usage: python scripts/oauth_auto.py APP_ID APP_SECRET")
        sys.exit(1)

    print("\n=== Add this redirect URI in Meta Developer Console ===")
    print(f"  {REDIRECT_URI_HTTPS}\n")
    print("(Or use the simpler manual flow: python scripts/exchange_code.py APP_ID APP_SECRET)\n")

    cert, key = ensure_cert()
    auth = auth_url(APP_ID).replace(REDIRECT_URI, REDIRECT_URI_HTTPS)

    server = HTTPServer(("localhost", PORT), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)

    print("1) Opening browser — log in as @influencer.bot@threads.net and approve.")
    print("   Accept the browser security warning for localhost (self-signed cert).\n")
    print(f"   Manual URL:\n   {auth}\n")
    webbrowser.open(auth)

    print("2) Waiting for HTTPS callback...")
    server.handle_request()
    server.server_close()

    if not captured_code:
        print("ERROR: No code received. Try the manual flow instead:")
        print(f"  python scripts/exchange_code.py {APP_ID} <secret>")
        sys.exit(1)

    # Exchange using the port-specific redirect URI
    code = captured_code[0]
    import requests
    r = requests.post("https://graph.threads.net/oauth/access_token", data={
        "client_id": APP_ID, "client_secret": APP_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI_HTTPS, "code": code,
    }, timeout=30).json()
    if "access_token" not in r:
        print(f"ERROR: {r}")
        sys.exit(1)
    short_token, user_id = r["access_token"], str(r["user_id"])
    r2 = requests.get("https://graph.threads.net/access_token", params={
        "grant_type": "th_exchange_token", "client_secret": APP_SECRET,
        "access_token": short_token,
    }, timeout=30).json()
    if "access_token" not in r2:
        print(f"ERROR: {r2}")
        sys.exit(1)

    update_env(user_id, r2["access_token"])
    print(f"\nSUCCESS — THREADS_USER_ID={user_id}")


if __name__ == "__main__":
    main()
