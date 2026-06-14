#!/usr/bin/env python3
"""Automated OAuth: starts local server, opens browser, captures code, updates .env."""
from __future__ import annotations

import re
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests

APP_ID = sys.argv[1] if len(sys.argv) > 1 else ""
APP_SECRET = sys.argv[2] if len(sys.argv) > 2 else ""
PORT = 8765
REDIRECT_URI = f"http://localhost:{PORT}/callback"

SCOPES = ",".join([
    "threads_basic",
    "threads_content_publish",
    "threads_read_replies",
    "threads_manage_replies",
    "threads_manage_insights",
    "threads_keyword_search",
])

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
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
                b"<h1>Centurion authorized!</h1><p>You can close this tab.</p>"
            )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        pass


def update_env(user_id: str, token: str) -> None:
    lines = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text().splitlines()
    kv = {}
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            kv[k.strip()] = v.strip()
    kv["THREADS_USER_ID"] = user_id
    kv["THREADS_ACCESS_TOKEN"] = token
    out = [f"{k}={v}" for k, v in kv.items()]
    ENV_PATH.write_text("\n".join(out) + "\n")
    print(f"Updated {ENV_PATH}")


def main():
    if not APP_ID or not APP_SECRET:
        print("Usage: python scripts/oauth_auto.py APP_ID APP_SECRET")
        sys.exit(1)

    auth_url = "https://threads.net/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "response_type": "code",
    })

    server = HTTPServer(("localhost", PORT), Handler)
    print(f"\n1) Opening browser — log in as @influencer.bot@threads.net and approve.\n")
    print(f"   If browser doesn't open, visit:\n   {auth_url}\n")
    webbrowser.open(auth_url)

    print("2) Waiting for OAuth callback...")
    server.handle_request()
    server.server_close()

    if not captured_code:
        print("ERROR: No code received. Add redirect URI to Meta app:")
        print(f"   {REDIRECT_URI}")
        sys.exit(1)

    code = captured_code[0]
    print("3) Exchanging code for long-lived token...")

    r = requests.post("https://graph.threads.net/oauth/access_token", data={
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }, timeout=30).json()

    if "error" in r or "access_token" not in r:
        print(f"ERROR: {r}")
        sys.exit(1)

    short_token, user_id = r["access_token"], str(r["user_id"])

    r2 = requests.get("https://graph.threads.net/access_token", params={
        "grant_type": "th_exchange_token",
        "client_secret": APP_SECRET,
        "access_token": short_token,
    }, timeout=30).json()

    if "access_token" not in r2:
        print(f"ERROR exchanging token: {r2}")
        sys.exit(1)

    token = r2["access_token"]
    update_env(user_id, token)
    print(f"\nSUCCESS")
    print(f"THREADS_USER_ID={user_id}")
    print(f"THREADS_ACCESS_TOKEN={token[:20]}... (saved to .env)")


if __name__ == "__main__":
    main()
