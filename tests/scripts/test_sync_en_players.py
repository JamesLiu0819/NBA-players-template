# 用途：測試 scripts/sync_en_players.py 的 sync_players——把繁中球員的數值欄位複製到英文檔，
# 英文的文字欄位不動。
# 可手動調整的變數：無。

import unittest

from scripts.sync_en_players import sync_players


class SyncPlayersTest(unittest.TestCase):
    def test_copies_numbers_and_keeps_english_text(self):
        zh = [{"id": "a", "team": "LAL", "coordinates": {"A": 50}, "body": {"height_cm": 200}, "notable_traits": ["中文"], "archetype_id": "x"}]
        en = [{"id": "a", "team": "DAL", "coordinates": {"A": 10}, "body": {"height_cm": 190}, "notable_traits": ["English"]}]
        out = sync_players(zh, en)[0]
        self.assertEqual(out["team"], "LAL")
        self.assertEqual(out["coordinates"], {"A": 50})
        self.assertEqual(out["body"], {"height_cm": 200})
        self.assertEqual(out["archetype_id"], "x")
        self.assertEqual(out["notable_traits"], ["English"])

    def test_removes_an_archetype_override_dropped_in_zh(self):
        out = sync_players([{"id": "a"}], [{"id": "a", "archetype_id": "x"}])[0]
        self.assertNotIn("archetype_id", out)

    def test_mismatched_ids_raise(self):
        with self.assertRaises(ValueError):
            sync_players([{"id": "a"}], [{"id": "b"}])


if __name__ == "__main__":
    unittest.main()
