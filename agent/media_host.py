"""Host generated images at a public URL for Threads API (requires fetchable image_url)."""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path

import requests

from .config import CFG


def public_url(path: Path) -> str:
    """Upload image and return a publicly accessible HTTPS URL."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and CFG.github_repo:
        try:
            return _upload_github(path, token)
        except Exception as e:
            print(f"[media] GitHub upload error: {e}")
    for uploader in (_upload_0x0, _upload_litterbox):
        try:
            return uploader(path)
        except Exception as e:
            print(f"[media] {uploader.__name__} failed: {e}")
    raise RuntimeError("all image upload methods failed")


def _upload_github(path: Path, token: str) -> str:
    owner, repo = CFG.github_repo.split("/", 1)
    dest = f"media/posts/{path.name}"
    api = f"https://api.github.com/repos/{owner}/{repo}/contents/{dest}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    content = base64.b64encode(path.read_bytes()).decode()
    payload = {
        "message": f"media: {path.name}",
        "content": content,
    }
    existing = requests.get(api, headers=headers, timeout=30)
    if existing.status_code == 200:
        payload["sha"] = existing.json()["sha"]

    r = requests.put(api, headers=headers, json=payload, timeout=60)
    if r.status_code not in (200, 201):
        print(f"[media] GitHub upload failed ({r.status_code}): {r.text[:200]}")
        return _upload_catbox(path)

    # Give CDN a moment to propagate before Meta fetches the image.
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{dest}"
    print(f"[media] hosted on GitHub: {url}")
    time.sleep(12)
    return url


def _upload_0x0(path: Path) -> str:
    with path.open("rb") as f:
        r = requests.post("https://0x0.st", files={"file": f}, timeout=60)
    url = r.text.strip()
    if not url.startswith("https://"):
        raise RuntimeError(r.text[:200])
    print(f"[media] hosted on 0x0.st: {url}")
    time.sleep(3)
    return url


def _upload_litterbox(path: Path) -> str:
    with path.open("rb") as f:
        r = requests.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": "24h"},
            files={"fileToUpload": (path.name, f, "image/png")},
            timeout=60,
        )
    url = r.text.strip()
    if not url.startswith("https://"):
        raise RuntimeError(r.text[:200])
    print(f"[media] hosted on litterbox: {url}")
    time.sleep(3)
    return url


def _upload_catbox(path: Path) -> str:
    with path.open("rb") as f:
        r = requests.post(
            "https://catbox.moe/userapi.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (path.name, f, "image/png")},
            timeout=60,
        )
    url = r.text.strip()
    if not url.startswith("https://"):
        raise RuntimeError(f"image upload failed: {r.text[:200]}")
    print(f"[media] hosted on catbox: {url}")
    time.sleep(5)
    return url
