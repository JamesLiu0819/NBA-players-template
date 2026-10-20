# Google Login + Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional Google-account login to the NBA 球員模板 site, giving logged-in users cross-device access to their latest quiz result, a favorites list, and giving the site owner a read-only in-browser view of feedback — all while keeping every existing feature fully usable without logging in.

**Architecture:** Authlib handles the Google OAuth 2.0 dance inside the existing Flask app; login state lives in Flask's signed session cookie (no new session store). Three new Postgres tables (`users`, `results`, `favorites`) follow `server/db.py`'s existing `_get_connection() → None`/in-memory-fallback pattern used by `site_stats`/`feedback`. The frontend stays a single-file vanilla-JS SPA; this feature adds two new pages ("我的收藏", an admin-only feedback page) to the existing 4-page hard-isolation router, plus a topnav auth control and a ★ button on the 10-player comparison cards.

**Tech Stack:** Flask 3.1.3, Authlib (new), psycopg[binary] 3.2.3, Neon Postgres, vanilla JS (no framework/build step).

**Spec:** `docs/superpowers/specs/2026-10-21-google-login-accounts-design.md`

## Global Constraints

- Code and commit messages in English; all UI copy in Traditional Chinese with Simplified (`zh-Hans`) and English (`en`) translations added alongside every new string — `UI_STRINGS` in `src/ui/index.html` must stay in sync across all three keys (CLAUDE.md).
- `/src/engine` stays pure — nothing in this plan touches it; all new code lives in `server/` and `src/ui/index.html` (CLAUDE.md).
- `pool` is always one of the two existing strings `"current"`/`"alltime"` (the `POOLS` tuple in `server/app.py:127`) — reuse that constant and its existing validation pattern; never invent a new pool value.
- `lang` is always one of `SUPPORTED_LANGUAGES = ("zh", "zh-Hans", "en")` (`server/app.py:126`).
- New third-party dependency: `Authlib`, added to `server/requirements.txt`.
- New environment variables (set on Render, never committed): `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ADMIN_EMAIL`. The app must not crash at startup or on `/auth/login` if any of these are unset — degrade to "login unavailable" / "no admin configured", matching `db.py`'s existing graceful-degradation style (`init_db()` never raises).
- `results` is append-only: application code only ever `INSERT`s into it, never `UPDATE`/`DELETE`.
- `/api/admin/feedback` returns 404 (never 403) whenever the caller isn't the configured admin — the route must look indistinguishable from a route that doesn't exist.
- Test commands (run from repo root unless noted): `PYTHONPATH=src python3 -m unittest discover -s tests/engine`, `PYTHONPATH=.:src python3 -m unittest discover -s tests/scripts`, `(cd server && ../.venv/bin/python3 -m unittest test_app test_db)`.
- No new frontend automated test framework. Frontend verification uses this project's existing headless-Chrome-via-CDP manual-check approach (see Task 12), not Playwright/Selenium/etc.
- Creating the actual Google Cloud OAuth client (Client ID/Secret) and setting the four env vars on Render is a one-time manual step the user does themselves — it is a prerequisite for *testing the real login flow end-to-end*, not for building or unit-testing any task below (every backend test in this plan mocks Authlib's Google call; see Task 2).

## Review Focus

The spec describes the desired behavior; these are the inputs/conditions it implies but that no single task's happy-path tests would catch on their own. Each line below gets its own test in the task that owns the code.

1. **Favoriting an unknown/typo'd `player_id`** — `POST /api/favorites` must 404, not silently store a dangling id or 500 (Task 5).
2. **Double-submitting the same favorite** (double-click, or a retried request) — the `UNIQUE(user_id, player_id, pool)` constraint means a second `POST` for the same triple must still return `200 {"ok": true}`, not a constraint-violation 500 (Task 5).
3. **Google's ID token omitting the optional `name` claim** — `get_or_create_user`/`/auth/callback` must store `name = NULL`/`None` rather than crashing on a missing dict key (Task 1, Task 2).
4. **A favorites write landing on a session whose `user_id` no longer exists in the DB** (e.g. a stale session surviving a manual DB edit) — `add_favorite`/`remove_favorite` must not blow up into a bare 500; the route catches the DB exception and returns 503, matching the existing `/api/feedback` error-handling idiom (Task 5).
5. **A logged-in, non-admin user hitting `/api/admin/feedback`** — this is the *common* case once Task 8 ships, because every logged-in session calls this endpoint once to detect admin status. It must 404 exactly like the logged-out case, exercised as its own test rather than assumed identical (Task 6).

## Clarifications made while planning (flagged for your review)

The approved spec left a few mechanics underspecified; here's how this plan resolves each one. Flag any you'd rather resolve differently when you review this plan:

- **`top_10` entries need a stable `player_id` to favorite**, but `/api/template-results`'s existing `top_10` shape (`rank/name/team/coordinates/distance/fit_stars/notable_traits/dominant_diff_axis/growth_recommendation/training_plans`) has no id field today — only a display `name`. Task 3 adds an additive `"id"` field (the same id `/api/players` and `/api/player-training-plan` already use) and updates the one existing test that asserts the exact key set.
- **`GET /api/admin/feedback`'s spec signature includes a `lang` query param**, but an admin viewing their own feedback has no reason to see only one language's submissions filtered out — every other route's `lang` param exists to pick which *UI content* to load, which doesn't apply to raw feedback rows. This plan drops `lang` filtering for this endpoint: it returns every feedback row, in every language, newest first (each row already carries its own `lang` field, matching the spec's response shape).
- **The spec's "前端整合" section never described a UI for goal #3** (viewing feedback in-browser) even though section 2's "這次做" list and the admin API both commit to it. Task 8 adds the minimal surface: a nav tab that's invisible to everyone except the detected admin, showing a read-only, newest-first list — no new page design beyond that.
- **`GET /api/my-results/latest` needs to tell the frontend which `pool`/`lang` produced the stored result**, so the frontend can set `state.pool` correctly before any later custom-player search — the literal spec text says the response is identical to `/api/template-results`'s, which doesn't carry that information (the caller already knows what it just submitted). This plan adds two additive top-level fields, `"pool"` and `"lang"`, to this one response only (Task 4).
- **Jumping from a favorited player straight into their training plan** only works today if the favorite's `pool` matches whatever pool the user's *current* quiz results happen to be in — the existing custom-player-search code hard-reads `state.pool` instead of taking a pool per call. Task 10 generalizes `fetchCustomPlayerTrainingPlan`/`selectCustomPlayer` to take an explicit `pool` argument (default `state.pool`, so the existing search box is unaffected) so a favorite from the *other* pool still resolves correctly.

---

### Task 1: Persistence layer — `users`, `results`, `favorites` tables

**Files:**
- Modify: `server/db.py`
- Test: `server/test_db.py`

**Interfaces:**
- Produces: `get_or_create_user(google_sub: str, email: str, name: str | None) -> dict` with keys `id, google_sub, email, name`.
- Produces: `save_result(user_id: int, pool: str, lang: str, axis_answers: list, body_answers: list) -> None`. Raises on failure (same contract as `save_feedback` — the caller decides whether to swallow it).
- Produces: `get_latest_result(user_id: int) -> dict | None` with keys `pool, lang, axis_answers, body_answers` (or `None` if the user has never submitted one).
- Produces: `list_favorites(user_id: int) -> list[dict]`, each `{"player_id": str, "pool": str}`.
- Produces: `add_favorite(user_id: int, player_id: str, pool: str) -> None`. Idempotent (a repeat call is a no-op, not an error). Raises on a real DB failure.
- Produces: `remove_favorite(user_id: int, player_id: str, pool: str) -> None`. Idempotent (removing a non-favorite is a no-op).
- Produces: `list_feedback() -> list[dict]`, each `{"created_at": datetime | None, "rating": int | None, "message": str | None, "lang": str}`, newest first. `created_at` is `None` on the in-memory fallback path (it was never tracked there) — this is the only path the test suite exercises, matching this project's existing convention of not testing against a real Postgres (see `test_db.py`'s own docstring).

- [ ] **Step 1: Write the failing tests**

Append to `server/test_db.py` (same file, same `InMemoryVisitCounterTest`-style pattern — these don't need a fresh `importlib.reload` since they don't touch `site_stats`, but keep the "force the in-memory path" setup so they run the same everywhere):

```python
class InMemoryUserAndResultTest(unittest.TestCase):
    def setUp(self):
        self._original_database_url = os.environ.pop("DATABASE_URL", None)
        import db
        importlib.reload(db)
        self.db = db

    def tearDown(self):
        if self._original_database_url is not None:
            os.environ["DATABASE_URL"] = self._original_database_url

    def test_get_or_create_user_creates_on_first_login(self):
        user = self.db.get_or_create_user("sub-1", "a@example.com", "Alice")
        self.assertEqual(user["google_sub"], "sub-1")
        self.assertEqual(user["email"], "a@example.com")
        self.assertEqual(user["name"], "Alice")
        self.assertIsInstance(user["id"], int)

    def test_get_or_create_user_returns_same_id_on_repeat_login(self):
        first = self.db.get_or_create_user("sub-2", "b@example.com", "Bob")
        second = self.db.get_or_create_user("sub-2", "b@example.com", "Bob")
        self.assertEqual(first["id"], second["id"])

    def test_get_or_create_user_refreshes_email_and_name_on_repeat_login(self):
        self.db.get_or_create_user("sub-3", "old@example.com", "Old Name")
        updated = self.db.get_or_create_user("sub-3", "new@example.com", "New Name")
        self.assertEqual(updated["email"], "new@example.com")
        self.assertEqual(updated["name"], "New Name")

    def test_get_or_create_user_handles_missing_name_claim(self):
        user = self.db.get_or_create_user("sub-4", "noname@example.com", None)
        self.assertIsNone(user["name"])

    def test_save_result_and_get_latest_result_round_trip(self):
        user = self.db.get_or_create_user("sub-5", "c@example.com", "Carol")
        axis = [{"question_id": "q1", "score": 3}]
        body = [{"question_id": "b1", "value": 190}]
        self.db.save_result(user["id"], "current", "zh", axis, body)
        latest = self.db.get_latest_result(user["id"])
        self.assertEqual(latest, {"pool": "current", "lang": "zh", "axis_answers": axis, "body_answers": body})

    def test_get_latest_result_returns_the_most_recent_of_several(self):
        user = self.db.get_or_create_user("sub-6", "d@example.com", "Dan")
        self.db.save_result(user["id"], "current", "zh", [{"question_id": "q1", "score": 1}], [])
        self.db.save_result(user["id"], "alltime", "en", [{"question_id": "q1", "score": 5}], [])
        latest = self.db.get_latest_result(user["id"])
        self.assertEqual(latest["pool"], "alltime")
        self.assertEqual(latest["lang"], "en")

    def test_get_latest_result_is_none_for_a_user_with_no_results(self):
        user = self.db.get_or_create_user("sub-7", "e@example.com", "Eve")
        self.assertIsNone(self.db.get_latest_result(user["id"]))


class InMemoryFavoritesTest(unittest.TestCase):
    def setUp(self):
        self._original_database_url = os.environ.pop("DATABASE_URL", None)
        import db
        importlib.reload(db)
        self.db = db
        self.user = self.db.get_or_create_user("sub-fav", "fav@example.com", "Fav")

    def tearDown(self):
        if self._original_database_url is not None:
            os.environ["DATABASE_URL"] = self._original_database_url

    def test_add_favorite_then_list_favorites(self):
        self.db.add_favorite(self.user["id"], "amen_thompson", "current")
        self.assertEqual(self.db.list_favorites(self.user["id"]), [{"player_id": "amen_thompson", "pool": "current"}])

    def test_adding_the_same_favorite_twice_does_not_duplicate_it(self):
        self.db.add_favorite(self.user["id"], "amen_thompson", "current")
        self.db.add_favorite(self.user["id"], "amen_thompson", "current")
        self.assertEqual(len(self.db.list_favorites(self.user["id"])), 1)

    def test_remove_favorite(self):
        self.db.add_favorite(self.user["id"], "amen_thompson", "current")
        self.db.remove_favorite(self.user["id"], "amen_thompson", "current")
        self.assertEqual(self.db.list_favorites(self.user["id"]), [])

    def test_removing_a_favorite_that_was_never_added_is_a_no_op(self):
        self.db.remove_favorite(self.user["id"], "does_not_exist", "current")
        self.assertEqual(self.db.list_favorites(self.user["id"]), [])

    def test_favorites_are_scoped_per_user(self):
        other = self.db.get_or_create_user("sub-fav-2", "fav2@example.com", "Fav2")
        self.db.add_favorite(self.user["id"], "amen_thompson", "current")
        self.assertEqual(self.db.list_favorites(other["id"]), [])


class InMemoryFeedbackListTest(unittest.TestCase):
    def setUp(self):
        self._original_database_url = os.environ.pop("DATABASE_URL", None)
        import db
        importlib.reload(db)
        self.db = db

    def tearDown(self):
        if self._original_database_url is not None:
            os.environ["DATABASE_URL"] = self._original_database_url

    def test_list_feedback_returns_saved_rows_newest_first(self):
        self.db.save_feedback(4, "很準", "zh")
        self.db.save_feedback(2, "還可以", "en")
        rows = self.db.list_feedback()
        self.assertEqual([r["rating"] for r in rows], [2, 4])
        self.assertEqual(rows[0]["lang"], "en")
        self.assertIsNone(rows[0]["created_at"])

    def test_list_feedback_is_empty_initially(self):
        self.assertEqual(self.db.list_feedback(), [])
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd server && ../.venv/bin/python3 -m unittest test_db -v`
Expected: `AttributeError: module 'db' has no attribute 'get_or_create_user'` (and similar for the other new functions) — they don't exist yet.

- [ ] **Step 3: Add the three tables to `init_db()`**

In `server/db.py`, inside `init_db()`'s `try` block, right after the existing `feedback` table's `cur.execute(...)` call (the one creating `CREATE TABLE IF NOT EXISTS feedback (...)`), add:

```python
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
```

- [ ] **Step 4: Add the in-memory stores and the new functions**

Near the top of `server/db.py`, next to the existing `_memory_visit_count`/`_memory_feedback`:

```python
_memory_users = {}        # id -> {"id", "google_sub", "email", "name"}
_memory_results = []      # [{"user_id", "pool", "lang", "axis_answers", "body_answers"}]
_memory_favorites = []    # [{"user_id", "player_id", "pool"}]
```

Append these functions at the end of `server/db.py`:

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd server && ../.venv/bin/python3 -m unittest test_db -v`
Expected: all tests pass, including the pre-existing `InMemoryVisitCounterTest` ones (unaffected by this change).

- [ ] **Step 6: Commit**

```bash
git add server/db.py server/test_db.py
git commit -m "db: add users/results/favorites tables and feedback listing"
```

---

### Task 2: Google OAuth login (`/auth/login`, `/auth/callback`, `/auth/logout`, `GET /api/me`)

**Files:**
- Modify: `server/requirements.txt`
- Modify: `server/app.py`
- Test: `server/test_app.py`

**Interfaces:**
- Consumes: `get_or_create_user` from `server/db.py` (Task 1).
- Produces: module-level `oauth` object in `server/app.py` (an Authlib `OAuth` instance with a `google` client registered on it when configured) — later tasks don't call this directly, but Task 8's admin-detection probe and this task's own tests patch `oauth.google.authorize_access_token`.
- Produces: `GOOGLE_LOGIN_CONFIGURED: bool` module-level constant in `server/app.py`.
- Produces: Flask `session` now carries `user_id` (int), `email` (str), `name` (str or None) once logged in. Every later route that needs login state reads `session.get("user_id")` / `session.get("email")` directly — no new helper function needed for this.

- [ ] **Step 1: Add the dependency**

In `server/requirements.txt`, add a line:

```
Authlib==1.3.2
```

Install it locally: `../.venv/bin/pip install -r server/requirements.txt` (run from `server/`, or adjust the path to wherever this project's venv lives — same one the existing test commands use).

- [ ] **Step 2: Write the failing tests**

Near the very top of `server/test_app.py`, **before** the existing `from app import app` line, add:

```python
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
```

(This must run before `app.py` is imported, since Google OAuth client registration happens at module import time. Every other test class in this file is unaffected — these three env vars only gate whether the `google` OAuth client gets registered and what secret Flask's session cookie is signed with.)

Then add a new test class to `server/test_app.py`:

```python
from unittest.mock import patch
import app as app_module


class AuthTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_me_reports_logged_out_by_default(self):
        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"email": None, "name": None})

    def test_login_redirects_to_google_without_hitting_the_network(self):
        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response.location)

    def test_callback_creates_a_user_and_logs_them_in(self):
        fake_token = {"userinfo": {"sub": "google-sub-1", "email": "person@example.com", "name": "Person"}}
        with patch.object(app_module.oauth.google, "authorize_access_token", return_value=fake_token):
            response = self.client.get("/auth/callback")
        self.assertEqual(response.status_code, 302)
        me = self.client.get("/api/me").get_json()
        self.assertEqual(me, {"email": "person@example.com", "name": "Person"})

    def test_callback_handles_a_missing_name_claim(self):
        fake_token = {"userinfo": {"sub": "google-sub-2", "email": "noname@example.com"}}
        with patch.object(app_module.oauth.google, "authorize_access_token", return_value=fake_token):
            self.client.get("/auth/callback")
        me = self.client.get("/api/me").get_json()
        self.assertIsNone(me["name"])

    def test_repeat_login_reuses_the_same_user(self):
        fake_token = {"userinfo": {"sub": "google-sub-3", "email": "dup@example.com", "name": "Dup"}}
        with patch.object(app_module.oauth.google, "authorize_access_token", return_value=fake_token):
            self.client.get("/auth/callback")
            self.client.get("/auth/callback")
        # two logins, no error -- get_or_create_user's upsert handles this (Task 1)
        me = self.client.get("/api/me").get_json()
        self.assertEqual(me["email"], "dup@example.com")

    def test_logout_clears_the_session(self):
        fake_token = {"userinfo": {"sub": "google-sub-4", "email": "bye@example.com", "name": "Bye"}}
        with patch.object(app_module.oauth.google, "authorize_access_token", return_value=fake_token):
            self.client.get("/auth/callback")
        response = self.client.post("/auth/logout")
        self.assertEqual(response.status_code, 302)
        me = self.client.get("/api/me").get_json()
        self.assertEqual(me, {"email": None, "name": None})
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app -v`
Expected: `ImportError`/`AttributeError` referencing `app.oauth` or 404s on `/auth/login` — none of these routes exist yet.

- [ ] **Step 4: Implement the OAuth client and routes**

In `server/app.py`, add these imports near the top (alongside the existing `from flask import ...` line):

```python
from flask import Flask, jsonify, redirect, request, send_from_directory, session, url_for  # noqa: E402
from authlib.integrations.flask_client import OAuth  # noqa: E402

