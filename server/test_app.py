# 用途：測試 API endpoint。POST /api/template-results 只吃六軸定位(12題)跟身材數值
# (6題,其中身高、體重必填,其餘 4 題可省略),回傳定位/3位深度模板/10人對照表,
# 每位球員附三種聯賽環境的訓練計劃(training_plans)。已經沒有技能題跟
# /api/priority-results,那支路由的測試移除,改成確認它真的不存在。
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


ENV_CODES = ("collapsed_no_shooters", "tight_perimeter_opp_shooters", "zone_defense")


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

    def test_response_includes_an_archetype_mode(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)
        data = response.get_json()

        self.assertIn(data["archetype_mode"], ("relative_strength", "body_only"))

    def test_one_survey_produces_a_full_result_without_any_skill_questions(self):
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
                "training_plans",
            },
        )
        self.assertEqual(top_player["rank"], 1)
        self.assertEqual(set(top_player["coordinates"].keys()), {"A", "B1", "B2", "C1", "C2", "D"})

    def test_every_top_10_player_has_training_plans_for_all_three_environments(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)

        for row in response.get_json()["top_10"]:
            self.assertEqual(set(row["training_plans"].keys()), set(ENV_CODES))
            for plan in row["training_plans"].values():
                self.assertLessEqual(len(plan), 5)

    def test_training_plan_items_have_the_expected_shape(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)
        items = [
            item
            for row in response.get_json()["top_10"]
            for plan in row["training_plans"].values()
            for item in plan
        ]

        self.assertTrue(items, "expected at least one trainable skill across the top 10")
        for item in items:
            self.assertEqual(
                set(item.keys()),
                {"skill_id", "name_zh", "P", "level", "is_signature", "metric", "drills"},
            )
            self.assertIn(item["level"], {"entry", "advanced", "mastery"})
            self.assertIsInstance(item["is_signature"], bool)
            self.assertEqual(
                set(item["metric"].keys()), {"action", "denominator", "direction", "threshold"}
            )
            self.assertIsInstance(item["drills"], list)

    def test_every_top_10_training_plan_has_a_signature_item_first(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)
        data = response.get_json()

        for player in data["top_10"]:
            for env_code, plan in player["training_plans"].items():
                self.assertGreaterEqual(len(plan), 1, f"{player['name']} / {env_code} has an empty plan")
                self.assertTrue(plan[0]["is_signature"], f"{player['name']} / {env_code} doesn't lead with the signature skill")

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


class RemovedPriorityEndpointTest(unittest.TestCase):
    def test_priority_results_endpoint_no_longer_exists(self):
        rules = {rule.rule for rule in app.url_map.iter_rules()}

        self.assertNotIn("/api/priority-results", rules)


class FormDataAndStaticTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_form_data_exposes_axis_and_body_questions_only(self):
        response = self.client.get("/api/form-data")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(
            set(data["questions"].keys()),
            {"axis_positioning", "body_measurements"},
        )
        self.assertNotIn("skills", data)

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


class FeedbackTest(unittest.TestCase):
    def setUp(self):
        import db
        self.db = db
        self.db._memory_feedback.clear()
        self.client = app.test_client()

    def test_saves_rating_and_message(self):
        response = self.client.post("/api/feedback", json={"rating": 4, "message": "很準", "lang": "zh"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db._memory_feedback, [{"rating": 4, "message": "很準", "lang": "zh"}])

    def test_rating_only_is_accepted(self):
        response = self.client.post("/api/feedback", json={"rating": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db._memory_feedback[0]["rating"], 2)
        self.assertIsNone(self.db._memory_feedback[0]["message"])

    def test_message_only_is_accepted(self):
        response = self.client.post("/api/feedback", json={"message": "希望能多幾位球員"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.db._memory_feedback[0]["rating"])

    def test_contact_is_not_collected(self):
        self.client.post("/api/feedback", json={"rating": 5, "contact": "a@example.com"})
        self.assertNotIn("contact", self.db._memory_feedback[0])

    def test_accepts_a_message_of_exactly_fifty_characters(self):
        response = self.client.post("/api/feedback", json={"message": "字" * 50})
        self.assertEqual(response.status_code, 200)

    def test_rejects_out_of_range_or_non_integer_rating(self):
        for bad in (0, 6, 3.5, "4", True):
            response = self.client.post("/api/feedback", json={"rating": bad, "message": "x"})
            self.assertEqual(response.status_code, 400, bad)
        self.assertEqual(self.db._memory_feedback, [])

    def test_rejects_empty_submission(self):
        response = self.client.post("/api/feedback", json={"message": "   "})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db._memory_feedback, [])

    def test_rejects_message_longer_than_fifty_characters(self):
        self.assertEqual(self.client.post("/api/feedback", json={"message": "字" * 51}).status_code, 400)
        self.assertEqual(self.db._memory_feedback, [])

    def test_rejects_unknown_language(self):
        response = self.client.post("/api/feedback", json={"rating": 3, "lang": "fr"})
        self.assertEqual(response.status_code, 400)

    def test_honeypot_pretends_success_but_stores_nothing(self):
        response = self.client.post("/api/feedback", json={"rating": 5, "website": "http://spam"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db._memory_feedback, [])

    def test_rejects_non_json_body(self):
        response = self.client.post("/api/feedback", data="not json", content_type="text/plain")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
