# 用途：測試 scripts/build_player_editor.py 的兩個純函數——把球員資料整理成編輯頁要的
# 格式(build_payload)、把資料塞進頁面的資料區塊(embed)。讀寫真實檔案的 main() 不在這裡測。
# 可手動調整的變數：無——下面的球員跟原型都是為了驗證規則設計的測試資料。

import json
import re
import unittest

from scripts.build_player_editor import build_payload, embed

ARCHETYPES = [
    {"id": "small", "name_zh": "小", "coordinates": {a: 80 for a in ("A", "B1", "B2", "C1", "C2", "D")}, "size": 10, "flavor": "f1"},
    {"id": "big", "name_zh": "大", "coordinates": {a: 20 for a in ("A", "B1", "B2", "C1", "C2", "D")}, "size": 90, "flavor": "f2"},
]


def player(pid, value, height, weight):
    return {
        "id": pid, "name": pid.title(), "team": "X",
        "coordinates": {a: value for a in ("A", "B1", "B2", "C1", "C2", "D")},
        "body": {"height_cm": height, "weight_kg": weight},
        "notable_traits": ["t"], "signature_skill_id": "s1",
    }


class BuildPayloadTest(unittest.TestCase):
    def test_tags_pools_and_attaches_engine_archetype_and_skill_name(self):
        pools = [("c", [player("guard", 80, 180, 75), player("center", 20, 215, 120)]),
                 ("h", [player("legend", 80, 190, 85)])]
        payload = build_payload(pools, ARCHETYPES, {"s1": "外線投射"}, "2026-10-23")
        by_id = {p["id"]: p for p in payload["players"]}
        self.assertEqual(by_id["guard"]["pool"], "c")
        self.assertEqual(by_id["legend"]["pool"], "h")
        self.assertEqual(by_id["guard"]["engine_archetype"], "small")
        self.assertEqual(by_id["center"]["engine_archetype"], "big")
        self.assertEqual(by_id["guard"]["signature_skill"], "外線投射")
        self.assertEqual(payload["snapshot"], "2026-10-23")
        self.assertEqual([a["id"] for a in payload["archetypes"]], ["small", "big"])


class ArchetypeOverridePayloadTest(unittest.TestCase):
    def test_hand_picked_archetype_is_carried_and_used_as_engine_archetype(self):
        guard = player("guard", 80, 180, 75)
        guard["archetype_id"] = "big"
        payload = build_payload([("c", [guard, player("center", 20, 215, 120)])], ARCHETYPES, {}, "d")
        by_id = {p["id"]: p for p in payload["players"]}
        self.assertEqual(by_id["guard"]["archetype_id"], "big")
        self.assertEqual(by_id["guard"]["engine_archetype"], "big")
        self.assertIsNone(by_id["center"]["archetype_id"])
        self.assertEqual(by_id["center"]["engine_archetype"], "big")


class EmbedTest(unittest.TestCase):
    PAGE = '<html><!--DATA-START--><script id="data" type="application/json">null</script><!--DATA-END--><p>keep</p></html>'

    def test_replaces_only_the_data_block(self):
        out = embed(self.PAGE, {"a": 1})
        self.assertIn('{"a":1}', out)
        self.assertIn("<p>keep</p>", out)
        self.assertNotIn(">null<", out)

    def test_running_twice_keeps_a_single_block(self):
        out = embed(embed(self.PAGE, {"a": 1}), {"a": 2})
        self.assertEqual(out.count("<!--DATA-START-->"), 1)
        self.assertIn('{"a":2}', out)

    def test_closing_script_text_in_data_cannot_break_out(self):
        out = embed(self.PAGE, {"name": "</script><b>x"})
        inner = re.search(r'type="application/json">(.*?)</script>', out).group(1)
        self.assertEqual(json.loads(inner)["name"], "</script><b>x")

    def test_missing_markers_is_an_error(self):
        with self.assertRaises(ValueError):
            embed("<html></html>", {})


if __name__ == "__main__":
    unittest.main()