from db import (  # noqa: E402
    get_or_create_user,
    increment_visit_count,
    init_db,
    save_feedback,
)
```

(This replaces the existing `from flask import Flask, jsonify, request, send_from_directory` and `from db import increment_visit_count, init_db, save_feedback` lines — merge them into the two blocks above rather than leaving duplicates.)

Right after `app = Flask(__name__, static_folder=None)` and before `init_db()`, add:

```python
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-do-not-use-in-production")

oauth = OAuth(app)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_LOGIN_CONFIGURED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
if GOOGLE_LOGIN_CONFIGURED:
    # Static endpoints (not server_metadata_url) so this never needs a live
    # network call except the real token exchange in authorize_access_token
    # -- authorize_redirect below must work offline for tests to mock it.
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        access_token_url="https://oauth2.googleapis.com/token",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
        client_kwargs={"scope": "openid email profile"},
    )
```

Add the routes (anywhere after the `app`/`oauth` setup above, e.g. right before the `@app.route("/api/form-data", ...)` route):

```python
@app.route("/auth/login")
def auth_login():
    if not GOOGLE_LOGIN_CONFIGURED:
        return jsonify({"error": "login is not configured"}), 503
    return oauth.google.authorize_redirect(url_for("auth_callback", _external=True))


@app.route("/auth/callback")
def auth_callback():
    if not GOOGLE_LOGIN_CONFIGURED:
        return jsonify({"error": "login is not configured"}), 503
    token = oauth.google.authorize_access_token()
    userinfo = token["userinfo"]
    user = get_or_create_user(userinfo["sub"], userinfo["email"], userinfo.get("name"))
    session["user_id"] = user["id"]
    session["email"] = user["email"]
    session["name"] = user["name"]
    return redirect("/")


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return redirect("/")


