# 用途：v2 球員資料生成用的「模擬作答」推導邏輯。原本(v1)球員的 coordinates
# 是直接手動指定 0-100 座標,跟真人使用者「回答 1-5 題目再用
# score_axis_coordinates 算平均」的流程完全不同,兩邊永遠不會完全對齊。
# mock_axis_answers 把手動估算的目標座標反推成一組 1-5 模擬作答,球員座標
# 之後改成用這組模擬作答、透過跟真人使用者一模一樣的 score_axis_coordinates
# 算出來,不再是直接手打的數字。(2026-10 移除 mock_skill_answers:技能行為題
# 已從題庫移除,沒有東西會再讀它。)
# 可手動調整的變數：無——這裡是通用推導公式,不含需要人工校準的參數。

AXES = ("A", "B1", "B2", "C1", "C2", "D")


def mock_axis_answers(axis_positioning_questions, target_coordinates):
    """Reverse score_axis_coordinates: given a target {"A".."D": 0-100}
    coordinate dict, derive a plausible 1-5 answer for every question in
    axis_positioning_questions, such that averaging them back through
    score_axis_coordinates lands close to the target (exact when the target
    average happens to divide evenly across that axis's question count,
    off by a small rounding amount otherwise -- the same quantization a
    real user's answers are subject to).

    Distributes the target sum for each axis as evenly as possible across
    that axis's questions (remainder assigned to the first questions in
    the given order), rather than giving every question of an axis an
    identical score -- deterministic, not random, so re-running this
    produces the exact same output every time.

    Returns a list of {"question_id", "score"} in axis_positioning_questions
    order.

    A question with "reverse_scored": true gets its computed score inverted
    (6-score) before being stored -- mirrors the 6-score flip
    score_axis_coordinates applies to those questions when re-scoring real
    answers, so the stored raw answer round-trips back to the same target
    (2026-09-13 fix, see engine/axis_position.py).
    """
    answers_by_id = {}
    for axis in AXES:
        axis_questions = [q for q in axis_positioning_questions if q["axis"] == axis]
        n = len(axis_questions)
        target_avg = target_coordinates[axis] / 100 * 4 + 1
        sum_target = round(target_avg * n)
        sum_target = min(5 * n, max(1 * n, sum_target))
        base, remainder = divmod(sum_target, n)
        for i, q in enumerate(axis_questions):
            score = base + 1 if i < remainder else base
            score = min(5, max(1, score))
            if q.get("reverse_scored"):
                score = 6 - score
            answers_by_id[q["id"]] = score

    return [{"question_id": q["id"], "score": answers_by_id[q["id"]]} for q in axis_positioning_questions]
