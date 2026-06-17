"""Shared OAuth helpers for Threads token exchange."""
from __future__ import annotations

import urllib.parse
from pathlib import Path

import requests

# Meta blocks http:// redirects — must be https
REDIRECT_URI = "https://localhost/callback"

SCOPES = ",".join([
    "threads_basic",
    "threads_content_publish",
    "threads_read_replies",
    "threads_manage_replies",
    "threads_manage_insights",
    "threads_keyword_search",
])

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def auth_url(app_id: str) -> str:
    return "https://threads.net/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": app_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "response_type": "code",
    })


def exchange_code(app_id: str, app_secret: str, code: str) -> tuple[str, str]:
    """Return (user_id, access_token). Prefers long-lived; falls back to short-lived."""
    code = code.strip().rstrip("#_")
    r = requests.post("https://graph.threads.net/oauth/access_token", data={
        "client_id": app_id,
        "client_secret": app_secret,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }, timeout=30).json()

    if "access_token" not in r:
        raise RuntimeError(f"Token exchange failed: {r}")

    short_token, user_id = r["access_token"], str(r["user_id"])

    for url in (
        "https://graph.threads.net/v1.0/access_token",
        "https://graph.threads.net/access_token",
    ):
        r2 = requests.get(url, params={
            "grant_type": "th_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token,
        }, timeout=30).json()
        if "access_token" in r2:
            print(f"[oauth] long-lived token via {url} (60-day)")
            return user_id, r2["access_token"]

    print(f"[oauth] long-lived exchange failed ({r2}); using short-lived token (~1hr)")
    print("[oauth] WARNING: re-auth within 1 hour or fix Meta app for long-lived tokens.")
    return user_id, short_token


def update_env(user_id: str, token: str) -> None:
    kv: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                kv[k.strip()] = v.strip()
    kv["THREADS_USER_ID"] = user_id
    kv["THREADS_ACCESS_TOKEN"] = token
    ENV_PATH.write_text("\n".join(f"{k}={v}" for k, v in kv.items()) + "\n")
    print(f"Saved credentials to {ENV_PATH}")