@app.route("/api/me", methods=["GET"])
def api_me():
    return jsonify({"email": session.get("email"), "name": session.get("name")})
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app -v`
Expected: all tests pass, including every pre-existing test class in this file.

- [ ] **Step 6: Commit**

```bash
git add server/requirements.txt server/app.py server/test_app.py
git commit -m "auth: add Google OAuth login via Authlib, GET /api/me"
```

---

### Task 3: Save a result on submit when logged in, and expose `id` on `top_10`

**Files:**
- Modify: `server/app.py`
- Test: `server/test_app.py`

**Interfaces:**
- Consumes: `save_result` from `server/db.py` (Task 1); `session.get("user_id")` from Task 2.
- Produces: every `top_10` entry from `POST /api/template-results` (and, from Task 4 onward, `GET /api/my-results/latest`) now includes `"id"` — the same player id used by `/api/players` and `/api/player-training-plan`. All other `top_10` fields are unchanged.

- [ ] **Step 1: Write the failing tests**

In `server/test_app.py`, update the existing `test_top_10_entries_have_expected_fields` test (inside `TemplateResultsTest`) to expect the new field:

```python
    def test_top_10_entries_have_expected_fields(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)
        top_player = response.get_json()["top_10"][0]

        self.assertEqual(
            set(top_player.keys()),
            {
                "id", "rank", "name", "team", "coordinates", "distance", "fit_stars",
                "notable_traits", "dominant_diff_axis", "growth_recommendation",
                "training_plans",
            },
        )
        self.assertEqual(top_player["rank"], 1)
        self.assertEqual(set(top_player["coordinates"].keys()), {"A", "B1", "B2", "C1", "C2", "D"})
```

Add a new test class:

```python
class SaveResultOnSubmitTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.questions = load_json(ROOT / "data" / "zh" / "題庫.json")
        self.payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
        }

    def _login(self, sub, email):
        fake_token = {"userinfo": {"sub": sub, "email": email, "name": "Test"}}
        from unittest.mock import patch
        import app as app_module
        with patch.object(app_module.oauth.google, "authorize_access_token", return_value=fake_token):
            self.client.get("/auth/callback")

    def test_logged_in_submission_is_saved_and_retrievable(self):
        self._login("sub-save-1", "save1@example.com")
        self.client.post("/api/template-results", json=self.payload)
        latest = self.client.get("/api/my-results/latest")
        self.assertEqual(latest.status_code, 200)

    def test_logged_out_submission_is_not_saved(self):
        response = self.client.get("/api/my-results/latest")
        self.assertEqual(response.status_code, 204)
        self.client.post("/api/template-results", json=self.payload)
        still_nothing = self.client.get("/api/my-results/latest")
        self.assertEqual(still_nothing.status_code, 204)

    def test_a_db_write_failure_does_not_break_the_response(self):
        self._login("sub-save-2", "save2@example.com")
        import db
        original = db.save_result
        db.save_result = lambda *a, **kw: (_ for _ in ()).throw(ConnectionError("simulated"))
        try:
            response = self.client.post("/api/template-results", json=self.payload)
            self.assertEqual(response.status_code, 200)
        finally:
            db.save_result = original
```

(This task's second test, `test_logged_in_submission_is_saved_and_retrievable`, calls `GET /api/my-results/latest`, which doesn't exist until Task 4 — that's expected; this test and Task 4's route are written together conceptually, but since Task 4 is the very next task and this plan is executed in order, leave this test in place now and it will pass once Task 4 lands. If you're running Task 3's tests in isolation before starting Task 4, this one test will fail with a 404 — that's the correct, expected state at this point.)

- [ ] **Step 2: Run the tests to verify the `top_10` id-field test fails and the save-tracking logic doesn't exist yet**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app.TemplateResultsTest.test_top_10_entries_have_expected_fields -v`
Expected: FAIL (missing `"id"` key).

- [ ] **Step 3: Add `id` to `top_10` and save the result when logged in**

In `server/app.py`'s `compute_template_results`, inside the `for rank, player in enumerate(ranked_players, start=1):` loop, add `"id": player["id"],` as the first key of the dict passed to `top_10.append(...)`:

```python
    for rank, player in enumerate(ranked_players, start=1):
        top_10.append({
            "id": player["id"],
            "rank": rank,
            "name": player["name"],
            "team": player["team"],
            "coordinates": player["coordinates"],
            "distance": player["distance"],
            "fit_stars": player["fit_stars"],
            "notable_traits": player["notable_traits"],
            "dominant_diff_axis": player["dominant_diff_axis"],
            "growth_recommendation": describe_growth_recommendation(player, skills_by_id, lang),
            "training_plans": {
                env: format_training_plan(
                    build_training_plan(
                        skills, ENV_WEIGHTS[env], coordinates, player["coordinates"],
                        player["signature_skill_id"], top_n=TRAINING_PLAN_TOP_N,
                    ),
                    skills_by_id,
                    drills_by_key,
                )
                for env in environment_codes()
            },
        })
```

