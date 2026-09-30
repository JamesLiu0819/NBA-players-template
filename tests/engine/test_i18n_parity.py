# 用途：驗證 data/zh/ 跟 data/en/ 的五組資料檔結構完全一致(id 集合、所有
# 非文字欄位),文字欄位兩邊都存在、非空、且不能相等(避免漏翻)。這是多語言
# 子專案最重要的安全網——任何一邊漏改都會讓這支測試失敗,不用等到使用者
# 真的切換語言才發現某個地方沒翻(見 docs/superpowers/specs/
# 2026-09-16-english-i18n-design.md §4)。
# ZhHansParityTest 補 data/zh-Hans/ 跟 data/zh/ 的同一種結構比對——但 zh-Hans
# 是用 scripts/build_zh_hans_data.py 對 data/zh 做 OpenCC 繁簡轉換產生的建置
# 產物,不是獨立翻譯,所以不能比照 en 用「文字不能相等」當漏翻的判斷依據:
# 繁簡轉換本來就可能讓沒有繁簡異體字的字串轉換前後完全相同(例如整句都是
# 「一」「人」這種兩岸同形字),那不算漏轉換。這裡只驗證 id 集合、非文字欄位
# 跟文字欄位「存在且非空」,真正抓「忘記重跑轉換腳本」的方法是重新執行
# scripts/build_zh_hans_data.py,不是靠這支測試反推。
# 可手動調整的變數：無——這裡是通用比對邏輯,不含需要人工校準的參數。

import json
import unittest
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_json(lang, filename):
    with open(DATA_DIR / lang / filename, encoding="utf-8") as f:
        return json.load(f)


class QuestionsParityTest(unittest.TestCase):
    def setUp(self):
        self.zh = load_json("zh", "題庫.json")
        self.en = load_json("en", "questions.json")

    def _by_id(self, questions):
        return {q["id"]: q for q in questions}

    def test_axis_positioning_ids_match(self):
        zh_ids = {q["id"] for q in self.zh["axis_positioning"]}
        en_ids = {q["id"] for q in self.en["axis_positioning"]}
        self.assertEqual(zh_ids, en_ids)

    def test_skill_behavior_ids_match(self):
        zh_ids = {q["id"] for q in self.zh["skill_behavior"]}
        en_ids = {q["id"] for q in self.en["skill_behavior"]}
        self.assertEqual(zh_ids, en_ids)

    def test_body_measurements_ids_match(self):
        zh_ids = {q["id"] for q in self.zh["body_measurements"]}
        en_ids = {q["id"] for q in self.en["body_measurements"]}
        self.assertEqual(zh_ids, en_ids)

    def test_axis_positioning_non_text_fields_match(self):
        zh_by_id = self._by_id(self.zh["axis_positioning"])
        en_by_id = self._by_id(self.en["axis_positioning"])
        for qid, zh_q in zh_by_id.items():
            en_q = en_by_id[qid]
            self.assertEqual(zh_q["axis"], en_q["axis"], qid)
            self.assertEqual(
                zh_q.get("reverse_scored", False), en_q.get("reverse_scored", False), qid
            )

    def test_skill_behavior_non_text_fields_match(self):
        zh_by_id = self._by_id(self.zh["skill_behavior"])
        en_by_id = self._by_id(self.en["skill_behavior"])
        for qid, zh_q in zh_by_id.items():
            self.assertEqual(zh_q["skill_id"], en_by_id[qid]["skill_id"], qid)

    def test_body_measurements_non_text_fields_match(self):
        zh_by_id = self._by_id(self.zh["body_measurements"])
        en_by_id = self._by_id(self.en["body_measurements"])
        for qid, zh_q in zh_by_id.items():
            en_q = en_by_id[qid]
            self.assertEqual(zh_q["field"], en_q["field"], qid)
            self.assertEqual(zh_q["unit"], en_q["unit"], qid)
            self.assertEqual(zh_q["min"], en_q["min"], qid)
            self.assertEqual(zh_q["max"], en_q["max"], qid)
            self.assertEqual(zh_q.get("required", False), en_q.get("required", False), qid)

    def test_prompts_are_translated_not_copied(self):
        for section in ("axis_positioning", "skill_behavior", "body_measurements"):
            zh_by_id = self._by_id(self.zh[section])
            en_by_id = self._by_id(self.en[section])
            for qid, zh_q in zh_by_id.items():
                en_q = en_by_id[qid]
                self.assertTrue(en_q["prompt"].strip(), qid)
                self.assertNotEqual(zh_q["prompt"], en_q["prompt"], qid)

    def test_anchors_are_translated_not_copied(self):
        for section in ("axis_positioning", "skill_behavior"):
            zh_by_id = self._by_id(self.zh[section])
            en_by_id = self._by_id(self.en[section])
            for qid, zh_q in zh_by_id.items():
                en_q = en_by_id[qid]
                for score in ("1", "2", "3", "4", "5"):
                    self.assertTrue(en_q["anchors"][score].strip(), f"{qid}[{score}]")
                    self.assertNotEqual(
                        zh_q["anchors"][score], en_q["anchors"][score], f"{qid}[{score}]"
                    )


