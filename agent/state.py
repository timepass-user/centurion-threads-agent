"""All persistent state in one SQLite file (committed back to the repo by CI,
so the agent has memory across stateless GitHub Actions runs)."""
import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "state.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    media_id     TEXT PRIMARY KEY,
    text         TEXT NOT NULL,
    fmt          TEXT NOT NULL,
    posted_at    REAL NOT NULL,
    views        INTEGER DEFAULT 0,
    likes        INTEGER DEFAULT 0,
    replies      INTEGER DEFAULT 0,
    reposts      INTEGER DEFAULT 0,
    quotes       INTEGER DEFAULT 0,
    scored       INTEGER DEFAULT 0      -- fed to bandit yet?
);
CREATE TABLE IF NOT EXISTS sent_replies (
    reply_media_id  TEXT PRIMARY KEY,
    target_post_id  TEXT NOT NULL,
    target_username TEXT,
    text            TEXT NOT NULL,
    sent_at         REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS arms (
    fmt    TEXT PRIMARY KEY,
    alpha  REAL DEFAULT 1.0,   -- Beta-distribution successes + 1
    beta   REAL DEFAULT 1.0    -- failures + 1
);
CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT
);
CREATE TABLE IF NOT EXISTS sent_engagements (
    action          TEXT NOT NULL,
    media_id        TEXT PRIMARY KEY,
    target_id       TEXT,
    text            TEXT,
    sent_at         REAL NOT NULL
);
"""


class State:
    def __init__(self, path: Path = DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------- kv ----------
    def get(self, key: str, default=None):
        row = self.conn.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
        return json.loads(row["v"]) if row else default

    def set(self, key: str, value):
        self.conn.execute(
            "INSERT INTO kv (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (key, json.dumps(value)),
        )
        self.conn.commit()

    # ---------- posts ----------
    def record_post(self, media_id: str, text: str, fmt: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO posts (media_id, text, fmt, posted_at) VALUES (?,?,?,?)",
            (media_id, text, fmt, time.time()),
        )
        self.conn.commit()

    def posts_in_last(self, hours: float) -> int:
        cutoff = time.time() - hours * 3600
        return self.conn.execute(
            "SELECT COUNT(*) c FROM posts WHERE posted_at > ?", (cutoff,)
        ).fetchone()["c"]

    def last_post_time(self) -> float:
        row = self.conn.execute("SELECT MAX(posted_at) m FROM posts").fetchone()
        return row["m"] or 0.0

    def recent_post_texts(self, n: int = 25) -> list[str]:
        rows = self.conn.execute(
            "SELECT text FROM posts ORDER BY posted_at DESC LIMIT ?", (n,)
        ).fetchall()
        return [r["text"] for r in rows]

    def unscored_posts(self, older_than_hours: float = 20) -> list[sqlite3.Row]:
        cutoff = time.time() - older_than_hours * 3600
        return self.conn.execute(
            "SELECT * FROM posts WHERE scored=0 AND posted_at < ?", (cutoff,)
        ).fetchall()

    def update_metrics(self, media_id: str, m: dict):
        self.conn.execute(
            "UPDATE posts SET views=?, likes=?, replies=?, reposts=?, quotes=? WHERE media_id=?",
            (m.get("views", 0), m.get("likes", 0), m.get("replies", 0),
             m.get("reposts", 0), m.get("quotes", 0), media_id),
        )
        self.conn.commit()

    def mark_scored(self, media_id: str):
        self.conn.execute("UPDATE posts SET scored=1 WHERE media_id=?", (media_id,))
        self.conn.commit()

    def engagement_rates(self) -> list[float]:
        rows = self.conn.execute(
            "SELECT views, likes, replies, reposts FROM posts WHERE views > 0"
        ).fetchall()
        return [(r["likes"] + 2 * r["replies"] + 2 * r["reposts"]) / max(r["views"], 1)
                for r in rows]

    # ---------- replies ----------
    def record_reply(self, reply_media_id, target_post_id, target_username, text):
        self.conn.execute(
            "INSERT OR IGNORE INTO sent_replies VALUES (?,?,?,?,?)",
            (reply_media_id, target_post_id, target_username, text, time.time()),
        )
        self.conn.commit()

    def replied_to(self, target_post_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM sent_replies WHERE target_post_id=?", (target_post_id,)
        ).fetchone() is not None

    def replied_to_user_recently(self, username: str, hours: float = 72) -> bool:
        cutoff = time.time() - hours * 3600
        return self.conn.execute(
            "SELECT 1 FROM sent_replies WHERE target_username=? AND sent_at > ?",
            (username, cutoff),
        ).fetchone() is not None

    def replies_in_last(self, hours: float) -> int:
        cutoff = time.time() - hours * 3600
        return self.conn.execute(
            "SELECT COUNT(*) c FROM sent_replies WHERE sent_at > ?", (cutoff,)
        ).fetchone()["c"]

    def last_reply_time(self) -> float:
        row = self.conn.execute("SELECT MAX(sent_at) m FROM sent_replies").fetchone()
        return row["m"] or 0.0

    # ---------- engagements (reposts, quotes, self-threads) ----------
    def record_engagement(self, action: str, media_id: str, target_id: str = "",
                          text: str = ""):
        self.conn.execute(
            "INSERT OR IGNORE INTO sent_engagements VALUES (?,?,?,?,?)",
            (action, media_id, target_id, text, time.time()),
        )
        self.conn.commit()

    def engaged(self, action: str, target_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM sent_engagements WHERE action=? AND target_id=?",
            (action, target_id),
        ).fetchone() is not None

    def engagements_in_last(self, action: str, hours: float) -> int:
        cutoff = time.time() - hours * 3600
        return self.conn.execute(
            "SELECT COUNT(*) c FROM sent_engagements WHERE action=? AND sent_at > ?",
            (action, cutoff),
        ).fetchone()["c"]

    def last_engagement_time(self, action: str | None = None) -> float:
        if action:
            row = self.conn.execute(
                "SELECT MAX(sent_at) m FROM sent_engagements WHERE action=?", (action,)
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT MAX(sent_at) m FROM sent_engagements"
            ).fetchone()
        return row["m"] or 0.0

    # ---------- bandit ----------
    def get_arm(self, fmt: str) -> tuple[float, float]:
        row = self.conn.execute("SELECT alpha, beta FROM arms WHERE fmt=?", (fmt,)).fetchone()
        if not row:
            self.conn.execute("INSERT INTO arms (fmt) VALUES (?)", (fmt,))
            self.conn.commit()
            return 1.0, 1.0
        return row["alpha"], row["beta"]

    def update_arm(self, fmt: str, success: bool):
        a, b = self.get_arm(fmt)
        if success:
            a += 1
        else:
            b += 1
        self.conn.execute("UPDATE arms SET alpha=?, beta=? WHERE fmt=?", (a, b, fmt))
        self.conn.commit()

    def arm_table(self) -> dict:
        return {r["fmt"]: (r["alpha"], r["beta"])
                for r in self.conn.execute("SELECT * FROM arms").fetchall()}

    # ---------- followers ----------
    def log_followers(self, n: int):
        self.conn.execute(
            "INSERT OR REPLACE INTO follower_log VALUES (?, ?)", (time.time(), n)
        )
        self.conn.commit()

    def follower_history(self, n: int = 14) -> list[tuple[float, int]]:
        rows = self.conn.execute(
            "SELECT * FROM follower_log ORDER BY ts DESC LIMIT ?", (n,)
        ).fetchall()
        return [(r["ts"], r["followers"]) for r in reversed(rows)]
