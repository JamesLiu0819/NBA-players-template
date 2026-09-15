# 用途：site_stats 表的 Postgres 連線跟遞增邏輯。沒有 DATABASE_URL 環境變數
# 時(本機開發、跑測試套件)自動退化成進程內的記憶體計數器，呼叫端不需要
# 知道現在是哪一種模式。見
# docs/superpowers/specs/2026-09-15-visit-counter-design.md。
# 可手動調整的變數：無。
"""Visit-counter persistence: Postgres when DATABASE_URL is set, an
in-memory counter otherwise (local dev / tests).
"""
import os
import sys

_memory_visit_count = 0


def _get_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return None
    import psycopg
    return psycopg.connect(database_url)


def init_db():
    """Idempotently ensure the site_stats table and its single row exist.
    No-op when DATABASE_URL isn't set. Call once at process startup.

    Connection/schema errors are caught and logged, not raised -- a DB
    outage at startup (e.g. the Render free-tier Postgres expiring after
    90 days, see the 2026-09-15 design doc) should degrade to "no visit
    counter", not take the entire site down.
    """
    try:
        conn = _get_connection()
        if conn is None:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS site_stats (
                        id INTEGER PRIMARY KEY,
                        visit_count BIGINT NOT NULL DEFAULT 0
                    )
                    """
                )
                cur.execute(
                    "INSERT INTO site_stats (id, visit_count) VALUES (1, 0) ON CONFLICT (id) DO NOTHING"
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"init_db: visit counter unavailable ({e})", file=sys.stderr)


def increment_visit_count():
    """Increment the visit counter by 1 and return the new value.

    Uses Postgres (DATABASE_URL) when available; otherwise increments an
    in-memory counter local to this process -- the path local dev and the
    test suite actually exercise (2026-09-15 design doc).
    """
    global _memory_visit_count
    conn = _get_connection()
    if conn is None:
        _memory_visit_count += 1
        return _memory_visit_count

    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE site_stats SET visit_count = visit_count + 1 WHERE id = 1 RETURNING visit_count"
            )
            new_count = cur.fetchone()[0]
        conn.commit()
        return new_count
    finally:
        conn.close()
