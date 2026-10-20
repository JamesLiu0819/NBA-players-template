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
_memory_feedback = []
_memory_users = {}        # id -> {"id", "google_sub", "email", "name"}
_memory_results = []      # [{"user_id", "pool", "lang", "axis_answers", "body_answers"}]
_memory_favorites = []    # [{"user_id", "player_id", "pool"}]


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
    outage at startup should degrade to "no visit counter", not take the
    entire site down. This actually happened once (2026-10): the database
    was on Render's free-tier Postgres, which expires 90 days after
    creation unless upgraded. It expired, and the site kept running the
    whole time on the in-memory fallback below. DATABASE_URL now points
    at a Neon free-tier database instead, which has no such expiry (see
    the 2026-09-15 design doc for the counter design itself), but this
    guard stays regardless -- any hosted DB can have a transient outage.
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
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback (
                        id BIGSERIAL PRIMARY KEY,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        rating SMALLINT,
                        message TEXT,
                        lang TEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id BIGSERIAL PRIMARY KEY,
                        google_sub TEXT NOT NULL UNIQUE,
                        email TEXT NOT NULL,
                        name TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS results (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(id),
                        pool TEXT NOT NULL,
                        lang TEXT NOT NULL,
                        axis_answers JSONB NOT NULL,
                        body_answers JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS favorites (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(id),
                        player_id TEXT NOT NULL,
                        pool TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        UNIQUE (user_id, player_id, pool)
                    )
                    """
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


def save_feedback(rating, message, lang):
    """Store one feedback row. Postgres when DATABASE_URL is set; otherwise
    an in-memory list (local dev / tests). Errors are raised to the caller,
    which turns them into a retryable response -- unlike the visit counter,
    a feedback write that silently disappears would lose the user's input.
    """
    conn = _get_connection()
    if conn is None:
        _memory_feedback.append({"rating": rating, "message": message, "lang": lang})
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feedback (rating, message, lang) VALUES (%s, %s, %s)",
                (rating, message, lang),
            )
        conn.commit()
    finally:
        conn.close()


def get_or_create_user(google_sub, email, name):
    """Look up a user by their Google `sub` claim, creating one on first
    login. Email/name are refreshed from Google on every login (an upsert,
    not a plain insert-if-missing) since Google is the source of truth for
    both -- only google_sub is treated as the stable identity.
    """
    conn = _get_connection()
    if conn is None:
        for user in _memory_users.values():
            if user["google_sub"] == google_sub:
                user["email"] = email
                user["name"] = name
                return dict(user)
        new_id = len(_memory_users) + 1
        user = {"id": new_id, "google_sub": google_sub, "email": email, "name": name}
        _memory_users[new_id] = user
        return dict(user)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (google_sub, email, name)
                VALUES (%s, %s, %s)
                ON CONFLICT (google_sub) DO UPDATE SET email = EXCLUDED.email, name = EXCLUDED.name
                RETURNING id, google_sub, email, name
                """,
                (google_sub, email, name),
            )
            row = cur.fetchone()
        conn.commit()
        return {"id": row[0], "google_sub": row[1], "email": row[2], "name": row[3]}
    finally:
        conn.close()


def save_result(user_id, pool, lang, axis_answers, body_answers):
    """Append one raw-answer snapshot to `results`. Insert-only by design
    (see the 2026-10-21 design doc, section 3.3) -- never UPDATE/DELETE
    this table from application code. Raises on failure, same contract as
    save_feedback: the caller (POST /api/template-results) decides whether
    a failed write here should affect the response.
    """
    conn = _get_connection()
    if conn is None:
        _memory_results.append({
            "user_id": user_id, "pool": pool, "lang": lang,
            "axis_answers": axis_answers, "body_answers": body_answers,
        })
        return
    from psycopg.types.json import Json
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO results (user_id, pool, lang, axis_answers, body_answers)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, pool, lang, Json(axis_answers), Json(body_answers)),
            )
        conn.commit()
    finally:
        conn.close()


def get_latest_result(user_id):
    """The most recently saved result for this user, or None if they've
    never submitted one while logged in. Returns the raw stored answers
    (not a computed result) -- the caller re-runs compute_template_results
    on them, see the design doc section 3.3."""
    conn = _get_connection()
    if conn is None:
        rows = [r for r in _memory_results if r["user_id"] == user_id]
        if not rows:
            return None
        latest = rows[-1]
        return {
            "pool": latest["pool"], "lang": latest["lang"],
            "axis_answers": latest["axis_answers"], "body_answers": latest["body_answers"],
        }
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pool, lang, axis_answers, body_answers FROM results
                WHERE user_id = %s ORDER BY created_at DESC LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return {"pool": row[0], "lang": row[1], "axis_answers": row[2], "body_answers": row[3]}
    finally:
        conn.close()


def list_favorites(user_id):
    conn = _get_connection()
    if conn is None:
        return [
            {"player_id": f["player_id"], "pool": f["pool"]}
            for f in _memory_favorites if f["user_id"] == user_id
        ]
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT player_id, pool FROM favorites WHERE user_id = %s ORDER BY created_at",
                (user_id,),
            )
            rows = cur.fetchall()
        return [{"player_id": r[0], "pool": r[1]} for r in rows]
    finally:
        conn.close()


def add_favorite(user_id, player_id, pool):
    """Idempotent: favoriting the same (user, player, pool) twice is a
    no-op, not an error -- the UNIQUE constraint backs this on Postgres,
    and the in-memory path checks for the duplicate explicitly."""
    conn = _get_connection()
    if conn is None:
        if not any(
            f["user_id"] == user_id and f["player_id"] == player_id and f["pool"] == pool
            for f in _memory_favorites
        ):
            _memory_favorites.append({"user_id": user_id, "player_id": player_id, "pool": pool})
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO favorites (user_id, player_id, pool) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (user_id, player_id, pool),
            )
        conn.commit()
    finally:
        conn.close()


def remove_favorite(user_id, player_id, pool):
    """Idempotent: removing a favorite that doesn't exist is a no-op."""
    conn = _get_connection()
    if conn is None:
        _memory_favorites[:] = [
            f for f in _memory_favorites
            if not (f["user_id"] == user_id and f["player_id"] == player_id and f["pool"] == pool)
        ]
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM favorites WHERE user_id = %s AND player_id = %s AND pool = %s",
                (user_id, player_id, pool),
            )
        conn.commit()
    finally:
        conn.close()


def list_feedback():
    """All feedback rows, newest first, for the owner's in-browser admin
    view. Postgres rows carry a real created_at; the in-memory fallback
    (local dev/tests) never tracked one, so this returns created_at=None
    there -- the only path this function's own tests exercise, matching
    this project's existing convention of not testing against a real
    Postgres (see this file's own InMemoryVisitCounterTest docstring)."""
    conn = _get_connection()
    if conn is None:
        return [dict(f, created_at=None) for f in reversed(_memory_feedback)]
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT created_at, rating, message, lang FROM feedback ORDER BY created_at DESC")
            rows = cur.fetchall()
        return [{"created_at": r[0], "rating": r[1], "message": r[2], "lang": r[3]} for r in rows]
    finally:
        conn.close()