(`rank_similar_players_by_style_and_body` already returns each player's full dict, which includes `id` — see how `player["name"]`/`player["team"]` are already pulled from the same dict a few lines above.)

In `api_template_results`, after computing `results` successfully (after the `try`/`except (ValueError, KeyError)` block, before `return jsonify(results)`), add:

```python
    user_id = session.get("user_id")
    if user_id is not None:
        try:
            save_result(user_id, pool, lang, payload["axis_answers"], payload.get("body_answers") or [])
        except Exception as e:
            print(f"save_result failed: {e}", file=sys.stderr)

    return jsonify(results)
```

Add `save_result` to the `from db import (...)` block added in Task 2.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app -v`
Expected: `test_top_10_entries_have_expected_fields` and the DB-failure/logged-out tests in `SaveResultOnSubmitTest` pass now. `test_logged_in_submission_is_saved_and_retrievable` still fails with 404 until Task 4 — confirm that's the *only* failure before moving on.

- [ ] **Step 5: Commit**

```bash
git add server/app.py server/test_app.py
git commit -m "api: expose player id on top_10, save result on submit when logged in"
```

---

### Task 4: `GET /api/my-results/latest`

**Files:**
- Modify: `server/app.py`
- Test: `server/test_app.py`

**Interfaces:**
- Consumes: `get_latest_result` from `server/db.py` (Task 1); `compute_template_results`, `load_data`, `load_archetypes`, `load_drills` already defined in `server/app.py`.
- Produces: `GET /api/my-results/latest` → 200 with the same shape as `POST /api/template-results`'s response plus two additive top-level fields `"pool"` and `"lang"`; or 204 with an empty body if not logged in or no stored result exists.

- [ ] **Step 1: Write the failing tests**

Add to `server/test_app.py`:

```python
class LatestResultTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.questions = load_json(ROOT / "data" / "zh" / "題庫.json")

    def _login(self, sub, email):
        fake_token = {"userinfo": {"sub": sub, "email": email, "name": "Test"}}
        from unittest.mock import patch
        import app as app_module
        with patch.object(app_module.oauth.google, "authorize_access_token", return_value=fake_token):
            self.client.get("/auth/callback")

    def test_returns_204_when_not_logged_in(self):
        response = self.client.get("/api/my-results/latest")
        self.assertEqual(response.status_code, 204)

    def test_returns_204_when_logged_in_but_never_submitted(self):
        self._login("sub-latest-1", "latest1@example.com")
        response = self.client.get("/api/my-results/latest")
        self.assertEqual(response.status_code, 204)

    def test_returns_the_recomputed_result_with_pool_and_lang(self):
        self._login("sub-latest-2", "latest2@example.com")
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
            "pool": "alltime",
            "lang": "en",
        }
        self.client.post("/api/template-results", json=payload)

        response = self.client.get("/api/my-results/latest")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["pool"], "alltime")
        self.assertEqual(data["lang"], "en")
        self.assertEqual(len(data["top_10"]), 10)
        en_names = {p["name"] for p in load_json(ROOT / "data" / "en" / "players_alltime.json")["players"]}
        self.assertTrue({row["name"] for row in data["top_10"]}.issubset(en_names))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app.LatestResultTest -v`
Expected: 404s (route doesn't exist yet).

- [ ] **Step 3: Implement the route**

Add to `server/app.py` (after `api_template_results`):

```python
@app.route("/api/my-results/latest", methods=["GET"])
def api_my_results_latest():
    user_id = session.get("user_id")
    if user_id is None:
        return "", 204

    stored = get_latest_result(user_id)
    if stored is None:
        return "", 204

    pool, lang = stored["pool"], stored["lang"]
    questions, skills, players = load_data(pool, lang)
    archetypes = load_archetypes(lang)
    drills_by_key = load_drills(lang)
    payload = {"axis_answers": stored["axis_answers"], "body_answers": stored["body_answers"]}
    try:
        results = compute_template_results(payload, questions, players, skills, archetypes, drills_by_key, lang, pool)
    except (ValueError, KeyError):
        return "", 204

    results["pool"] = pool
    results["lang"] = lang
    return jsonify(results)
```

Add `get_latest_result` to the `from db import (...)` block.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app -v`
Expected: all pass, including Task 3's previously-404ing `test_logged_in_submission_is_saved_and_retrievable`.

- [ ] **Step 5: Commit**

```bash
git add server/app.py server/test_app.py
git commit -m "api: add GET /api/my-results/latest"
```

---

### Task 5: `GET`/`POST`/`DELETE /api/favorites`

**Files:**
- Modify: `server/app.py`
- Test: `server/test_app.py`

**Interfaces:**
- Consumes: `list_favorites`, `add_favorite`, `remove_favorite` from `server/db.py` (Task 1).
- Produces: `GET /api/favorites?lang=zh` → `{"favorites": [{"player_id", "pool", "name", "team"}, ...]}`. `POST`/`DELETE /api/favorites` with body `{"player_id", "pool"}` → `{"ok": true}`. All three require login (401 otherwise).

- [ ] **Step 1: Write the failing tests**

Add to `server/test_app.py`:

