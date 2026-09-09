# 用途：L2 定位層，把 BARS 作答換算成四軸座標(A/B/C/D,各 0-100)。
# 可手動調整的變數：無——這裡是通用計算規則,不含需要人工校準的參數。
# 若要改「1-5 分怎麼映射到 0-100」的公式本身,直接改 score_axis_coordinates 內的算式。

"""L2 positioning layer: four-axis coordinates (A/B/C/D, each 0-100).

Pure functions only. See SPEC.md §3.1 and §5.1 (BARS rationale).
"""

AXES = ("A", "B", "C", "D")


def score_axis_coordinates(questions, answers):
    """Compute the four-axis positioning coordinates from BARS answers.

    questions: list of {"id", "axis", ...} covering all four axes.
    answers: list of {"question_id", "score"} where score is a 1-5 Likert value.

    Returns {"A": float, "B": float, "C": float, "D": float}, each 0-100,
    derived by averaging the 1-5 answers for that axis and rescaling
    linearly so 1 -> 0 and 5 -> 100.

    Raises ValueError if an answer references an unknown question, a score
    is outside 1-5, or any axis has no answers at all.
    """
    axis_by_question = {q["id"]: q["axis"] for q in questions}

    scores_by_axis = {axis: [] for axis in AXES}
    for answer in answers:
        question_id = answer["question_id"]
        if question_id not in axis_by_question:
            raise ValueError(f"answer references unknown question: {question_id}")

        score = answer["score"]
        if not (1 <= score <= 5):
            raise ValueError(f"score out of range 1-5 for {question_id}: {score}")

        scores_by_axis[axis_by_question[question_id]].append(score)

    coordinates = {}
    for axis in AXES:
        scores = scores_by_axis[axis]
        if not scores:
            raise ValueError(f"no answers found for axis {axis}")
        average = sum(scores) / len(scores)
        coordinates[axis] = (average - 1) / 4 * 100

    return coordinates
