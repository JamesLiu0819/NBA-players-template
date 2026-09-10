# 用途：測試 POST /api/results 這支唯一的 API endpoint,包含成功情境(完整作答
# 回傳完整結果 JSON)跟失敗情境(缺欄位、資料不合法時回傳 400 而不是 500)。
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


def build_full_payload():
    questions = load_json(ROOT / "data" / "questions.json")
    skills = load_json(ROOT / "data" / "skills.json")["skills"]
    return {
        "axis_answers": [{"question_id": q["id"], "score": 3} for q in questions["axis_positioning"]],
        "skill_answers": [{"question_id": q["id"], "score": 3} for q in questions["skill_behavior"]],
        "body_answers": [
            {"question_id": q["id"], "value": (q["min"] + q["max"]) / 2}
            for q in questions["body_measurements"]
        ],
        "env": {s["id"]: 1.0 for s in skills},
    }


class ApiResultsTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_full_valid_payload_returns_200_with_expected_shape(self):
        response = self.client.post("/api/results", json=build_full_payload())

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(set(data["coordinates"].keys()), {"A", "B", "C", "D"})
        self.assertEqual(len(data["priorities"]), 15)
        self.assertIn("dominant_factor_sentence", data)
        self.assertEqual(set(data["deep_templates"].keys()), {"skill_fit", "body_fit", "ceiling"})
        self.assertEqual(len(data["top_10"]), 10)
        self.assertIn("anti_template", data)

    def test_missing_body_answers_still_returns_200_with_null_body_fit(self):
        payload = build_full_payload()
        del payload["body_answers"]

        response = self.client.post("/api/results", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["deep_templates"]["body_fit"])

    def test_missing_required_field_returns_400(self):
        payload = build_full_payload()
        del payload["axis_answers"]

        response = self.client.post("/api/results", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_non_json_body_returns_400(self):
        response = self.client.post("/api/results", data="not json", content_type="text/plain")

        self.assertEqual(response.status_code, 400)

    def test_incomplete_axis_answers_returns_400_not_500(self):
        payload = build_full_payload()
        payload["axis_answers"] = payload["axis_answers"][:1]  # only 1 of 16 answered

        response = self.client.post("/api/results", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_top_10_entries_have_expected_fields(self):
        response = self.client.post("/api/results", json=build_full_payload())
        top_player = response.get_json()["top_10"][0]

        self.assertEqual(
            set(top_player.keys()),
            {
                "rank", "name", "team", "distance", "fit_stars",
                "notable_traits", "dominant_diff_axis", "growth_recommendation",
            },
        )
        self.assertEqual(top_player["rank"], 1)

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
