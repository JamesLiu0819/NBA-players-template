# 用途：L1 身體特徵層,把身材數值題(SPEC.md §5.2)的作答換算成 {欄位: 數值}
# 字典,再提供跟球員 body 欄位比對距離的函數,供「身體最貼合」深度模板跟 10 人
# 對照表(含身材加權)使用。body_distance 會用 field_ranges 把每個欄位正規化
# 到 0-100 再算距離,避免公分級的欄位(如 running_vertical_reach_cm)蓋過秒數
# 級的欄位(如 sprint_100m_seconds)。
# percentile_normalize_body 是另外一層轉換：身高/體重直接拿使用者的公分/公斤
# 跟 NBA 球員比,幾乎所有使用者都會比整個球員池矮/輕,身材模板永遠是池子裡最
# 矮的後衛(2026-09-11 討論)。所以先把身高/體重換算成「在籃球玩家母體裡算
# 第幾百分位」才比距離;臂展/摸高/衝刺沒有可靠的一般母體數據可以參考,維持原本
# 的絕對數值正規化。
# 2026-10 發現使用者跟球員「兩邊各用一套不同的百分位算法」是錯的:原本使用者
# 是常態分布連續算,球員是在球員池內排名算,兩套算法對同一個身高的輸出完全不
# 可比——實測 206cm/113kg 的身材,算出來跟「206cm/112kg、幾乎一模一樣」的
# Karl Malone 距離反而比跟「216cm/126kg、真的差了一大截」的 Shaq 還遠,因為
# Malone 206cm 在球員池自己的排名只排到 61.7 百分位(球員池本來就一堆更高的
# 中鋒),但使用者的 206cm 用常態分布算出來是 95+ 百分位,兩個數字對不上。
# 所以改成兩邊都套同一套函數(_tail_capped_percentile),才能真的比出「身材
# 像不像」而不是「兩套不相干的排名剛好湊近」。這套函數在門檻(身高 190cm /
# 體重 93kg,對應 TALL_ATHLETE_THRESHOLD_Z=1.25 個標準差,使用者建議的「超過
# 這個身材條件大概率已經是職業球員」)以下維持原本的常態分布累積機率,超過門檻
# 後改成線性,從門檻百分位一路拉到 100(對應題目定義的最大值),避免 NBA 等級
# 的身高體重全部被常態分布尾端壓縮成幾乎同一個數字(206cm 跟 220cm 用常態分布
# 算出來都逼近 99.9%+,線性段才能把這段差距攤開,維持區分度)。門檻以下(一般
# 使用者最常落的範圍)完全沒變,169/188cm 的既有驗證案例行為不變。
# 可手動調整的變數：GENERAL_POPULATION_BODY_STATS(假設的籃球玩家母體身高/
# 體重平均值跟標準差,是粗略估計,不是有實證來源的統計值,覺得換算出來的百分位
# 不合理可以直接調)、TALL_ATHLETE_THRESHOLD_Z(超過這個標準差就從常態分布切換
# 成線性,目前 1.25 對應身高門檻 190cm,體重門檻同一個 z 值算出來是 93kg)。
# missing_required_body_fields：身高、體重(data/questions.json body_measurements
# 裡標 "required": true 的題目)是 engine/archetype.py 體型分數的必要輸入,沒填
# 就無法算,所以後端在算模板結果前要先擋掉;其餘身材題維持選填,省略不算錯
# (2026-10 討論)。

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


def missing_required_body_fields(questions, answers):
    """Return the ids of required body questions with no matching answer.

    questions: list of {"id", ..., "required": bool (optional, default False)}.
    answers: list of {"question_id", "value"}.

    A question counts as answered if any answer references its id, regardless
    of that answer's value -- range validation is collect_body_measurements'
    job, not this function's.
    """
    answered_ids = {a["question_id"] for a in answers}
    return [q["id"] for q in questions if q.get("required", False) and q["id"] not in answered_ids]


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


TALL_ATHLETE_THRESHOLD_Z = 1.25

# 2026-10 分段比較門檻（spec item 1）：使用者在門檻以下時，球員用「在自己
# 那個球員池內排第幾」取代常態分布百分位，避免身材比重幾乎占滿距離平方的
# 六成、把所有使用者拉向池子裡最矮最輕的幾位球員。兩組門檻各以現有的
# TALL_ATHLETE_THRESHOLD_Z 門檻（190cm／93kg）為中心，前後 10 個單位線性
# 過渡，是暫定值，之後要調整就直接改這四個數字。
HEIGHT_TRANSITION_LOW = 185.0
HEIGHT_TRANSITION_HIGH = 195.0
WEIGHT_TRANSITION_LOW = 88.0
WEIGHT_TRANSITION_HIGH = 98.0

