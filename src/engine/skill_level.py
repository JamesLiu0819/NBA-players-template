# 用途：L1 技能向量，把 BARS 作答換算成技能現況水準,再算出缺口 G_i。
# 可手動調整的變數：compute_gap 的 target 預設值(目前是 5.0,代表「精熟」)。
# 如果之後想讓目標水準依角色定位或使用者設定的目標而不同,就是改這個預設值的呼叫端,
# 不是改這支檔案的邏輯本身。

"""L1 skill vector: current behavioral level and gap G_i.

Pure functions only. See SPEC.md §4 (G_i) and §5.1 (BARS rationale).
"""


def score_skill_current_level(questions, answers, skill_id):
    """Average the BARS answers belonging to skill_id into a 1-5 current level.

    questions: list of {"id", "skill_id", ...}.
    answers: list of {"question_id", "score"} where score is a 1-5 Likert value.

    Raises ValueError if skill_id has no matching questions, none of its
    questions were answered, or an answered score is outside 1-5.
    """
    question_ids = {q["id"] for q in questions if q["skill_id"] == skill_id}
    if not question_ids:
        raise ValueError(f"no questions defined for skill: {skill_id}")

    scores = []
    for answer in answers:
        if answer["question_id"] not in question_ids:
            continue
        score = answer["score"]
        if not (1 <= score <= 5):
            raise ValueError(f"score out of range 1-5 for {answer['question_id']}: {score}")
        scores.append(score)

    if not scores:
        raise ValueError(f"no answers found for skill: {skill_id}")

    return sum(scores) / len(scores)


def score_skill_current_level_from_single_answer(answers, question_id):
    """Use one BARS answer's raw 1-5 score directly as a skill's current level.

    For skills whose dedicated skill_behavior question was removed as a
    duplicate of an axis_positioning question (see "also_measures_skill" in
    questions.json): the axis question asks about literally the same
    real-world behavior, so its score is a valid substitute measurement.

    answers: list of {"question_id", "score"}.
    question_id: id of the substitute question to read the score from.

    Raises ValueError if question_id has no matching answer, or its score is
    outside 1-5.
    """
    for answer in answers:
        if answer["question_id"] == question_id:
            score = answer["score"]
            if not (1 <= score <= 5):
                raise ValueError(f"score out of range 1-5 for {question_id}: {score}")
            return score
    raise ValueError(f"no answer found for question: {question_id}")


def compute_gap(current, target=5.0):
    """G_i = target level minus current level, clamped to [0, 5].

    A skill already at or above its target contributes no gap (0), since a
    negative gap would otherwise imply negative priority in P_i.
    """
    return max(0.0, target - current)
