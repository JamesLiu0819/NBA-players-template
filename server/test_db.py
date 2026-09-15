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


if __name__ == "__main__":
    unittest.main()
