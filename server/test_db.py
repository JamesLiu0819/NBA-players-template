# 用途：測試 db.py 在沒有 DATABASE_URL 時的記憶體 fallback 遞增邏輯——這是
# 本機開發跟測試套件實際會跑到的路徑,不連真的 Postgres(見
# docs/superpowers/specs/2026-09-15-visit-counter-design.md)。Postgres 路徑
# 本身不寫自動化測試,跟專案既有慣例一致(測試不連外部服務)。
# 執行方式：cd server && ../.venv/bin/python3 -m unittest test_db -v

import importlib
import os
import unittest


class InMemoryVisitCounterTest(unittest.TestCase):
    def setUp(self):
        # 不管實際環境有沒有設定 DATABASE_URL,測試一律強制走記憶體路徑；
        # reload 讓每個測試方法從乾淨的計數器狀態開始。
        self._original_database_url = os.environ.pop("DATABASE_URL", None)
        import db
        importlib.reload(db)
        self.db = db

    def tearDown(self):
        if self._original_database_url is not None:
            os.environ["DATABASE_URL"] = self._original_database_url

    def test_first_increment_returns_one(self):
        self.assertEqual(self.db.increment_visit_count(), 1)

    def test_increments_accumulate_across_calls(self):
        self.db.increment_visit_count()
        self.db.increment_visit_count()
        self.assertEqual(self.db.increment_visit_count(), 3)

    def test_init_db_is_a_no_op_without_database_url(self):
        self.db.init_db()
        self.assertEqual(self.db.increment_visit_count(), 1)

    def test_init_db_does_not_raise_when_connection_fails(self):
        def broken_connection():
            raise ConnectionError("simulated failure")

        self.db._get_connection = broken_connection

        try:
            self.db.init_db()
        except Exception as e:
            self.fail(f"init_db() should not raise, but raised: {e}")


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


if __name__ == "__main__":
    unittest.main()