class SkillsParityTest(unittest.TestCase):
    def setUp(self):
        self.zh = load_json("zh", "技能.json")["skills"]
        self.en = load_json("en", "skills.json")["skills"]

    def _by_id(self, skills):
        return {s["id"]: s for s in skills}

    def test_ids_match(self):
        self.assertEqual(
            {s["id"] for s in self.zh}, {s["id"] for s in self.en}
        )

    def test_non_text_fields_match(self):
        zh_by_id, en_by_id = self._by_id(self.zh), self._by_id(self.en)
        for sid, zh_s in zh_by_id.items():
            en_s = en_by_id[sid]
            for field in ("category", "cost_C", "court_required", "teammate_required",
                          "axis_relevance", "video_tags"):
                self.assertEqual(zh_s[field], en_s[field], f"{sid}.{field}")
            for field in ("denominator", "direction", "thresholds"):
                self.assertEqual(
                    zh_s["metric"][field], en_s["metric"][field], f"{sid}.metric.{field}"
                )

    def test_text_fields_are_translated_not_copied(self):
        zh_by_id, en_by_id = self._by_id(self.zh), self._by_id(self.en)
        for sid, zh_s in zh_by_id.items():
            en_s = en_by_id[sid]
            self.assertTrue(en_s["name_zh"].strip(), sid)
            self.assertNotEqual(zh_s["name_zh"], en_s["name_zh"], sid)
            self.assertTrue(en_s["metric"]["action"].strip(), sid)
            self.assertNotEqual(zh_s["metric"]["action"], en_s["metric"]["action"], sid)


class ArchetypesParityTest(unittest.TestCase):
    def setUp(self):
        self.zh = load_json("zh", "原型.json")["archetypes"]
        self.en = load_json("en", "archetypes.json")["archetypes"]

    def _by_id(self, archetypes):
        return {a["id"]: a for a in archetypes}

    def test_ids_match(self):
        self.assertEqual(
            {a["id"] for a in self.zh}, {a["id"] for a in self.en}
        )

    def test_coordinates_match(self):
        zh_by_id, en_by_id = self._by_id(self.zh), self._by_id(self.en)
        for aid, zh_a in zh_by_id.items():
            self.assertEqual(zh_a["coordinates"], en_by_id[aid]["coordinates"], aid)

    def test_size_matches(self):
        zh_by_id, en_by_id = self._by_id(self.zh), self._by_id(self.en)
        for aid, zh_a in zh_by_id.items():
            self.assertEqual(zh_a["size"], en_by_id[aid]["size"], aid)

    def test_text_fields_are_translated_not_copied(self):
        zh_by_id, en_by_id = self._by_id(self.zh), self._by_id(self.en)
        for aid, zh_a in zh_by_id.items():
            en_a = en_by_id[aid]
            self.assertTrue(en_a["name_zh"].strip(), aid)
            self.assertNotEqual(zh_a["name_zh"], en_a["name_zh"], aid)
            self.assertTrue(en_a["flavor"].strip(), aid)
            self.assertNotEqual(zh_a["flavor"], en_a["flavor"], aid)


