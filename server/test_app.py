# 用途：測試兩支 API endpoint。POST /api/template-results 只吃四軸定位(16題)
# 跟身材數值(6題,其中身高、體重必填,其餘 4 題可省略),回傳定位/3位深度模板/
# 10人對照表——刻意不需要技能行為跟環境權重,因為很多使用者沒在打正式比賽,
# 只想知道自己的球員模板是誰。
# POST /api/priority-results 才吃技能行為(15題)跟環境權重,回傳優先訓練順序,
# 是使用者自己選擇要不要看的「進階」分析。
# 用 Flask 內建的 test_client,不需要真的啟動伺服器。
# 執行方式(跟主要的 engine 測試套件分開跑,因為需要 Flask,不是純標準函式庫)：
#   cd server && ../.venv/bin/python3 -m unittest test_app -v
# 可手動調整的變數：無——這支檔案裡的作答資料是為了驗證 API 契約而設計的
# 測試案例,不是要調的參數。

import json
import unittest
from pathlib import Path

from app import app

ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_axis_answers(questions):
    return [{"question_id": q["id"], "score": 3} for q in questions["axis_positioning"]]


def build_body_answers(questions):
    return [
        {"question_id": q["id"], "value": (q["min"] + q["max"]) / 2}
        for q in questions["body_measurements"]
    ]


def build_required_body_answers(questions):
    # height_cm/weight_kg are required (2026-10); most tests below aren't
    # about body measurements at all, so they only need the minimum payload
    # that clears validation, not the full 6-question set.
    return [
        {"question_id": q["id"], "value": (q["min"] + q["max"]) / 2}
        for q in questions["body_measurements"]
        if q.get("required", False)
    ]


def build_skill_answers(questions):
    return [{"question_id": q["id"], "score": 3} for q in questions["skill_behavior"]]


def build_env(skills):
    return {s["id"]: 1.0 for s in skills}


class TemplateResultsTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.questions = load_json(ROOT / "data" / "zh" / "題庫.json")

    def test_full_payload_returns_200_with_expected_shape(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(set(data["coordinates"].keys()), {"A", "B1", "B2", "C1", "C2", "D"})
        self.assertEqual(
            set(data["deep_templates"].keys()), {"skill_fit", "body_fit", "ceiling"}
        )
        self.assertEqual(len(data["top_10"]), 10)
        # this endpoint must NOT require or return priority-analysis fields
        self.assertNotIn("priorities", data)
        self.assertNotIn("dominant_factor_sentence", data)

    def test_works_without_skill_answers_or_env_in_the_request(self):
        # the whole point of this endpoint: no BARS skill self-assessment,
        # no league environment, and it still produces a full result.
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 200)

    def test_missing_required_body_answers_returns_400(self):
        # height_cm/weight_kg are required (2026-10) -- they feed the
        # archetype classifier's body-size term, so a template result can't
        # be computed without them.
        payload = {"axis_answers": build_axis_answers(self.questions)}

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 400)
        error = response.get_json()["error"]
        self.assertIn("body_height", error)
        self.assertIn("body_weight", error)

    def test_optional_body_fields_can_be_skipped_once_required_ones_are_present(self):
        # wingspan/reach/sprint stay optional -- only height/weight are
        # mandatory, and supplying just those two is already enough to
        # populate body_fit (it's no longer possible to get a null
        # body_fit through the API now that height/weight can't be omitted).
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get_json()["deep_templates"]["body_fit"])

    def test_missing_axis_answers_returns_400(self):
        response = self.client.post("/api/template-results", json={})

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_incomplete_axis_answers_returns_400_not_500(self):
        payload = {"axis_answers": build_axis_answers(self.questions)[:1]}

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_non_json_body_returns_400(self):
        response = self.client.post("/api/template-results", data="not json", content_type="text/plain")

        self.assertEqual(response.status_code, 400)

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
                "rank", "name", "team", "coordinates", "distance", "fit_stars",
                "notable_traits", "dominant_diff_axis", "growth_recommendation",
            },
        )
        self.assertEqual(top_player["rank"], 1)
        self.assertEqual(set(top_player["coordinates"].keys()), {"A", "B1", "B2", "C1", "C2", "D"})

    def test_response_includes_archetype_and_scouting_report(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)
        data = response.get_json()

        self.assertEqual(set(data["archetype"].keys()), {"name_zh", "flavor"})
        self.assertIsInstance(data["scouting_report"], str)
        self.assertEqual(data["scouting_report"], data["archetype"]["flavor"])

    def test_missing_pool_defaults_to_current_players(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 200)
        current_names = {p["name"] for p in load_json(ROOT / "data" / "zh" / "球員.json")["players"]}
        top_10_names = {row["name"] for row in response.get_json()["top_10"]}
        self.assertTrue(top_10_names.issubset(current_names))

    def test_pool_alltime_uses_historical_players(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
            "pool": "alltime",
        }

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 200)
        alltime_names = {p["name"] for p in load_json(ROOT / "data" / "zh" / "歷史球員.json")["players"]}
        top_10_names = {row["name"] for row in response.get_json()["top_10"]}
        self.assertTrue(top_10_names.issubset(alltime_names))

    def test_invalid_pool_returns_400(self):
        payload = {"axis_answers": build_axis_answers(self.questions), "pool": "does_not_exist"}

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_lang_en_returns_english_content(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
            "lang": "en",
        }

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        en_names = {p["name"] for p in load_json(ROOT / "data" / "en" / "players.json")["players"]}
        top_10_names = {row["name"] for row in data["top_10"]}
        self.assertTrue(top_10_names.issubset(en_names))
        # scouting_report 是原型 flavor 文案,英文版跟中文版內容一定不同
        zh_response = self.client.post(
            "/api/template-results",
            json={
                "axis_answers": build_axis_answers(self.questions),
                "body_answers": build_required_body_answers(self.questions),
            },
        )
        self.assertNotEqual(data["scouting_report"], zh_response.get_json()["scouting_report"])

    def test_lang_zh_hans_returns_simplified_content(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
            "lang": "zh-Hans",
        }

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        zh_hans_names = {p["name"] for p in load_json(ROOT / "data" / "zh-Hans" / "球员.json")["players"]}
        top_10_names = {row["name"] for row in data["top_10"]}
        self.assertTrue(top_10_names.issubset(zh_hans_names))

    def test_invalid_lang_returns_400(self):
        payload = {"axis_answers": build_axis_answers(self.questions), "lang": "fr"}

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_missing_lang_defaults_to_zh(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 200)
        zh_names = {p["name"] for p in load_json(ROOT / "data" / "zh" / "球員.json")["players"]}
        top_10_names = {row["name"] for row in response.get_json()["top_10"]}
        self.assertTrue(top_10_names.issubset(zh_names))


class PriorityResultsTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.questions = load_json(ROOT / "data" / "zh" / "題庫.json")
        self.skills = load_json(ROOT / "data" / "zh" / "技能.json")["skills"]

    def build_full_payload(self):
        return {
            "axis_answers": build_axis_answers(self.questions),
            "skill_answers": build_skill_answers(self.questions),
            "env": build_env(self.skills),
        }

    def test_full_payload_returns_200_with_expected_shape(self):
        response = self.client.post("/api/priority-results", json=self.build_full_payload())

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(set(data["coordinates"].keys()), {"A", "B1", "B2", "C1", "C2", "D"})
        self.assertEqual(len(data["priorities"]), 15)
        self.assertIn("dominant_factor_sentence", data)
        # this endpoint is priority-only -- template/matching fields don't belong here
        self.assertNotIn("top_10", data)
        self.assertNotIn("deep_templates", data)

    def test_missing_skill_answers_returns_400(self):
        payload = self.build_full_payload()
        del payload["skill_answers"]

        response = self.client.post("/api/priority-results", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_missing_env_returns_400(self):
        payload = self.build_full_payload()
        del payload["env"]

        response = self.client.post("/api/priority-results", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_incomplete_env_returns_400_not_a_dropped_connection(self):
        # env present but missing one skill's weight used to raise SystemExit
        # in build_priority_items(), which isn't caught by the route's
        # except (ValueError, KeyError) -- the Flask dev server just dropped
        # the connection instead of returning a clean 400 (final-review
        # Finding 3). Regression test for the ValueError fix.
        payload = self.build_full_payload()
        del payload["env"][self.skills[0]["id"]]

        response = self.client.post("/api/priority-results", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_non_json_body_returns_400(self):
        response = self.client.post("/api/priority-results", data="not json", content_type="text/plain")

        self.assertEqual(response.status_code, 400)


class FormDataAndStaticTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_form_data_exposes_questions_and_slim_skills_only(self):
        response = self.client.get("/api/form-data")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(
            set(data["questions"].keys()),
            {"axis_positioning", "skill_behavior", "body_measurements"},
        )
        self.assertEqual(len(data["skills"]), 15)
        # only id/name_zh -- not axis_relevance, cost_C, metric, etc.
        self.assertEqual(set(data["skills"][0].keys()), {"id", "name_zh"})

    def test_serves_index_html_at_root(self):
        response = self.client.get("/")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"<html", response.data.lower())
        finally:
            response.close()


class SiteVisitTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_returns_200_with_visit_count_field(self):
        response = self.client.post("/api/site-visit")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data["visit_count"], int)

    def test_visit_count_increments_across_calls(self):
        first = self.client.post("/api/site-visit").get_json()["visit_count"]
        second = self.client.post("/api/site-visit").get_json()["visit_count"]

        self.assertEqual(second, first + 1)


if __name__ == "__main__":
    unittest.main()
