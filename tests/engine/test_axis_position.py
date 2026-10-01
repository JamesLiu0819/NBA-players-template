# 用途：測試 score_axis_coordinates(把 BARS 作答換算成六軸座標)的計算邏輯,
# 包含正常情況、缺題目、答案對不到題目、分數超出範圍等邊界情況。
# 可手動調整的變數：無——QUESTIONS 是固定的測試用假資料(12 題,每軸 2 題),
# 不是要調的參數,是為了讓測試獨立於 data/questions.json 的實際內容。

import unittest

from engine.axis_position import score_axis_coordinates

AXES = ("A", "B1", "B2", "C1", "C2", "D")

QUESTIONS = [
    {"id": f"{axis}_{i}", "axis": axis, "prompt": "..."}
    for axis in AXES
    for i in (1, 2)
]


def answers_with_scores(scores_by_axis):
    """Build a full 12-answer set; scores_by_axis maps axis -> list of 2 scores."""
    answers = []
    for axis, scores in scores_by_axis.items():
        for i, score in enumerate(scores, start=1):
            answers.append({"question_id": f"{axis}_{i}", "score": score})
    return answers


ALL_MID = {axis: [3, 3] for axis in AXES}


class ScoreAxisCoordinatesTest(unittest.TestCase):
    def test_mid_scale_answers_map_to_50_on_every_axis(self):
        answers = answers_with_scores(ALL_MID)

        coords = score_axis_coordinates(QUESTIONS, answers)

        self.assertEqual(coords, {axis: 50.0 for axis in AXES})

    def test_averages_scores_within_an_axis_before_scaling(self):
        scores = dict(ALL_MID)
        scores.update({
            "A": [1, 5],    # avg 3 -> 50
            "B1": [5, 5],   # avg 5 -> 100
            "C1": [1, 1],   # avg 1 -> 0
            "D": [2, 3],    # avg 2.5 -> 37.5
        })
        answers = answers_with_scores(scores)

        coords = score_axis_coordinates(QUESTIONS, answers)

        self.assertEqual(coords["A"], 50.0)
        self.assertEqual(coords["B1"], 100.0)
        self.assertEqual(coords["C1"], 0.0)
        self.assertEqual(coords["D"], 37.5)

    def test_missing_axis_answers_raises(self):
        scores = dict(ALL_MID)
        del scores["D"]  # D missing entirely
        answers = answers_with_scores(scores)

        with self.assertRaises(ValueError):
            score_axis_coordinates(QUESTIONS, answers)

    def test_answer_referencing_unknown_question_raises(self):
        answers = answers_with_scores(ALL_MID)
        answers.append({"question_id": "does-not-exist", "score": 3})

        with self.assertRaises(ValueError):
            score_axis_coordinates(QUESTIONS, answers)

    def test_score_out_of_range_raises(self):
        scores = dict(ALL_MID)
        scores["D"] = [3, 6]  # invalid
        answers = answers_with_scores(scores)

        with self.assertRaises(ValueError):
            score_axis_coordinates(QUESTIONS, answers)

    def test_reverse_scored_question_flips_its_raw_score_before_averaging(self):
        # the 2nd B2 question is flagged reverse_scored: a raw score of 1
        # should contribute like a 5 (and vice versa) so anchor text can read
        # "1 = least, 5 = most" of the literal described behaviour while
        # still counting toward the axis in the intended direction
        # (2026-09-13 fix).
        questions = [q.copy() for q in QUESTIONS]
        for q in questions:
            if q["id"] == "B2_2":
                q["reverse_scored"] = True

        scores = dict(ALL_MID)
        scores["B2"] = [5, 1]  # B2_2=1, reverse-scored -> counts as 5
        answers = answers_with_scores(scores)

        coords = score_axis_coordinates(questions, answers)

        self.assertEqual(coords["B2"], 100.0)


if __name__ == "__main__":
    unittest.main()
