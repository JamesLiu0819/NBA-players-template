# 用途：測試 score_axis_coordinates(把 BARS 作答換算成四軸座標)的計算邏輯,
# 包含正常情況、缺題目、答案對不到題目、分數超出範圍等邊界情況。
# 可手動調整的變數：無——QUESTIONS 是固定的測試用假資料(16 題,每軸 4 題),
# 不是要調的參數,是為了讓測試獨立於 data/questions.json 的實際內容。

import unittest

from engine.axis_position import score_axis_coordinates

QUESTIONS = [
    {"id": "a1", "axis": "A", "prompt": "..."},
    {"id": "a2", "axis": "A", "prompt": "..."},
    {"id": "a3", "axis": "A", "prompt": "..."},
    {"id": "a4", "axis": "A", "prompt": "..."},
    {"id": "b1", "axis": "B", "prompt": "..."},
    {"id": "b2", "axis": "B", "prompt": "..."},
    {"id": "b3", "axis": "B", "prompt": "..."},
    {"id": "b4", "axis": "B", "prompt": "..."},
    {"id": "c1", "axis": "C", "prompt": "..."},
    {"id": "c2", "axis": "C", "prompt": "..."},
    {"id": "c3", "axis": "C", "prompt": "..."},
    {"id": "c4", "axis": "C", "prompt": "..."},
    {"id": "d1", "axis": "D", "prompt": "..."},
    {"id": "d2", "axis": "D", "prompt": "..."},
    {"id": "d3", "axis": "D", "prompt": "..."},
    {"id": "d4", "axis": "D", "prompt": "..."},
]


def answers_with_scores(scores_by_prefix):
    """Build a full 16-answer set; scores_by_prefix maps axis letter -> list of 4 scores."""
    answers = []
    for axis, scores in scores_by_prefix.items():
        prefix = axis.lower()
        for i, score in enumerate(scores, start=1):
            answers.append({"question_id": f"{prefix}{i}", "score": score})
    return answers


class ScoreAxisCoordinatesTest(unittest.TestCase):
    def test_mid_scale_answers_map_to_50_on_every_axis(self):
        answers = answers_with_scores({
            "A": [3, 3, 3, 3],
            "B": [3, 3, 3, 3],
            "C": [3, 3, 3, 3],
            "D": [3, 3, 3, 3],
        })

        coords = score_axis_coordinates(QUESTIONS, answers)

        self.assertEqual(coords, {"A": 50.0, "B": 50.0, "C": 50.0, "D": 50.0})

    def test_averages_scores_within_an_axis_before_scaling(self):
        answers = answers_with_scores({
            "A": [1, 5, 3, 3],  # avg 3 -> 50
            "B": [5, 5, 5, 5],  # avg 5 -> 100
            "C": [1, 1, 1, 1],  # avg 1 -> 0
            "D": [1, 2, 3, 4],  # avg 2.5 -> 37.5
        })

        coords = score_axis_coordinates(QUESTIONS, answers)

        self.assertEqual(coords["A"], 50.0)
        self.assertEqual(coords["B"], 100.0)
        self.assertEqual(coords["C"], 0.0)
        self.assertEqual(coords["D"], 37.5)

    def test_missing_axis_answers_raises(self):
        answers = answers_with_scores({
            "A": [3, 3, 3, 3],
            "B": [3, 3, 3, 3],
            "C": [3, 3, 3, 3],
            # D missing entirely
        })

        with self.assertRaises(ValueError):
            score_axis_coordinates(QUESTIONS, answers)

    def test_answer_referencing_unknown_question_raises(self):
        answers = answers_with_scores({
            "A": [3, 3, 3, 3],
            "B": [3, 3, 3, 3],
            "C": [3, 3, 3, 3],
            "D": [3, 3, 3, 3],
        })
        answers.append({"question_id": "does-not-exist", "score": 3})

        with self.assertRaises(ValueError):
            score_axis_coordinates(QUESTIONS, answers)

    def test_score_out_of_range_raises(self):
        answers = answers_with_scores({
            "A": [3, 3, 3, 3],
            "B": [3, 3, 3, 3],
            "C": [3, 3, 3, 3],
            "D": [3, 3, 3, 6],  # invalid
        })

        with self.assertRaises(ValueError):
            score_axis_coordinates(QUESTIONS, answers)


if __name__ == "__main__":
    unittest.main()
