"""Minimal Threads API client. Base: https://graph.threads.net/v1.0
Only the endpoints this agent needs: publish, reply, insights, keyword search,
profile, token refresh."""
import time
import requests

BASE = "https://graph.threads.net/v1.0"


class ThreadsError(RuntimeError):
    pass


class ThreadsAccessBlocked(ThreadsError):
    """Meta error #200 — token revoked, app restricted, or permissions missing."""


def _is_access_blocked(err: dict) -> bool:
    msg = (err.get("message") or "").lower()
    return err.get("code") == 200 and ("blocked" in msg or "permission" in msg)


class ThreadsClient:
    def __init__(self, user_id: str, token: str):
        self.user_id = user_id
        self.token = token

    # ---------- low level ----------
    def _req(self, method: str, path: str, **params) -> dict:
        params["access_token"] = self.token
        url = f"{BASE}/{path}"
        for attempt in range(3):
            try:
                r = requests.request(method, url, params=params, timeout=30)
            except requests.RequestException as e:
                if attempt == 2:
                    raise ThreadsError(f"network error on {path}: {e}") from e
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            data = r.json() if r.content else {}
            if "error" in data:
                err = data["error"]
                if _is_access_blocked(err):
                    raise ThreadsAccessBlocked(f"{path}: {err}")
                raise ThreadsError(f"{path}: {err}")
            return data
        raise ThreadsError(f"{path}: exhausted retries (last status {r.status_code})")

    # ---------- publishing (two-step: container -> publish) ----------
    def _publish_container(self, params: dict) -> str:
        container = self._req("POST", f"{self.user_id}/threads", **params)
        time.sleep(8)
        published = self._req("POST", f"{self.user_id}/threads_publish",
                              creation_id=container["id"])
        return published["id"]

    def publish_text(self, text: str, reply_to_id: str | None = None,
                     quote_post_id: str | None = None) -> str:
        params: dict = {"media_type": "TEXT", "text": text}
        if reply_to_id:
            params["reply_to_id"] = reply_to_id
        if quote_post_id:
            params["quote_post_id"] = quote_post_id
        return self._publish_container(params)

    def publish_image(self, text: str, image_url: str,
                      reply_to_id: str | None = None) -> str:
        params: dict = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": text,
        }
        if reply_to_id:
            params["reply_to_id"] = reply_to_id
        return self._publish_container(params)

    def repost(self, media_id: str) -> str:
        """Native repost (reshare) of another user's post."""
        data = self._req("POST", f"{media_id}/repost")
        return data.get("id", media_id)

    # ---------- reading ----------
    def keyword_search(self, query: str, search_type: str = "RECENT", limit: int = 25) -> list[dict]:
        data = self._req(
            "GET", "keyword_search",
            q=query, search_type=search_type, limit=limit,
            fields="id,text,username,timestamp,permalink,has_replies,is_reply",
        )
        return data.get("data", [])

    def media_insights(self, media_id: str) -> dict:
        data = self._req("GET", f"{media_id}/insights",
                         metric="views,likes,replies,reposts,quotes")
        out = {}
        for m in data.get("data", []):
            vals = m.get("values", [{}])
            out[m["name"]] = vals[0].get("value", 0) if vals else 0
        return out

    def profile(self) -> dict:
        return self._req("GET", "me",
                         fields="id,username,threads_biography,threads_profile_picture_url")

    def follower_count(self) -> int:
        data = self._req("GET", f"{self.user_id}/threads_insights",
                         metric="followers_count")
        for m in data.get("data", []):
            if m["name"] == "followers_count":
                return m.get("total_value", {}).get("value", 0)
        return 0

    def my_recent_posts(self, limit: int = 10) -> list[dict]:
        data = self._req("GET", f"{self.user_id}/threads",
                         fields="id,text,timestamp", limit=limit)
        return data.get("data", [])

    def replies_to(self, media_id: str) -> list[dict]:
        data = self._req("GET", f"{media_id}/replies",
                         fields="id,text,username,timestamp")
        return data.get("data", [])

    # ---------- token lifecycle (long-lived tokens last 60 days) ----------
    def refresh_token(self) -> str:
        data = self._req("GET", "refresh_access_token",
                         grant_type="th_refresh_token")
        return data["access_token"]

    def verify_access(self) -> dict:
        """Lightweight health check. Raises ThreadsAccessBlocked if credentials are dead."""
        return self.profile()
