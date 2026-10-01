# 用途：L2 定位層，把 BARS 作答換算成六軸座標(A/B1/B2/C1/C2/D,各 0-100)。
# 可手動調整的變數：無——這裡是通用計算規則,不含需要人工校準的參數,AXES 元組
# 本身也不是用來調的參數(改軸數要連 data/questions.json、skills.json、
# archetypes.json、players.json 一起動,不是只改這裡)。
# 若要改「1-5 分怎麼映射到 0-100」的公式本身,直接改 score_axis_coordinates 內的算式。
# 題目若標記 "reverse_scored": true,代表這題的錨點文字是按「描述行為的字面
# 頻率」由高到低排列(1=幾乎每次,5=幾乎不會),跟其他題目「1=最少,5=最多」的
# 方向相反——用意是讓使用者讀到的選項順序全部一致,不用每題重新判斷方向。分數
# 會先做 6-score 反轉,再照正常方式平均,所以這題的軸方向不會變(2026-09-13
# 討論)。2026-10 六軸改版後目前沒有任何一題用到這個欄位——舊版 B/C 軸裡需要
# 反轉的題目問的其實是「站位/角色分配」而非「表現好壞」,改版時已經重寫成直接
# 的表現型問法,不再需要反轉(見 data/questions.json 的 _editable_fields),
# 但函式本身繼續支援這個欄位,未來要加類似題目還是可以用。

"""L2 positioning layer: six-axis coordinates (A/B1/B2/C1/C2/D, each 0-100).

Pure functions only. See SPEC.md §3.1 and §5.1 (BARS rationale).
"""

AXES = ("A", "B1", "B2", "C1", "C2", "D")


def score_axis_coordinates(questions, answers):
    """Compute the six-axis positioning coordinates from BARS answers.

    questions: list of {"id", "axis", ...} covering all six axes.
    answers: list of {"question_id", "score"} where score is a 1-5 Likert value.

    Returns {"A"/"B1"/"B2"/"C1"/"C2"/"D": float}, each 0-100,
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