```python
class FavoritesTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _login(self, sub, email):
        fake_token = {"userinfo": {"sub": sub, "email": email, "name": "Test"}}
        from unittest.mock import patch
        import app as app_module
        with patch.object(app_module.oauth.google, "authorize_access_token", return_value=fake_token):
            self.client.get("/auth/callback")

    def test_all_three_methods_require_login(self):
        self.assertEqual(self.client.get("/api/favorites").status_code, 401)
        self.assertEqual(self.client.post("/api/favorites", json={"player_id": "x", "pool": "current"}).status_code, 401)
        self.assertEqual(self.client.delete("/api/favorites", json={"player_id": "x", "pool": "current"}).status_code, 401)

    def test_add_then_list_returns_enriched_entry(self):
        self._login("sub-favapi-1", "favapi1@example.com")
        add = self.client.post("/api/favorites", json={"player_id": "amen_thompson", "pool": "current"})
        self.assertEqual(add.status_code, 200)
        self.assertEqual(add.get_json(), {"ok": True})

        listing = self.client.get("/api/favorites")
        self.assertEqual(listing.status_code, 200)
        favorites = listing.get_json()["favorites"]
        self.assertEqual(len(favorites), 1)
        self.assertEqual(favorites[0]["player_id"], "amen_thompson")
        self.assertEqual(favorites[0]["pool"], "current")
        self.assertTrue(favorites[0]["name"])
        self.assertTrue(favorites[0]["team"])

    def test_adding_an_unknown_player_id_404s(self):
        self._login("sub-favapi-2", "favapi2@example.com")
        response = self.client.post("/api/favorites", json={"player_id": "not_a_real_player", "pool": "current"})
        self.assertEqual(response.status_code, 404)

    def test_adding_the_same_favorite_twice_still_succeeds(self):
        self._login("sub-favapi-3", "favapi3@example.com")
        self.client.post("/api/favorites", json={"player_id": "amen_thompson", "pool": "current"})
        second = self.client.post("/api/favorites", json={"player_id": "amen_thompson", "pool": "current"})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(self.client.get("/api/favorites").get_json()["favorites"]), 1)

    def test_remove_favorite(self):
        self._login("sub-favapi-4", "favapi4@example.com")
        self.client.post("/api/favorites", json={"player_id": "amen_thompson", "pool": "current"})
        remove = self.client.delete("/api/favorites", json={"player_id": "amen_thompson", "pool": "current"})
        self.assertEqual(remove.status_code, 200)
        self.assertEqual(self.client.get("/api/favorites").get_json()["favorites"], [])

    def test_removing_a_non_favorite_still_succeeds(self):
        self._login("sub-favapi-5", "favapi5@example.com")
        response = self.client.delete("/api/favorites", json={"player_id": "amen_thompson", "pool": "current"})
        self.assertEqual(response.status_code, 200)

    def test_invalid_pool_400s(self):
        self._login("sub-favapi-6", "favapi6@example.com")
        response = self.client.post("/api/favorites", json={"player_id": "amen_thompson", "pool": "bogus"})
        self.assertEqual(response.status_code, 400)

    def test_missing_fields_400(self):
        self._login("sub-favapi-7", "favapi7@example.com")
        self.assertEqual(self.client.post("/api/favorites", json={}).status_code, 400)

    def test_a_db_failure_on_add_returns_503_not_500(self):
        self._login("sub-favapi-8", "favapi8@example.com")
        import db
        original = db.add_favorite
        db.add_favorite = lambda *a, **kw: (_ for _ in ()).throw(ConnectionError("simulated"))
        try:
            response = self.client.post("/api/favorites", json={"player_id": "amen_thompson", "pool": "current"})
            self.assertEqual(response.status_code, 503)
        finally:
            db.add_favorite = original
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app.FavoritesTest -v`
Expected: 404s (route doesn't exist yet).

- [ ] **Step 3: Implement the routes**

Add to `server/app.py`:

```python
FAVORITE_REQUIRED_FIELDS = ("player_id", "pool")


@app.route("/api/favorites", methods=["GET"])
def api_favorites_list():
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"error": "login required"}), 401

    lang = request.args.get("lang", "zh")
    if lang not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"invalid lang: {lang}"}), 400

    favorites = list_favorites(user_id)
    players_by_pool = {}
    enriched = []
    for fav in favorites:
        pool = fav["pool"]
        if pool not in players_by_pool:
            _q, _s, players = load_data(pool, lang)
            players_by_pool[pool] = {p["id"]: p for p in players}
        player = players_by_pool[pool].get(fav["player_id"])
        if player is None:
            continue  # stale favorite referencing a since-removed id -- skip it, don't 500
        enriched.append({"player_id": fav["player_id"], "pool": pool, "name": player["name"], "team": player["team"]})
    return jsonify({"favorites": enriched})


@app.route("/api/favorites", methods=["POST"])
def api_favorites_add():
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"error": "login required"}), 401

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "request body must be JSON"}), 400
    missing = missing_fields(payload, FAVORITE_REQUIRED_FIELDS)
    if missing:
        return jsonify({"error": f"missing required field(s): {', '.join(missing)}"}), 400

    pool = payload["pool"]
    if pool not in POOLS:
        return jsonify({"error": f"invalid pool: {pool}"}), 400

    _q, _s, players = load_data(pool, "zh")  # player id set is language-independent
    if payload["player_id"] not in {p["id"] for p in players}:
        return jsonify({"error": f"unknown player_id: {payload['player_id']}"}), 404

    try:
        add_favorite(user_id, payload["player_id"], pool)
    except Exception as e:
        print(f"add_favorite failed: {e}", file=sys.stderr)
        return jsonify({"error": "could not save favorite, please try again later"}), 503
    return jsonify({"ok": True})


@app.route("/api/favorites", methods=["DELETE"])
def api_favorites_remove():
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"error": "login required"}), 401

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "request body must be JSON"}), 400
    missing = missing_fields(payload, FAVORITE_REQUIRED_FIELDS)
    if missing:
        return jsonify({"error": f"missing required field(s): {', '.join(missing)}"}), 400

    try:
        remove_favorite(user_id, payload["player_id"], payload["pool"])
    except Exception as e:
        print(f"remove_favorite failed: {e}", file=sys.stderr)
        return jsonify({"error": "could not remove favorite, please try again later"}), 503
    return jsonify({"ok": True})
```

Add `list_favorites`, `add_favorite`, `remove_favorite` to the `from db import (...)` block.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add server/app.py server/test_app.py
git commit -m "api: add GET/POST/DELETE /api/favorites"
```

---

### Task 6: `GET /api/admin/feedback`

**Files:**
- Modify: `server/app.py`
- Test: `server/test_app.py`

**Interfaces:**
- Consumes: `list_feedback` from `server/db.py` (Task 1).
- Produces: `GET /api/admin/feedback` → 200 `{"feedback": [{"created_at", "rating", "message", "lang"}, ...]}` only when `session["email"] == ADMIN_EMAIL`; 404 otherwise (not logged in, logged in as someone else, or `ADMIN_EMAIL` unset).

- [ ] **Step 1: Write the failing tests**

Add to `server/test_app.py`:

```python
class AdminFeedbackTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        import db
        db._memory_feedback.clear()

    def _login(self, sub, email):
        fake_token = {"userinfo": {"sub": sub, "email": email, "name": "Test"}}
        from unittest.mock import patch
        import app as app_module
        with patch.object(app_module.oauth.google, "authorize_access_token", return_value=fake_token):
            self.client.get("/auth/callback")

    def test_404_when_not_logged_in(self):
        response = self.client.get("/api/admin/feedback")
        self.assertEqual(response.status_code, 404)

    def test_404_when_logged_in_as_a_non_admin(self):
        self._login("sub-admin-1", "regular-user@example.com")
        response = self.client.get("/api/admin/feedback")
        self.assertEqual(response.status_code, 404)

    def test_200_with_feedback_rows_when_logged_in_as_the_admin(self):
        import app as app_module
        app_module.ADMIN_EMAIL = "owner@example.com"
        try:
            self.client.post("/api/feedback", json={"rating": 5, "message": "讚", "lang": "zh"})
            self._login("sub-admin-2", "owner@example.com")
            response = self.client.get("/api/admin/feedback")
            self.assertEqual(response.status_code, 200)
            rows = response.get_json()["feedback"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["rating"], 5)
            self.assertEqual(rows[0]["message"], "讚")
            self.assertEqual(rows[0]["lang"], "zh")
        finally:
            app_module.ADMIN_EMAIL = None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app.AdminFeedbackTest -v`
Expected: 404s for the first two (those happen to already pass since the route is missing — that's a Flask 404, not this route's own 404 logic). The third test fails since the route doesn't exist.

(This is one case where "run it to see it fail" mostly tells you the third test fails — the first two tests pass by accident right now because of Flask's own 404 for an unknown route. Once the route exists in Step 3, re-run all three to confirm they pass for the *right* reason.)

- [ ] **Step 3: Implement the route**

Add to `server/app.py`, near the other module-level config (alongside `GOOGLE_LOGIN_CONFIGURED`):

```python
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
```

Add the route:

```python
@app.route("/api/admin/feedback", methods=["GET"])
def api_admin_feedback():
    if not ADMIN_EMAIL or session.get("email") != ADMIN_EMAIL:
        return jsonify({"error": "not found"}), 404
    return jsonify({"feedback": list_feedback()})
```

Add `list_feedback` to the `from db import (...)` block.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add server/app.py server/test_app.py
git commit -m "api: add GET /api/admin/feedback for the owner-only in-browser view"
```

---

### Task 7: Frontend — topnav login/logout

**Files:**
- Modify: `src/ui/index.html`

**Interfaces:**
- Consumes: `GET /api/me` (Task 2).
- Produces: `state.user = {email, name}` — later tasks (9, 10, 11) read this to gate favorite/admin/last-result UI. `async function loadAuthState()` — later tasks' `main()`/`setLang()` additions call this once; Task 9 also extends it.

- [ ] **Step 1: Add the `auth-nav` markup**

In `src/ui/index.html`, inside `<div class="topnav-actions">` (currently holding the visit counter, lang switch, and theme toggle — around where `<div class="lang-switch" id="lang-switch"></div>` is), add a new div right before it:

```html
      <div class="auth-nav" id="auth-nav"></div>
```

So the block reads:

```html
    <div class="topnav-actions">
      <span class="visit-counter" id="visit-counter" style="display:none"></span>
      <div class="auth-nav" id="auth-nav"></div>
      <div class="lang-switch" id="lang-switch"></div>
      <button type="button" class="theme-toggle" id="theme-toggle-btn" aria-label="切換成米白主題">☀</button>
    </div>
```

- [ ] **Step 2: Add CSS**

Add near the other `.topnav-*`/`.lang-switch` rules:

```css
  .auth-nav { display: flex; align-items: center; gap: 0.5rem; font-size: 0.78rem; }
  .auth-nav-name { color: var(--ink-soft); white-space: nowrap; max-width: 6rem; overflow: hidden; text-overflow: ellipsis; }
  .auth-nav a.auth-nav-login, .auth-nav button.auth-nav-logout {
    background: none; border: none; color: var(--accent-ink); cursor: pointer; font-size: 0.78rem;
    text-decoration: none; font-family: inherit; padding: 0;
  }
```

- [ ] **Step 3: Add `UI_STRINGS` keys**

In the `UI_STRINGS` object, add these two keys to each of the three language blocks (`zh`, `zh-Hans`, `en`):

```js
    loginLink: "登入",
    logoutLink: "登出",
```
```js
    loginLink: "登录",
    logoutLink: "登出",
```
```js
    loginLink: "Log in",
    logoutLink: "Log out",
```

- [ ] **Step 4: Add state, `loadAuthState()`, and `renderAuthNav()`**

In the `state` object literal, add:

```js
    user: { email: null, name: null },
```

After `renderLangSwitch()`'s definition, add two new functions:

```js
  async function loadAuthState() {
    try {
      const res = await fetch("/api/me");
      const data = await res.json();
      state.user = { email: data.email || null, name: data.name || null };
    } catch (err) {
      state.user = { email: null, name: null };
    }
  }

  function renderAuthNav() {
    const container = document.getElementById("auth-nav");
    container.innerHTML = "";
    if (state.user.email) {
      const name = document.createElement("span");
      name.className = "auth-nav-name";
      name.textContent = state.user.name || state.user.email;
      const logoutBtn = document.createElement("button");
      logoutBtn.type = "button";
      logoutBtn.className = "auth-nav-logout";
      logoutBtn.textContent = t().logoutLink;
      logoutBtn.addEventListener("click", () => {
        fetch("/auth/logout", { method: "POST" }).then(() => { window.location.href = "/"; });
      });
      container.append(name, logoutBtn);
    } else {
      const loginLink = document.createElement("a");
      loginLink.href = "/auth/login";
      loginLink.className = "auth-nav-login";
      loginLink.textContent = t().loginLink;
      container.appendChild(loginLink);
    }
  }
```

- [ ] **Step 5: Wire it into `main()` and `setLang()`**

In `main()`, right after the line `state.bodyQuestions = payload.questions.body_measurements;` and before `renderLangSwitch();`, add:

```js
    await loadAuthState();
```

Right after `renderLangSwitch();` in `main()`, add:

```js
    renderAuthNav();
```

In `setLang()`, right after the existing `renderLangSwitch();` call, add:

```js
    renderAuthNav();
```

(Login/logout labels are language-dependent, so the nav needs re-rendering on a language switch, same as the lang switch itself.)

- [ ] **Step 6: Manual check**

Run the server locally (`source .venv/bin/activate && python3 server/app.py`), open `http://localhost:5001`, and confirm:
- The topnav shows a "登入" link (since `GOOGLE_CLIENT_ID`/`SECRET` aren't set locally, clicking it will hit `/auth/login` and get a 503 JSON response — that's expected and correct per Task 2's graceful-degradation guard; full click-through verification happens in Task 12/after real credentials are configured).
- No console errors on page load.
- Switching language still shows the (translated) "登入"/"登录"/"Log in" label.

- [ ] **Step 7: Commit**

```bash
git add src/ui/index.html
git commit -m "ui: add topnav login/logout control"
```

---

### Task 8: Frontend — admin-only feedback page

**Files:**
- Modify: `src/ui/index.html`

**Interfaces:**
- Consumes: `GET /api/admin/feedback` (Task 6); `state.user`, `loadAuthState()` (Task 7).
- Produces: `state.isAdmin: bool`, `state.adminFeedback: array | null` — extends `loadAuthState()` from Task 7 (same function, new body) so no other task needs to call anything new.

- [ ] **Step 1: Add the page and nav tab markup**

In the `<div class="topnav-tabs">` block, add a new tab after the training tab:

```html
      <a href="#" class="topnav-tab" id="topnav-tab-admin" aria-disabled="true" style="display:none">意見回饋</a>
```

After the `<section class="app-page" id="page-training" hidden>` section's closing `</section>`, add a new page:

```html
  <section class="app-page" id="page-admin" hidden>
  <div class="page">
  <div id="admin-feedback-report"></div>
  </div>
  </section>
```

- [ ] **Step 2: Add CSS**

```css
  .admin-feedback-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .admin-feedback-row {
    border: 1px solid var(--line); border-radius: var(--radius); padding: 0.6rem 0.8rem; background: var(--paper-raised);
  }
  .admin-feedback-meta { display: flex; gap: 0.5rem; font-size: 0.72rem; color: var(--ink-soft); font-family: var(--mono); }
  .admin-feedback-message { margin: 0.3rem 0 0; }
```

- [ ] **Step 3: Add `UI_STRINGS` keys**

Add to all three language blocks:

```js
    navAdminFeedback: "意見回饋",
    adminFeedbackEmpty: "目前沒有任何意見。",
    adminFeedbackNoMessage: "(沒有留言)",
    adminFeedbackNoRating: "(沒有星等)",
```
```js
    navAdminFeedback: "意见反馈",
    adminFeedbackEmpty: "目前没有任何意见。",
    adminFeedbackNoMessage: "(没有留言)",
    adminFeedbackNoRating: "(没有星等)",
```
```js
    navAdminFeedback: "Feedback",
    adminFeedbackEmpty: "No feedback yet.",
    adminFeedbackNoMessage: "(no message)",
    adminFeedbackNoRating: "(no rating)",
```

- [ ] **Step 4: Extend `loadAuthState()` to probe admin status**

Replace Task 7's `loadAuthState()` body with:

```js
  async function loadAuthState() {
    try {
      const res = await fetch("/api/me");
      const data = await res.json();
      state.user = { email: data.email || null, name: data.name || null };
    } catch (err) {
      state.user = { email: null, name: null };
    }

    state.isAdmin = false;
    state.adminFeedback = null;
    if (state.user.email) {
      try {
        const res = await fetch("/api/admin/feedback");
        if (res.ok) {
          state.isAdmin = true;
          state.adminFeedback = (await res.json()).feedback;
        }
      } catch (err) {
        // 不是 admin,或探測失敗——兩種情況都當作不是 admin,不用另外處理
      }
    }
  }
```

- [ ] **Step 5: Render the admin tab and page**

Add a render function, right after `renderAuthNav()`:

```js
  function renderAdminFeedbackPage() {
    const el = document.getElementById("admin-feedback-report");
    const s = t();
    if (!state.adminFeedback || state.adminFeedback.length === 0) {
      el.innerHTML = `<p class="training-empty">${s.adminFeedbackEmpty}</p>`;
      return;
    }
    el.innerHTML = `<div class="admin-feedback-list">${state.adminFeedback.map((row) => `
      <div class="admin-feedback-row">
        <div class="admin-feedback-meta">
          <span>${row.created_at ? escapeHtml(String(row.created_at)) : ""}</span>
          <span>${row.lang ? escapeHtml(row.lang) : ""}</span>
          <span>${row.rating ? starMarkup(row.rating) : s.adminFeedbackNoRating}</span>
        </div>
        <p class="admin-feedback-message">${row.message ? escapeHtml(row.message) : s.adminFeedbackNoMessage}</p>
      </div>`).join("")}</div>`;
  }
```

In `main()`, right after the `renderAuthNav();` call added in Task 7, add:

```js
    document.getElementById("topnav-tab-admin").style.display = state.isAdmin ? "" : "none";
    document.getElementById("topnav-tab-admin").textContent = t().navAdminFeedback;
    document.getElementById("topnav-tab-admin").setAttribute("aria-disabled", String(!state.isAdmin));
    if (state.isAdmin) renderAdminFeedbackPage();
```

Add `"admin"` to both `PAGE_IDS` and `TAB_IDS`:

```js
  const PAGE_IDS = ["home", "quiz", "template", "training", "admin"];
  const TAB_IDS = ["home", "template", "training", "admin"];
```

(The generic `for (const name of TAB_IDS) { ... showPage(name) ... }` click-wiring near the bottom of the file already handles this new tab with no further changes — it respects `aria-disabled`, and `style.display = "none"` keeps it invisible to non-admins regardless.)

- [ ] **Step 6: Manual check**

Since there's no real admin session available without live Google credentials, verify via the server tests (Task 6, already passing) plus a quick visual check: load the page locally, confirm the "意見回饋" tab is absent (not just disabled — actually invisible) for a logged-out visitor, and that no console error appears.

- [ ] **Step 7: Commit**

```bash
git add src/ui/index.html
git commit -m "ui: add admin-only in-browser feedback page"
```

---

### Task 9: Frontend — ★ favorite button on the 10-player comparison cards

**Files:**
- Modify: `src/ui/index.html`

**Interfaces:**
- Consumes: `GET/POST/DELETE /api/favorites` (Task 5); `top_10[].id` (Task 3); `state.user` (Task 7).
- Produces: `state.favorites: array | null` (each `{player_id, pool, name, team}`), `function isFavorited(pool, id)`, `async function loadFavorites()`, `async function toggleFavorite(playerId, pool)` — Task 10 (favorites page) and Task 11 both read/reuse `state.favorites`.

- [ ] **Step 1: Add CSS**

```css
  .card-head-right { display: flex; align-items: center; gap: 0.5rem; flex: none; }
  .favorite-btn {
    background: none; border: none; cursor: pointer; font-size: 1rem; line-height: 1;
    padding: 0; color: var(--accent-ink);
  }
  .favorite-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .favorite-login-prompt { font-size: 0.68rem; color: var(--ink-soft); }
  .favorite-login-prompt a { color: var(--accent-ink); }
```

- [ ] **Step 2: Add `UI_STRINGS` keys**

```js
    favoriteAddLabel: "收藏這位球員",
    favoriteRemoveLabel: "取消收藏",
    favoriteLoginPrompt: "登入才能收藏",
```
```js
    favoriteAddLabel: "收藏这位球员",
    favoriteRemoveLabel: "取消收藏",
    favoriteLoginPrompt: "登录才能收藏",
```
```js
    favoriteAddLabel: "Favorite this player",
    favoriteRemoveLabel: "Remove favorite",
    favoriteLoginPrompt: "Log in to favorite",
```

- [ ] **Step 3: Add state and data-layer functions**

In the `state` object literal, add:

```js
    favorites: null,
```

After `loadAuthState()` (as extended by Task 8), add:

```js
  function isFavorited(pool, id) {
    return !!(state.favorites && state.favorites.some((f) => f.pool === pool && f.player_id === id));
  }

  async function loadFavorites() {
    try {
      const res = await fetch(`/api/favorites?lang=${state.lang}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      state.favorites = (await res.json()).favorites;
    } catch (err) {
      state.favorites = [];
    }
  }

  function updateFavoriteButton(playerId, isFav) {
    document.querySelectorAll(".match-list [data-favorite-id]").forEach((btn) => {
      if (btn.dataset.favoriteId !== playerId) return;
      btn.textContent = isFav ? "★" : "☆";
      btn.setAttribute("aria-pressed", String(isFav));
      btn.setAttribute("aria-label", isFav ? t().favoriteRemoveLabel : t().favoriteAddLabel);
    });
  }

  async function toggleFavorite(playerId, pool) {
    const wasFav = isFavorited(pool, playerId);
    try {
      const res = await fetch("/api/favorites", {
        method: wasFav ? "DELETE" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ player_id: playerId, pool }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (wasFav) {
        state.favorites = state.favorites.filter((f) => !(f.pool === pool && f.player_id === playerId));
      } else {
        const m = (state.results && state.results.top_10.find((row) => row.id === playerId)) || {};
        state.favorites.push({ player_id: playerId, pool, name: m.name || "", team: m.team || "" });
      }
      updateFavoriteButton(playerId, !wasFav);
    } catch (err) {
      // 失敗就不改狀態,星星維持原樣——這是次要功能,不值得加一個獨立的錯誤提示
    }
  }
```

Call `loadFavorites()` right after `loadAuthState()` inside `main()` and `setLang()`, guarded by login state:

In `main()`, right after `await loadAuthState();`, add:

```js
    if (state.user.email) { await loadFavorites(); } else { state.favorites = []; }
```

In `setLang()`, right after the `renderAuthNav();` line added in Task 7, add:

```js
    if (state.user.email) { await loadFavorites(); }
```

- [ ] **Step 4: Render the star button on each comparison card**

Add a render helper right before `renderMatchCardInner`:

```js
  function renderFavoriteControl(m) {
    if (!state.user.email) {
      return `<span class="favorite-login-prompt">${t().favoriteLoginPrompt} <a href="/auth/login">${t().loginLink}</a></span>`;
    }
    const isFav = isFavorited(state.pool, m.id);
    return `<button type="button" class="favorite-btn" data-favorite-id="${escapeHtml(m.id)}" aria-pressed="${isFav}" aria-label="${isFav ? t().favoriteRemoveLabel : t().favoriteAddLabel}">${isFav ? "★" : "☆"}</button>`;
  }
```

Change `renderMatchCardInner` to wrap `.stat-line` and the new control together:

```js
  function renderMatchCardInner(rank, m) {
    return `
      <div class="card-head">
        <div class="who">
          <span class="rank mono">#${rank}</span>
          <span class="name">${escapeHtml(m.name)}</span>
          <span class="team mono">${escapeHtml(m.team)}</span>
        </div>
        <div class="card-head-right">
          <div class="stat-line">
            <span class="stat-label">${t().similarityLabel}</span>
            <span class="stars">${starMarkup(m.fit_stars)}</span>
          </div>
          ${renderFavoriteControl(m)}
        </div>
      </div>
      <div class="traits">${m.notable_traits.map((tr) => `<span class="trait">${escapeHtml(tr)}</span>`).join("")}</div>
      <div class="callout">
        <span class="axis-tag">${t().dominantAxisGap(t().axisLabels[m.dominant_diff_axis])}</span>
        <span class="growth">${t().growthNotePrefix}${escapeHtml(m.growth_recommendation)}</span>
      </div>`;
  }
```

- [ ] **Step 5: Wire the click, ahead of the card's own select-to-view-training click**

In `handleReportClick`, add a new branch **before** the existing `const playerEl = e.target.closest("[data-player-index]");` check (the star button is nested inside a card that also carries `data-player-index`, so this branch must run first and `return`):

```js
    const favoriteBtn = e.target.closest("[data-favorite-id]");
    if (favoriteBtn) {
      toggleFavorite(favoriteBtn.dataset.favoriteId, state.pool);
      return;
    }
```

- [ ] **Step 6: Manual check**

Run the server locally, submit the quiz, confirm each of the 10 comparison cards shows "登入才能收藏 登入" (logged out). Confirm clicking elsewhere on the card still selects it for the training plan (the favorite-login-prompt text itself isn't clickable-to-select, which is fine — it's not inside the `[data-player-index]` click path's concern, it's just inert text next to a link).

- [ ] **Step 7: Commit**

```bash
git add src/ui/index.html
git commit -m "ui: add favorite star button to the 10-player comparison cards"
```

---

### Task 10: Frontend — "我的收藏" page

**Files:**
- Modify: `src/ui/index.html`

**Interfaces:**
- Consumes: `state.favorites`, `isFavorited`, `loadFavorites` (Task 9); `state.user` (Task 7).
- Produces: generalizes `fetchCustomPlayerTrainingPlan(id, pool)` and `selectCustomPlayer(id, pool = state.pool)` to take an explicit pool (previously both always read `state.pool` directly) — the search-box call sites are updated to pass `state.pool` explicitly, so their behavior is unchanged.

- [ ] **Step 1: Add the page and nav tab markup**

In `<div class="topnav-tabs">`, add (after the home tab, before `template`, to match the spec's intended tab ordering — but ordering is cosmetic; placing it anywhere in this list is fine as long as it's present):

```html
      <a href="#" class="topnav-tab" id="topnav-tab-favorites" aria-disabled="true">我的收藏</a>
```

After `page-training`'s `</section>` (and before the admin page added in Task 8, or after it — order doesn't matter), add:

```html
  <section class="app-page" id="page-favorites" hidden>
  <div class="page">
  <div id="favorites-report"></div>
  </div>
  </section>
```

Add `"favorites"` to `PAGE_IDS` and `TAB_IDS`:

```js
  const PAGE_IDS = ["home", "quiz", "template", "training", "favorites", "admin"];
  const TAB_IDS = ["home", "template", "training", "favorites", "admin"];
```

- [ ] **Step 2: Add CSS**

```css
  .favorites-list { display: flex; flex-direction: column; gap: 0.6rem; }
  .favorite-row {
    display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;
    background: var(--paper-raised); border: 1px solid var(--line); border-radius: var(--radius); padding: 0.7rem 0.9rem;
  }
  .favorite-row .name { font-weight: 700; }
  .favorite-row .team { font-family: var(--mono); font-size: 0.72rem; color: var(--ink-soft); }
  .favorite-row-actions { display: flex; gap: 0.4rem; margin-left: auto; }
```

- [ ] **Step 3: Add `UI_STRINGS` keys**

```js
    navFavorites: "我的收藏",
    favoritesEmpty: "還沒有收藏的球員。",
    favoriteGotoTraining: "查看訓練計劃",
    favoriteRemoveButton: "移除",
```
```js
    navFavorites: "我的收藏",
    favoritesEmpty: "还没有收藏的球员。",
    favoriteGotoTraining: "查看训练计划",
    favoriteRemoveButton: "移除",
```
```js
    navFavorites: "Favorites",
    favoritesEmpty: "No favorites yet.",
    favoriteGotoTraining: "View training plan",
    favoriteRemoveButton: "Remove",
```

- [ ] **Step 4: Generalize the custom-player pool handling**

Change `fetchCustomPlayerTrainingPlan`'s signature and cache key (it currently reads `state.pool` directly):

```js
  async function fetchCustomPlayerTrainingPlan(id, pool) {
    const key = `${pool}|${state.lang}|${state.selectedEnv}|${id}`;
    if (state.customPlanCache.has(key)) return state.customPlanCache.get(key);
    const res = await fetch("/api/player-training-plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        player_id: id,
        coordinates: state.results.coordinates,
        env: state.selectedEnv,
        pool: pool,
        lang: state.lang,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    state.customPlanCache.set(key, data);
    return data;
  }

  async function selectCustomPlayer(id, pool = state.pool) {
    state.customPlayerId = id;
    state.customPlayerPool = pool;
    document.getElementById("player-search-input").value = "";
    hidePlayerSearchResults();
    await renderTrainingSection();
  }
```

Add `state.customPlayerPool = null;` to the initial `state` object, next to `customPlayerId: null,`.

In `renderTrainingSection()`'s custom-player branch, change the call from `fetchCustomPlayerTrainingPlan(id)` to `fetchCustomPlayerTrainingPlan(id, state.customPlayerPool)`:

```js
    if (state.customPlayerId) {
      const id = state.customPlayerId;
      const pool = state.customPlayerPool;
      body.innerHTML = `<p class="training-empty">${s.trainingPlanLoading}</p>`;
      try {
        const custom = await fetchCustomPlayerTrainingPlan(id, pool);
        if (state.customPlayerId !== id) return;
        body.innerHTML = renderTrainingBody(custom, custom.training_plan);
      } catch (err) {
        if (state.customPlayerId !== id) return;
        body.innerHTML = `<p class="training-empty">${s.trainingPlanError}</p>`;
      }
      return;
    }
```

In `resetSession()`, next to `state.customPlayerId = null;`, add `state.customPlayerPool = null;`.

In `handleReportClick`'s existing `data-player-index` branch, next to `state.customPlayerId = null;`, add `state.customPlayerPool = null;` (selecting a comparison-table card always means "not a custom player," so its pool field should reset too, for consistency — it's not read in that branch, but leaving it stale would be a trap for later changes).

- [ ] **Step 5: Render the favorites page**

Add after `renderAdminFeedbackPage()`:

```js
  function renderFavoritesPage() {
    const el = document.getElementById("favorites-report");
    const s = t();
    if (!state.favorites || state.favorites.length === 0) {
      el.innerHTML = `<p class="training-empty">${s.favoritesEmpty}</p>`;
      return;
    }
    el.innerHTML = `<div class="favorites-list">${state.favorites.map((f) => `
      <div class="favorite-row" data-favorite-player-id="${escapeHtml(f.player_id)}" data-favorite-pool="${escapeHtml(f.pool)}">
        <span class="name">${escapeHtml(f.name)}</span>
        <span class="team mono">${escapeHtml(f.team)}</span>
        <div class="favorite-row-actions">
          <button type="button" class="favorite-goto-training">${s.favoriteGotoTraining}</button>
          <button type="button" class="favorite-remove">${s.favoriteRemoveButton}</button>
        </div>
      </div>`).join("")}</div>`;
  }

  function goToTrainingForFavorite(playerId, pool) {
    if (!state.results) {
      openQuiz(pool);
      return;
    }
    selectCustomPlayer(playerId, pool);
    showPage("training");
  }

  async function removeFavoriteFromPage(playerId, pool) {
    await toggleFavorite(playerId, pool);
    renderFavoritesPage();
  }
```

- [ ] **Step 6: Wire clicks and tab availability**

In `handleReportClick`, add two branches (anywhere before the final `data-player-index` fallback):

```js
    const gotoTrainingBtn = e.target.closest(".favorite-goto-training");
    if (gotoTrainingBtn) {
      const row = gotoTrainingBtn.closest("[data-favorite-player-id]");
      goToTrainingForFavorite(row.dataset.favoritePlayerId, row.dataset.favoritePool);
      return;
    }
    const removeFavoriteBtn = e.target.closest(".favorite-remove");
    if (removeFavoriteBtn) {
      const row = removeFavoriteBtn.closest("[data-favorite-player-id]");
      removeFavoriteFromPage(row.dataset.favoritePlayerId, row.dataset.favoritePool);
      return;
    }
```

In `updateTabAvailability()`, add a `favorites` entry to the `enabled` map:

```js
  function updateTabAvailability() {
    const enabled = {
      template: state.results !== null,
      training: state.results !== null,
      favorites: !!state.user.email,
    };
    for (const [name, on] of Object.entries(enabled)) {
      document.getElementById(`topnav-tab-${name}`).setAttribute("aria-disabled", String(!on));
    }
  }
```

In `main()`, right after the block added in Task 8 (`document.getElementById("topnav-tab-admin")...`), add:

```js
    document.getElementById("topnav-tab-favorites").textContent = t().navFavorites;
    updateTabAvailability();
    if (state.user.email) renderFavoritesPage();
```

(`updateTabAvailability()` is already called once earlier in `main()`, right after `showPage("home")` — this second call is needed because `state.user` wasn't known yet at that point. Leave the earlier call in place; this one simply re-applies it now that login state is known.)

- [ ] **Step 7: Manual check**

Load the page locally, confirm the "我的收藏" tab is visible but disabled (greyed out, per the existing `aria-disabled` CSS rule `.topnav-tab[aria-disabled="true"]`) while logged out.

- [ ] **Step 8: Commit**

```bash
git add src/ui/index.html
git commit -m "ui: add the favorites page, generalize custom-player pool handling"
```

---

### Task 11: Frontend — "查看我上次的結果" homepage button

**Files:**
- Modify: `src/ui/index.html`

**Interfaces:**
- Consumes: `GET /api/my-results/latest` (Task 4); `state.user`, `loadAuthState()` (Task 7); `renderTemplateReport`, `updateTabAvailability`, `showPage` (pre-existing).

- [ ] **Step 1: Add the markup**

In `#page-home`, between the closing `</div>` of `.rules-box` and the opening `<div class="mode-select" ...>`, add:

```html
  <div class="view-last-result-block" id="view-last-result-block" style="display:none">
    <button type="button" class="primary" id="view-last-result-btn"></button>
  </div>
```

- [ ] **Step 2: Add CSS**

```css
  .view-last-result-block { margin: 1rem 0; }
```

- [ ] **Step 3: Add `UI_STRINGS` key**

```js
    viewLastResultButton: "查看我上次的結果",
```
```js
    viewLastResultButton: "查看我上次的结果",
```
```js
    viewLastResultButton: "View my last result",
```

- [ ] **Step 4: Add state and the fetch**

In the `state` object literal, add:

```js
    lastResult: null,
```

Add a function after `loadFavorites()`:

```js
  async function loadLastResult() {
    if (!state.user.email) { state.lastResult = null; return; }
    try {
      const res = await fetch("/api/my-results/latest");
      if (res.status === 204) { state.lastResult = null; return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      state.lastResult = await res.json();
    } catch (err) {
      state.lastResult = null;
    }
  }
```

- [ ] **Step 5: Wire it into `main()` and render the button**

In `main()`, right after the `if (state.user.email) { await loadFavorites(); } else { state.favorites = []; }` line added in Task 9, add:

```js
    await loadLastResult();
    const viewLastResultBlock = document.getElementById("view-last-result-block");
    if (state.lastResult) {
      document.getElementById("view-last-result-btn").textContent = t().viewLastResultButton;
      viewLastResultBlock.style.display = "block";
    } else {
      viewLastResultBlock.style.display = "none";
    }
```

Add the click handler, in the same block of one-time listener wiring as the other `main()` listeners (near `document.getElementById("mode-current-btn").addEventListener(...)`):

```js
    document.getElementById("view-last-result-btn").addEventListener("click", () => {
      if (!state.lastResult) return;
      state.pool = state.lastResult.pool;
      state.selectedEnv = ENV_CODES[0];
      state.selectedPlayerIndex = 0;
      state.customPlayerId = null;
      state.customPlayerPool = null;
      renderTemplateReport(state.lastResult);
      updateTabAvailability();
      showPage("template");
    });
```

- [ ] **Step 6: Manual check**

Logged out, confirm the button never appears. (A logged-in check requires a real Google login, deferred to Task 12/post-credentials verification — note that `server/test_app.py`'s `LatestResultTest` already covers the underlying API's correctness.)

- [ ] **Step 7: Commit**

```bash
git add src/ui/index.html
git commit -m "ui: add the 'view my last result' homepage shortcut"
```

---

### Task 12: Full-suite regression run + manual browser verification

**Files:** none (verification only).

- [ ] **Step 1: Run every automated test suite**

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/engine
PYTHONPATH=.:src python3 -m unittest discover -s tests/scripts
(cd server && ../.venv/bin/python3 -m unittest test_app test_db)
```

Expected: all pass. (`tests/engine`/`tests/scripts` should be entirely unaffected by this plan — nothing here touches `/src/engine` — so this is primarily a regression check that nothing in `server/app.py`'s import changes broke anything these suites happen to exercise indirectly.)

- [ ] **Step 2: Headless-Chrome manual pass (logged-out regression)**

Using this project's existing headless-Chrome-via-CDP approach (`/Applications/Google Chrome.app --headless=new --remote-debugging-port=9333`, driven via the `websocket` Python library), load the site at phone width (~390px) logged out and confirm:
- All four pre-existing pages (首頁/問題/我的模板/訓練計劃) still work end-to-end: submit the quiz, view the template report, switch environments and players in the training section, use the custom-player search box.
- The topnav shows "登入", no "意見回饋" tab, and a disabled "我的收藏" tab.
- Each of the 10 comparison cards shows the "登入才能收藏" prompt instead of a star, and clicking elsewhere on the card still selects it for the training plan.
- No new console errors anywhere in this flow.

- [ ] **Step 3: Document the remaining manual step for the user**

Report to the user (not a code change): full verification of the logged-in flows — real Google login, favoriting/unfavoriting, the favorites page, "查看我上次的結果," and the admin feedback page — requires the Google Cloud OAuth client and the four Render environment variables (`SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ADMIN_EMAIL`) to be set up first (spec section 8). That setup is a manual step for the user; once it's done, the quickest check is: log in on the live/local site with the account meant to be the admin, confirm "意見回饋" appears, favorite a couple of players from both pools, confirm they show up correctly on "我的收藏", and confirm "查看我上次的結果" appears on a second visit after submitting the quiz once while logged in.

- [ ] **Step 4: Commit (only if Steps 1-2 required any fixes)**

If no fixes were needed, there's nothing to commit for this task — it's a verification pass, not a code change.