class PlayersParityTest(unittest.TestCase):
    NON_TEXT_FIELDS = (
        "id", "name", "team", "coordinates", "body", "signature_skill_id",
        "learnability_flag", "mock_axis_answers", "mock_skill_answers",
    )

    def setUp(self):
        self.zh = load_json("zh", "球員.json")["players"]
        self.en = load_json("en", "players.json")["players"]

    def _by_id(self, players):
        return {p["id"]: p for p in players}

    def test_ids_match(self):
        self.assertEqual(
            {p["id"] for p in self.zh}, {p["id"] for p in self.en}
        )

    def test_non_text_fields_match(self):
        zh_by_id, en_by_id = self._by_id(self.zh), self._by_id(self.en)
        for pid, zh_p in zh_by_id.items():
            en_p = en_by_id[pid]
            for field in self.NON_TEXT_FIELDS:
                self.assertEqual(zh_p[field], en_p[field], f"{pid}.{field}")

    def test_notable_traits_are_translated_not_copied(self):
        zh_by_id, en_by_id = self._by_id(self.zh), self._by_id(self.en)
        for pid, zh_p in zh_by_id.items():
            en_p = en_by_id[pid]
            self.assertEqual(len(zh_p["notable_traits"]), len(en_p["notable_traits"]), pid)
            for zh_trait, en_trait in zip(zh_p["notable_traits"], en_p["notable_traits"]):
                self.assertTrue(en_trait.strip(), pid)
                self.assertNotEqual(zh_trait, en_trait, pid)


class PlayersAlltimeParityTest(unittest.TestCase):
    NON_TEXT_FIELDS = PlayersParityTest.NON_TEXT_FIELDS

    def setUp(self):
        self.zh = load_json("zh", "歷史球員.json")["players"]
        self.en = load_json("en", "players_alltime.json")["players"]

    def _by_id(self, players):
        return {p["id"]: p for p in players}

    def test_ids_match(self):
        self.assertEqual(
            {p["id"] for p in self.zh}, {p["id"] for p in self.en}
        )

    def test_non_text_fields_match(self):
        zh_by_id, en_by_id = self._by_id(self.zh), self._by_id(self.en)
        for pid, zh_p in zh_by_id.items():
            en_p = en_by_id[pid]
            for field in self.NON_TEXT_FIELDS:
                self.assertEqual(zh_p[field], en_p[field], f"{pid}.{field}")

    def test_notable_traits_are_translated_not_copied(self):
        zh_by_id, en_by_id = self._by_id(self.zh), self._by_id(self.en)
        for pid, zh_p in zh_by_id.items():
            en_p = en_by_id[pid]
            self.assertEqual(len(zh_p["notable_traits"]), len(en_p["notable_traits"]), pid)
            for zh_trait, en_trait in zip(zh_p["notable_traits"], en_p["notable_traits"]):
                self.assertTrue(en_trait.strip(), pid)
                self.assertNotEqual(zh_trait, en_trait, pid)


