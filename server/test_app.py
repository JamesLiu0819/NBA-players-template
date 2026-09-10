# 用途：測試兩支 API endpoint。POST /api/template-results 只吃四軸定位(16題)
# 跟身材數值(6題,可省略),回傳定位/3位深度模板/10人對照表——刻意不需要技能
# 行為跟環境權重,因為很多使用者沒在打正式比賽,只想知道自己的球員模板是誰。
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


def build_skill_answers(questions):
    return [{"question_id": q["id"], "score": 3} for q in questions["skill_behavior"]]


def build_env(skills):
    return {s["id"]: 1.0 for s in skills}


class TemplateResultsTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.questions = load_json(ROOT / "data" / "questions.json")

    def test_full_payload_returns_200_with_expected_shape(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(set(data["coordinates"].keys()), {"A", "B", "C", "D"})
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
        payload = {"axis_answers": build_axis_answers(self.questions)}

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 200)

    def test_missing_body_answers_still_returns_200_with_null_body_fit(self):
        payload = {"axis_answers": build_axis_answers(self.questions)}

        response = self.client.post("/api/template-results", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["deep_templates"]["body_fit"])

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
        payload = {"axis_answers": build_axis_answers(self.questions)}

        response = self.client.post("/api/template-results", json=payload)
        top_player = response.get_json()["top_10"][0]

        self.assertEqual(
            set(top_player.keys()),
            {
                "rank", "name", "team", "distance", "fit_stars",
                "notable_traits", "dominant_diff_axis", "growth_recommendation",
            },
        )
        self.assertEqual(top_player["rank"], 1)


class PriorityResultsTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.questions = load_json(ROOT / "data" / "questions.json")
        self.skills = load_json(ROOT / "data" / "skills.json")["skills"]

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
        self.assertEqual(set(data["coordinates"].keys()), {"A", "B", "C", "D"})
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


if __name__ == "__main__":
    unittest.main()
