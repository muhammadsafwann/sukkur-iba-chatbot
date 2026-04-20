"""
analytics.py
Logs each user query to a SQLite database and provides protected stats endpoints.
"""

import os
import sqlite3
import time
from pathlib import Path
from fastapi import HTTPException

DB_PATH = Path(__file__).parent.parent / "analytics.db"

# Load admin API key from environment — never hardcode secrets in source
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")


def init_db():
    """Create the analytics table if it doesn't exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                query TEXT NOT NULL
            )
        """)
        conn.commit()


def log_query(query: str):
    """Insert a query into the database."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO queries (timestamp, query) VALUES (?, ?)",
            (int(time.time()), query)
        )
        conn.commit()


def get_stats(limit: int = 100):
    """Return total count and recent queries."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM queries")
        total = cur.fetchone()[0]
        cur = conn.execute(
            "SELECT timestamp, query FROM queries ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        recent = [{"timestamp": ts, "query": q} for ts, q in cur.fetchall()]
    return {"total": total, "recent": recent}


def get_daily_counts(days: int = 7) -> dict:
    """
    Return a {date_string: count} mapping for the last N days,
    computed entirely in SQL so it is never limited by the Python-side
    'recent' query cap.  Uses SQLite's 'localtime' modifier so day
    boundaries match the server's local timezone — consistent with the
    time.localtime() calls used elsewhere in the dashboard.
    """
    since = int(time.time()) - days * 86400
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            SELECT date(timestamp, 'unixepoch', 'localtime') AS day,
                   COUNT(*) AS cnt
            FROM   queries
            WHERE  timestamp >= ?
            GROUP  BY day
            """,
            (since,)
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def verify_admin_key(api_key: str):
    """Check if the provided key matches the configured admin key."""
    if not ADMIN_API_KEY or api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


# Initialise the database when the module is first imported.
# api.py's lifespan handler also calls this explicitly so startup
# errors are surfaced with a clear log message.
init_db()