class ZhHansStructureParityTest(unittest.TestCase):
    """Structural parity between data/zh and data/zh-Hans (script-converted,
    not independently translated -- see module docstring for why text
    equality isn't asserted here)."""

    def setUp(self):
        self.questions_zh = load_json("zh", "題庫.json")
        self.questions_zh_hans = load_json("zh-Hans", "题库.json")
        self.skills_zh = load_json("zh", "技能.json")["skills"]
        self.skills_zh_hans = load_json("zh-Hans", "技能.json")["skills"]
        self.archetypes_zh = load_json("zh", "原型.json")["archetypes"]
        self.archetypes_zh_hans = load_json("zh-Hans", "原型.json")["archetypes"]
        self.players_zh = load_json("zh", "球員.json")["players"]
        self.players_zh_hans = load_json("zh-Hans", "球员.json")["players"]
        self.players_alltime_zh = load_json("zh", "歷史球員.json")["players"]
        self.players_alltime_zh_hans = load_json("zh-Hans", "历史球员.json")["players"]

    def test_question_ids_match_across_all_sections(self):
        for section in ("axis_positioning", "skill_behavior", "body_measurements"):
            zh_ids = {q["id"] for q in self.questions_zh[section]}
            zh_hans_ids = {q["id"] for q in self.questions_zh_hans[section]}
            self.assertEqual(zh_ids, zh_hans_ids, section)

    def test_question_prompts_and_anchors_are_present(self):
        for section in ("axis_positioning", "skill_behavior"):
            for q in self.questions_zh_hans[section]:
                self.assertTrue(q["prompt"].strip(), q["id"])
                for score in ("1", "2", "3", "4", "5"):
                    self.assertTrue(q["anchors"][score].strip(), f"{q['id']}[{score}]")

    def test_skill_ids_and_non_text_fields_match(self):
        zh_by_id = {s["id"]: s for s in self.skills_zh}
        zh_hans_by_id = {s["id"]: s for s in self.skills_zh_hans}
        self.assertEqual(set(zh_by_id), set(zh_hans_by_id))
        for sid, zh_s in zh_by_id.items():
            zh_hans_s = zh_hans_by_id[sid]
            for field in ("category", "cost_C", "court_required", "teammate_required",
                          "axis_relevance", "video_tags"):
                self.assertEqual(zh_s[field], zh_hans_s[field], f"{sid}.{field}")
            self.assertTrue(zh_hans_s["name_zh"].strip(), sid)
            self.assertTrue(zh_hans_s["metric"]["action"].strip(), sid)

    def test_archetype_ids_and_coordinates_match(self):
        zh_by_id = {a["id"]: a for a in self.archetypes_zh}
        zh_hans_by_id = {a["id"]: a for a in self.archetypes_zh_hans}
        self.assertEqual(set(zh_by_id), set(zh_hans_by_id))
        for aid, zh_a in zh_by_id.items():
            zh_hans_a = zh_hans_by_id[aid]
            self.assertEqual(zh_a["coordinates"], zh_hans_a["coordinates"], aid)
            self.assertEqual(zh_a["size"], zh_hans_a["size"], aid)
            self.assertTrue(zh_hans_a["name_zh"].strip(), aid)
            self.assertTrue(zh_hans_a["flavor"].strip(), aid)

    def _assert_player_pool_parity(self, zh_players, zh_hans_players):
        zh_by_id = {p["id"]: p for p in zh_players}
        zh_hans_by_id = {p["id"]: p for p in zh_hans_players}
        self.assertEqual(set(zh_by_id), set(zh_hans_by_id))
        for pid, zh_p in zh_by_id.items():
            zh_hans_p = zh_hans_by_id[pid]
            for field in PlayersParityTest.NON_TEXT_FIELDS:
                self.assertEqual(zh_p[field], zh_hans_p[field], f"{pid}.{field}")
            self.assertEqual(len(zh_p["notable_traits"]), len(zh_hans_p["notable_traits"]), pid)
            for trait in zh_hans_p["notable_traits"]:
                self.assertTrue(trait.strip(), pid)

    def test_players_current_pool_parity(self):
        self._assert_player_pool_parity(self.players_zh, self.players_zh_hans)

    def test_players_alltime_pool_parity(self):
        self._assert_player_pool_parity(self.players_alltime_zh, self.players_alltime_zh_hans)


if __name__ == "__main__":
    unittest.main()
