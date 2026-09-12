# 用途：L2 定位層，把 BARS 作答換算成四軸座標(A/B/C/D,各 0-100)。
# 可手動調整的變數：無——這裡是通用計算規則,不含需要人工校準的參數。
# 若要改「1-5 分怎麼映射到 0-100」的公式本身,直接改 score_axis_coordinates 內的算式。
# 題目若標記 "reverse_scored": true(目前 data/questions.json 的 axis_b3、
# axis_c1),代表這題的錨點文字是按「描述行為的字面頻率」由高到低排列(1=幾乎
# 每次,5=幾乎不會),跟其他題目「1=最少,5=最多」的方向相反——用意是讓使用者
# 讀到的選項順序全部一致,不用每題重新判斷方向。分數會先做 6-score 反轉,再
# 照正常方式平均,所以這題的軸方向不會變(2026-09-13 討論)。

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

    A question with "reverse_scored": true has its raw 1-5 score flipped
    (6 - score) before it counts toward the axis -- lets a question's anchor
    text read "1 = least, 5 = most" of the literally-described behaviour
    while the behaviour itself runs opposite to the axis (e.g. spending more
    time camped in the paint should count against the spacing axis, not for
    it), instead of forcing every anchor set to describe the axis-positive
    behaviour directly (2026-09-13 fix).
    """
    axis_by_question = {q["id"]: q["axis"] for q in questions}
    reverse_by_question = {q["id"]: q.get("reverse_scored", False) for q in questions}

    scores_by_axis = {axis: [] for axis in AXES}
    for answer in answers:
        question_id = answer["question_id"]
        if question_id not in axis_by_question:
            raise ValueError(f"answer references unknown question: {question_id}")

        score = answer["score"]
        if not (1 <= score <= 5):
            raise ValueError(f"score out of range 1-5 for {question_id}: {score}")

        if reverse_by_question[question_id]:
            score = 6 - score

        scores_by_axis[axis_by_question[question_id]].append(score)

    coordinates = {}
    for axis in AXES:
        scores = scores_by_axis[axis]
        if not scores:
            raise ValueError(f"no answers found for axis {axis}")
        average = sum(scores) / len(scores)
        coordinates[axis] = (average - 1) / 4 * 100

    return coordinates
