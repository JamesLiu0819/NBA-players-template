# 用途：驗證 data/players.json 的資料完整性(欄位齊全、座標範圍、id 唯一、
# signature_skill_id 對應到真的存在的技能)。這份資料是 scripts/build_players_seed.py
# 的產出,不是這支測試檔要驗證的邏輯本身。
# 可手動調整的變數：MIN_PLAYERS(至少要有幾位球員才能湊出 10 人對照表)。

import json
import unittest
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
AXES = ("A", "B", "C", "D")
VALID_LEARNABILITY_FLAGS = {"low", "medium", "high"}
MIN_PLAYERS = 10


def load_json(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class PlayersDataTest(unittest.TestCase):
    def setUp(self):
        self.players = load_json("players.json")["players"]
        self.skill_ids = {s["id"] for s in load_json("skills.json")["skills"]}

    def test_has_at_least_min_players(self):
        self.assertGreaterEqual(len(self.players), MIN_PLAYERS)

    def test_ids_are_unique(self):
        ids = [p["id"] for p in self.players]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_player_has_required_fields(self):
        required = {
            "id", "name", "team", "coordinates", "body",
            "notable_traits", "signature_skill_id", "learnability_flag",
            "_estimate_basis",
        }
        for player in self.players:
            self.assertTrue(required.issubset(player.keys()), player.get("id"))

    def test_coordinates_are_within_zero_to_hundred(self):
        for player in self.players:
            for axis in AXES:
                value = player["coordinates"][axis]
                self.assertGreaterEqual(value, 0, player["id"])
                self.assertLessEqual(value, 100, player["id"])

    def test_notable_traits_are_two_to_four_concrete_items(self):
        for player in self.players:
            traits = player["notable_traits"]
            self.assertGreaterEqual(len(traits), 2, player["id"])
            self.assertLessEqual(len(traits), 4, player["id"])

    def test_learnability_flag_is_valid(self):
        for player in self.players:
            self.assertIn(player["learnability_flag"], VALID_LEARNABILITY_FLAGS, player["id"])

    def test_signature_skill_id_if_present_exists_in_skills_json(self):
        for player in self.players:
            skill_id = player["signature_skill_id"]
            if skill_id is not None:
                self.assertIn(skill_id, self.skill_ids, player["id"])


if __name__ == "__main__":
    unittest.main()
