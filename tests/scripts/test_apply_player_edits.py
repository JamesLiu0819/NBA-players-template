# 用途：測試 scripts/apply_player_edits.py 的純函數：改寫種子腳本的球員項目（刪除、改座標、
# 改身材、指定原型）、略過沒有變動的修改、移動代表球員、記錄手動修正。
# 可手動調整的變數：無——下面的種子腳本片段和修改都是測試資料。

import unittest

from scripts.apply_player_edits import (
    delete_entry,
    meaningful_changes,
    set_archetype,
    set_body,
    set_coordinate,
    update_exemplars,
    update_overrides,
)

SEED = '''PLAYERS = [
    {
        "id": "a", "name": "A", "team": "HOU",
        "coordinates": {"A": 84, "B1": 13, "B2": 71, "C1": 81, "C2": 63, "D": 95},
        "body": {"height_cm": 201, "wingspan_cm": 213},
        "notable_traits": ["x"],
        "signature_skill_id": "s",
        "learnability_flag": "low",
    },
    {
        "id": "b", "name": "B", "team": "BOS",
        "coordinates": {"A": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5, "D": 6},
        "body": {"height_cm": 190, "wingspan_cm": 200},
        "signature_skill_id": "t",
    },
]
'''


class SeedEditTest(unittest.TestCase):
    def test_delete_entry_removes_only_that_player(self):
        out = delete_entry(SEED, "a")
        self.assertNotIn('"id": "a"', out)
        self.assertIn('"id": "b"', out)
        self.assertTrue(out.startswith("PLAYERS = [\n    {\n        \"id\": \"b\""))

    def test_set_coordinate(self):
        out = set_coordinate(SEED, "b", "B2", 87.5)
        self.assertIn('"coordinates": {"A": 1, "B1": 2, "B2": 87.5, "C1": 4, "C2": 5, "D": 6}', out)
        self.assertIn('"coordinates": {"A": 84, "B1": 13, "B2": 71', out)

    def test_set_body_adds_or_replaces_a_field(self):
        out = set_body(SEED, "a", "sprint_100m_seconds", 13.5)
        self.assertIn('"body": {"height_cm": 201, "wingspan_cm": 213, "sprint_100m_seconds": 13.5}', out)
        out = set_body(out, "a", "height_cm", 204)
        self.assertIn('"height_cm": 204', out)

    def test_set_archetype_adds_replaces_and_removes(self):
        out = set_archetype(SEED, "a", "rim_protector")
        self.assertIn('"signature_skill_id": "s",\n        "archetype_id": "rim_protector",\n', out)
        out = set_archetype(out, "a", "floor_general")
        self.assertEqual(out.count('"archetype_id"'), 1)
        self.assertIn('"archetype_id": "floor_general"', out)
        self.assertNotIn('"archetype_id"', set_archetype(out, "a", None))

    def test_unknown_player_raises(self):
        with self.assertRaises(KeyError):
            delete_entry(SEED, "zzz")


class GroupingTest(unittest.TestCase):
    def test_skips_no_ops_and_edits_to_deleted_players(self):
        changes = [
            {"pool": "current", "id": "a", "field": "coordinates.A", "old": 87.5, "new": 87.5},
            {"pool": "current", "id": "a", "field": "coordinates.B1", "old": 25, "new": 37.5},
            {"pool": "current", "id": "b", "field": "coordinates.A", "old": 10, "new": 20},
            {"pool": "current", "id": "b", "field": "deleted", "old": False, "new": True},
        ]
        kept = meaningful_changes(changes)
        self.assertEqual([(c["id"], c["field"]) for c in kept], [("a", "coordinates.B1"), ("b", "deleted")])

    def test_update_exemplars_moves_adds_and_drops_deleted(self):
        archetypes = [{"id": "x", "exemplars": ["p1", "p2", "gone"]}, {"id": "y", "exemplars": ["p3"]}]
        changes = [{"id": "p2", "field": "exemplar_of", "new": "y"}, {"id": "p4", "field": "exemplar_of", "new": "x"},
                   {"id": "p3", "field": "exemplar_of", "new": None}]
        out = {a["id"]: a["exemplars"] for a in update_exemplars(archetypes, changes, {"gone"})}
        self.assertEqual(out, {"x": ["p1", "p4"], "y": ["p2"]})

    def test_archetype_left_without_representatives_is_an_error(self):
        with self.assertRaises(ValueError):
            update_exemplars([{"id": "x", "exemplars": ["p1"]}], [{"id": "p1", "field": "exemplar_of", "new": None}], set())

    def test_update_overrides_records_numbers_and_forgets_deleted(self):
        existing = {"current": {"old": {"coordinates": {"A": 50}}, "b": {"coordinates": {"A": 1}}}}
        changes = [{"pool": "current", "id": "a", "field": "coordinates.B2", "new": 75},
                   {"pool": "current", "id": "a", "field": "body.sprint_100m_seconds", "new": 13.5}]
        out = update_overrides(existing, changes, {("current", "b")})
        self.assertEqual(out["current"]["a"], {"coordinates": {"B2": 75}, "body": {"sprint_100m_seconds": 13.5}})
        self.assertIn("old", out["current"])
        self.assertNotIn("b", out["current"])


if __name__ == "__main__":
    unittest.main()
