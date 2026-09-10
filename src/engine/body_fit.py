# 用途：L1 身體特徵層,把身材數值題(SPEC.md §5.2)的作答換算成 {欄位: 數值}
# 字典,再提供跟球員 body 欄位比對距離的函數,供「身體最貼合」深度模板跟 10 人
# 對照表(含身材加權)使用。body_distance 會用 field_ranges 把每個欄位正規化
# 到 0-100 再算距離,避免公分級的欄位(如 running_vertical_reach_cm)蓋過秒數
# 級的欄位(如 sprint_100m_seconds)。
# percentile_normalize_body 是另外一層轉換：身高/體重直接拿使用者的公分/公斤
# 跟 NBA 球員比,幾乎所有使用者都會比整個球員池矮/輕,身材模板永遠是池子裡最
# 矮的後衛(2026-09-11 討論)。所以先把身高/體重換算成「在籃球玩家母體裡算
# 第幾百分位」,使用者用假設的常態分佈,球員用球員池自己的實際分佈,兩邊都換成
# 百分位後才比距離；臂展/摸高/衝刺沒有可靠的一般母體數據可以參考,維持原本的
# 絕對數值正規化。
# 可手動調整的變數：GENERAL_POPULATION_BODY_STATS(假設的籃球玩家母體身高/
# 體重平均值跟標準差,是粗略估計,不是有實證來源的統計值,覺得換算出來的百分位
# 不合理可以直接調)。

"""L1 body-measurement layer + a generic common-field distance function.

Pure functions only. See SPEC.md §5.2 (six numeric body measures) and the
2026-09-10 deep-template scoping discussion (docs/superpowers/plans).
"""

import math

GENERAL_POPULATION_BODY_STATS = {
    "height_cm": (180.0, 8.0),
    "weight_kg": (78.0, 12.0),
}


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


def body_distance(user_body, player_body, field_ranges):
    """Euclidean distance between two {field: value} body dicts, computed
    only over fields present in both.

    field_ranges: {field: (min, max)} used to min-max normalize each field
    to a 0-100 scale before taking the distance. Without this, fields with
    a larger raw numeric span (e.g. running_vertical_reach_cm, spanning
    hundreds of cm) would silently dominate fields with a smaller span
    (e.g. sprint_100m_seconds, spanning a dozen or so seconds).

    Raises ValueError if the two dicts share no fields at all.
    """
    common_fields = set(user_body) & set(player_body)
    if not common_fields:
        raise ValueError("no overlapping body fields; distance is undefined")

    def normalized(value, field):
        low, high = field_ranges[field]
        return (value - low) / (high - low) * 100

    return math.sqrt(
        sum(
            (normalized(user_body[field], field) - normalized(player_body[field], field)) ** 2
            for field in common_fields
        )
    )


def _normal_cdf_percentile(value, mean, sd):
    """Percentile (0-100) of value under a normal distribution with the
    given mean/sd, via the standard erf-based CDF formula."""
    z = (value - mean) / sd
    return 50 * (1 + math.erf(z / math.sqrt(2)))


def _empirical_percentile(value, pool_values):
    """Percentile (0-100) of value within pool_values, using the mean-rank
    method (a tie counts as half a rank, so a value equal to every other
    value in the pool lands at the 50th percentile).

    Raises ValueError if pool_values is empty.
    """
    if not pool_values:
        raise ValueError("empty pool; percentile is undefined")
    below = sum(1 for v in pool_values if v < value)
    equal = sum(1 for v in pool_values if v == value)
    return (below + 0.5 * equal) / len(pool_values) * 100


def percentile_normalize_body(user_body, players, field_ranges):
    """Replace height_cm/weight_kg in user_body and every player's body
    with a percentile (0-100) in place of the raw cm/kg value, before the
    generic min-max normalization in body_distance ever sees them.

    Comparing raw cm/kg directly against an NBA roster means almost every
    self-reporting user is shorter/lighter than nearly the whole player
    pool, so the body-aware matches collapse to whichever players are
    shortest -- there is no way for a genuinely tall user to ever be
    "average" relative to the pool. Converting to percentile first answers
    a different, more useful question: "how tall/heavy are you for a
    basketball player" mapped onto "how tall/heavy is this NBA player for
    an NBA player" -- so an average recreational-ball height maps to an
    average-for-the-roster NBA size, not the shortest player in it.

    The user's percentile comes from GENERAL_POPULATION_BODY_STATS (an
    assumed normal distribution for the basketball-playing population, not
    all humans -- see file header). Each player's percentile is empirical,
    computed from the actual player pool's own distribution.

    Only fields present in both GENERAL_POPULATION_BODY_STATS and
    field_ranges are converted; every other field (wingspan_cm,
    standing_reach_cm, running_vertical_reach_cm, sprint_100m_seconds --
    none of which have a reliable general-population reference) passes
    through completely unchanged.

    Returns (new_user_body, new_players, new_field_ranges), ready to pass
    straight into body_distance / rank_similar_players_by_style_and_body
    in place of the original three arguments.
    """
    percentile_fields = set(GENERAL_POPULATION_BODY_STATS) & set(field_ranges)
    if not percentile_fields:
        return user_body, players, field_ranges

    pools = {
        field: [p["body"][field] for p in players if field in p.get("body", {})]
        for field in percentile_fields
    }

    new_user_body = dict(user_body)
    new_field_ranges = dict(field_ranges)
    for field in percentile_fields:
        if field in user_body:
            mean, sd = GENERAL_POPULATION_BODY_STATS[field]
            new_user_body[field] = _normal_cdf_percentile(user_body[field], mean, sd)
        new_field_ranges[field] = (0, 100)

    new_players = []
    for player in players:
        body = dict(player.get("body", {}))
        for field in percentile_fields:
            if field in body:
                body[field] = _empirical_percentile(body[field], pools[field])
        new_players.append({**player, "body": body})

    return new_user_body, new_players, new_field_ranges
