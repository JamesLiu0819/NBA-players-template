# 用途：L1 身體特徵層,把身材數值題(SPEC.md §5.2)的作答換算成 {欄位: 數值}
# 字典,再提供跟球員 body 欄位比對距離的函數,供「身體最貼合」深度模板使用。
# 可手動調整的變數：無——這裡是通用計算規則,不含需要人工校準的參數。目前
# players.json 的 body 欄位只有 height_cm/wingspan_cm,所以 body_distance
# 實際上只會在這兩個欄位上算距離(其餘欄位等球員資料庫補齊後自動生效,不用
# 改這支檔案)。

"""L1 body-measurement layer + a generic common-field distance function.

Pure functions only. See SPEC.md §5.2 (six numeric body measures) and the
2026-09-10 deep-template scoping discussion (docs/superpowers/plans).
"""

import math


def collect_body_measurements(questions, answers):
    """Map body-measurement answers to their semantic field names.

    questions: list of {"id", "field", "min", "max", ...}.
    answers: list of {"question_id", "value"}.

    Returns {field: value} for whichever questions were answered -- an
    unanswered question is simply omitted, not an error (unlike the BARS
    axis/skill functions, each body question is independent, so there is no
    "average of multiple answers" to fall back on).

    Raises ValueError if an answer references an unknown question, or a
    value falls outside that question's [min, max] range.
    """
    question_by_id = {q["id"]: q for q in questions}

    measurements = {}
    for answer in answers:
        question_id = answer["question_id"]
        if question_id not in question_by_id:
            raise ValueError(f"answer references unknown question: {question_id}")

        question = question_by_id[question_id]
        value = answer["value"]
        if not (question["min"] <= value <= question["max"]):
            raise ValueError(
                f"value out of range [{question['min']}, {question['max']}] "
                f"for {question_id}: {value}"
            )

        measurements[question["field"]] = value

    return measurements


def body_distance(user_body, player_body):
    """Euclidean distance between two {field: value} body dicts, computed
    only over fields present in both (see file header: today that's just
    height_cm/wingspan_cm, since players.json doesn't carry the rest yet).

    Raises ValueError if the two dicts share no fields at all.
    """
    common_fields = set(user_body) & set(player_body)
    if not common_fields:
        raise ValueError("no overlapping body fields; distance is undefined")

    return math.sqrt(
        sum((user_body[field] - player_body[field]) ** 2 for field in common_fields)
    )
