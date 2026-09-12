# 用途：v2 球員資料生成用的「模擬作答」推導邏輯。原本(v1)球員的 coordinates
# 是直接手動指定 0-100 座標,跟真人使用者「回答 1-5 題目再用
# score_axis_coordinates 算平均」的流程完全不同——這造成兩個問題：(1) 真人
# 座標受限於離散平均值的網格,球員座標卻是連續值,兩邊永遠不會完全對齊;
# (2) 球員資料完全沒有技能層級(skill_behavior)的細節,10 人對照表配對永遠
# 配不到「這個人明明說自己不會背框單打」這種資訊(2026-09-11 討論)。
# mock_axis_answers 把手動估算的目標座標反推成一組 1-5 模擬作答,球員座標
# 之後改成用這組模擬作答、透過跟真人使用者一模一樣的 score_axis_coordinates
# 算出來,不再是直接手打的數字。mock_skill_answers 則是用 axis_relevance
# 加權平均(跟 engine/relevance.py 的 compute_relevance 同一套公式)推算球員
# 對 15 個技能行為題的模擬作答,招牌技能(signature_skill_id)強制拉到滿分,
# 讓球員資料也有技能層級的細節可以比對。
# 可手動調整的變數：無——這裡是通用推導公式,不含需要人工校準的參數。

from engine.relevance import compute_relevance

AXES = ("A", "B", "C", "D")


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


def mock_skill_answers(skill_behavior_questions, skills_by_id, coordinates, signature_skill_id):
    """Derive a plausible 1-5 answer for every skill_behavior question from
    a player's axis coordinates, using the same axis_relevance-weighted-
    average formula as engine/relevance.py's compute_relevance (0-1 scale,
    rescaled to 1-5). The player's signature_skill_id (if it matches a
    question's skill_id) is forced to 5 regardless of what the relevance
    estimate alone would say -- a player's known specialty shouldn't be
    at the mercy of a rough axis-weighted guess.

    Returns a list of {"question_id", "score"} in skill_behavior_questions
    order.
    """
    answers = []
    for q in skill_behavior_questions:
        skill = skills_by_id[q["skill_id"]]
        if q["skill_id"] == signature_skill_id:
            score = 5
        else:
            relevance = compute_relevance(coordinates, skill["axis_relevance"])
            score = min(5, max(1, round(relevance * 4) + 1))
        answers.append({"question_id": q["id"], "score": score})
    return answers