TRANSITION_BOUNDS = {
    "height_cm": (HEIGHT_TRANSITION_LOW, HEIGHT_TRANSITION_HIGH),
    "weight_kg": (WEIGHT_TRANSITION_LOW, WEIGHT_TRANSITION_HIGH),
}


def _transition_weight(value, low, high):
    """0 at/below low, 1 at/above high, linear in between -- how much a
    player's percentile for this field should come from the population
    curve (_tail_capped_percentile) versus from ranking within the player
    pool (_empirical_percentile_within_pool), based on the USER's own raw
    value for this field."""
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return (value - low) / (high - low)


def _empirical_percentile_within_pool(value, pool_values):
    """Percentile (0-100) of value within pool_values, mean-rank method (a
    tie counts as half a rank) -- mirrors engine/archetype.py's
    _empirical_percentile, duplicated here rather than imported: this
    module stays self-contained (L1, no cross-module dependency), and the
    two percentiles serve different purposes even though the formula is
    the same shape.

    A single-element pool returns 50.0 (the value is simultaneously the
    pool's min and max; there is no meaningful rank to report).
    """
    below = sum(1 for v in pool_values if v < value)
    equal = sum(1 for v in pool_values if v == value)
    return (below + 0.5 * equal) / len(pool_values) * 100


def _tail_capped_percentile(value, mean, sd, field_max, threshold_z=TALL_ATHLETE_THRESHOLD_Z):
    """Percentile (0-100) of value under a normal(mean, sd) distribution,
    except above threshold_z standard deviations it switches from the CDF
    to a straight line up to field_max -- see file header for why. Below
    the threshold this is identical to _normal_cdf_percentile.
    """
    threshold_value = mean + threshold_z * sd
    if value <= threshold_value:
        return _normal_cdf_percentile(value, mean, sd)
    threshold_pct = _normal_cdf_percentile(threshold_value, mean, sd)
    fraction = min((value - threshold_value) / (field_max - threshold_value), 1.0)
    return threshold_pct + fraction * (100 - threshold_pct)


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

    Both the user's and every player's percentile come from the SAME
    _tail_capped_percentile curve (GENERAL_POPULATION_BODY_STATS mean/sd,
    field_ranges' max as the top of the linear tail) -- see file header for
    why using two different curves (continuous for the user, empirical
    rank-within-pool for players) produced incomparable numbers.

    2026-10 (spec item 1): a player's percentile for height_cm/weight_kg is
    no longer always the population tail-capped curve. It's a blend between
    that curve and the player's rank WITHIN THIS SPECIFIC players POOL
    (_empirical_percentile_within_pool), weighted by where the USER's own
    raw value for that field falls relative to TRANSITION_BOUNDS[field]: at
    or below the low bound, players are ranked purely within the pool (a
    "how do you compare to other recreational players" framing on both
    sides); at or above the high bound, this reproduces today's behavior
    exactly (both sides on the same population curve); linear in between.
    The user's OWN percentile is never blended -- always the plain
    population curve, as before. Only height_cm/weight_kg are affected;
    every other field is untouched, same as before.

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

    def tail_pct(field, raw_value):
        mean, sd = GENERAL_POPULATION_BODY_STATS[field]
        field_max = field_ranges[field][1]
        return _tail_capped_percentile(raw_value, mean, sd, field_max)

    new_user_body = dict(user_body)
    new_field_ranges = dict(field_ranges)
    for field in percentile_fields:
        if field in user_body:
            new_user_body[field] = tail_pct(field, user_body[field])
        new_field_ranges[field] = (0, 100)

    # Pool of raw values per field, collected BEFORE any conversion -- needed
    # for the within-pool percentile and must never see already-converted
    # values from a previous call.
    pool_raw_values = {
        field: [player["body"][field] for player in players if field in player.get("body", {})]
        for field in percentile_fields
    }
    transition_weight = {
        field: (
            _transition_weight(user_body[field], *TRANSITION_BOUNDS[field])
            if field in user_body else 1.0  # no user value to decide the blend -> old behavior
        )
        for field in percentile_fields
    }

    new_players = []
    for player in players:
        body = dict(player.get("body", {}))
        for field in percentile_fields:
            if field not in body:
                continue
            w = transition_weight[field]
            pool_pct = _empirical_percentile_within_pool(body[field], pool_raw_values[field])
            population_pct = tail_pct(field, body[field])
            body[field] = (1 - w) * pool_pct + w * population_pct
        new_players.append({**player, "body": body})

    return new_user_body, new_players, new_field_ranges
