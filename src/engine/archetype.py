# 用途：把使用者分類到最接近的球場定位原型(data/archetypes.json)。
# classify_archetype 是最基本的最近鄰(Euclidean distance)比對,跟
# player_matching.py 找最像球員的邏輯是同一套精神,只是比對對象換成原型
# 錨點。classify_archetype_for_user 是結果頁實際使用的版本,直接拿使用者
# 自己的六軸座標比對原型(2026-10,spec item 5)——取代舊版「把 10 人對照表
# 前 N 位最相似的真人球員各自分類到最近的原型,再取多數決」的設計：舊設計的
# 問題是答案很平、沒有明顯風格的使用者,最後的原型標籤其實跟自己的座標無關,
# 只是鄰近球員剛好多數落在哪個原型(2026-09-13 討論引入多數決,2026-10 發現
# 這個根本缺陷後整個換掉)。新設計先用 style_axis_spread 判斷使用者在五個
# 技術軸(不含 D)上有沒有明顯的主打方向：有(>= ARCHETYPE_SPREAD_THRESHOLD)
# 就用「打法形狀」分類(_relative_strength_distance,雙方都先各自扣掉自己的
# 五軸平均值,只比較相對強弱,整體水準高低不影響結果);沒有就改用身材分數
# (compute_user_size)單獨比對,因為打法本身沒有訊號可用。
# 可手動調整的變數：ARCHETYPE_SPREAD_THRESHOLD(多少才算「有明顯主打方向」,
# 目前 25,見下方該常數旁的註解)。原型本身的數量/座標/文案在
# data/archetypes.json 裡調整,不在這支檔案。
#
# size 參數(2026-10 討論)：classify_archetype 原本純看六軸(A/B1/B2/C1/C2/D),
# 完全不看身材,結果矮個子只要打法平均就會被分類到「全能鋒線」之類隱含高大身材
# 的原型,高個子打控球風格也會被分類到「控場指揮官」——原型名稱在使用者認知裡
# 跟身材綁在一起,但計算本身完全沒有身材這個維度。size 是身高百分位跟體重百分位
# 的平均(不是直接算 BMI——BMI=體重/身高^2 會把身高訊號本身抵銷掉,而身高才是
# 真正決定「後衛 vs 中鋒」觀感的主因),跟六軸一樣是 0-100 尺度,所以直接
# 併入同一個歐氏距離,不用額外正規化。size 是選填參數,沒傳或原型缺 size 欄位
# 就完全退化成原本的純六軸距離。
#
# size 要用哪種百分位(2026-10 二次討論,修正前一版的誤用)：compute_player_sizes
# 算的是「身高/體重在這份 players 名單裡排第幾名」(0=全名單最矮最輕,100=全
# 名單最高最重)——跟 body_fit.percentile_normalize_body 給 10 人對照表身材比對
# 用的百分位(使用者 vs 一般人口常態分布)是兩個完全不同的量尺,不能共用同一個
# 轉換結果。之前讓兩者共用 percentile_normalize_body 的輸出,NBA 球員跟一般人比
# 幾乎全部落在 85-99 之間,把球員池內部「後衛 vs 中鋒」的區分度洗掉了,結果
# Bradley Beal、Anfernee Simons、Kyrie Irving 這種後衛的 size 都變成 90 上下,
# 比archetypes.json 裡任何後衛原型的 size 錨點(25-47)都高出一大截,反而被歸類
# 成內線型原型。所以 compute_player_sizes 必須吃「轉換前的原始 players 名單」
# (每位球員的 body.height_cm/weight_kg 是公分/公斤原始值,不是已經換算過的
# 百分位),在 percentile_normalize_body 把這些數字覆寫成另一種百分位之前就先
# 算好。archetypes.json 裡現有的 size 錨點數值(25-87)就是用這套「球員池內部
# 排名」校準出來的,不用跟著改。compute_player_sizes 現在只剩自己的測試在用
# (2026-10,改用 classify_archetype_for_user 後,結果頁改用 compute_user_size
# 算使用者自己的身材分數——同一份原始 players 名單、同一個「要在
# percentile_normalize_body 之前算」的時機限制,邏輯寫在 compute_user_size
# 自己的 docstring 裡,呼叫端是 server/app.py、scripts/run_player_match.py)。
# spec 目前只要求移除 classify_archetype_by_majority,compute_player_sizes
# 本身保留,沒有跟著刪。
#
# 2026-10 Task 9 驗收發現（尚未修正，記錄給之後處理）：全選同一分數的使用者
# （身材從 N(175,7)/N(70,12) 抽樣）在 compute_user_size 底下仍有約 99.7% 落在
# 同一個原型（combo_scorer,size=25,全部原型裡最小的錨點）,遠超驗收標準的
# 40% 上限。原因跟 Task 7 checkpoint 當時發現的問題同一個根源,只是沒有真正解決：
# compute_user_size 是對「球員池自己的身高體重」(現役池平均約 200cm)擬合常態
# 分布,一般使用者（平均 175cm）距離球員池平均 2-3 個標準差,算出來的 size 幾乎
# 全部落在 0 附近,而 25-87 的原型錨點裡沒有比 25 更小的錨點可以再往下分——不管
# 哪個使用者,只要 size 小於 28（combo_scorer 跟下一個錨點 floor_general=31 的
# 中點）都會收斂到同一個 combo_scorer。換成對一般人口分布(GENERAL_POPULATION_
# BODY_STATS)算百分位可以把 size 的分布拉開(0.97-94,平均約 31,12 個原型都會
# 被選到),但最大單一佔比仍有約 51%,一樣超過 40%——因為原型錨點本身在小尺寸
# 這端的密度不夠,換百分位算法本身不足以解決,需要連同 data/原型.json 的 size
# 錨點分布一起檢討,不是這支檔案能單獨修完的範圍。見
# .superpowers/sdd/2026-10-07-result-accuracy-fixes/task-9-report.md。

"""L3-adjacent matching layer: nearest-neighbor archetype classification.

Pure functions only.
"""

import math

AXES = ("A", "B1", "B2", "C1", "C2", "D")
SIZE_AXIS_WEIGHT = 1.0


def classify_archetype(coordinates, archetypes, size=None):
    """Return the archetype (from archetypes) whose coordinates are
    closest to the given coordinates (Euclidean distance over AXES).

    archetypes: list of dicts, each with at least "coordinates": {axis: 0-100
        for axis in AXES}. All other fields on the winning archetype pass
        through unchanged.
    size: optional 0-100 body-size score (see module header -- typically the
        average of a player's height and weight percentiles). When given,
        an archetype's own "size" field (if present) contributes
        (archetype["size"] - size)^2 * SIZE_AXIS_WEIGHT to the squared
        distance alongside AXES, so archetypes whose real-world body
        profile is far from `size` are penalized even if their style axes
        are close. An archetype missing a "size" field is treated as
        size-neutral (no penalty term) regardless of `size`.

    Raises ValueError if archetypes is empty.
    """
    if not archetypes:
        raise ValueError("archetypes must not be empty; classification is undefined")

    def distance(archetype):
        squared = sum(
            (archetype["coordinates"][axis] - coordinates[axis]) ** 2 for axis in AXES
        )
        if size is not None and "size" in archetype:
            squared += (archetype["size"] - size) ** 2 * SIZE_AXIS_WEIGHT
        return math.sqrt(squared)

    return min(archetypes, key=distance)


def _empirical_percentile(value, pool_values):
    """Percentile (0-100) of value within pool_values, using the mean-rank
    method (a tie counts as half a rank).

    Raises ValueError if pool_values is empty.
    """
    if not pool_values:
        raise ValueError("empty pool; percentile is undefined")
    below = sum(1 for v in pool_values if v < value)
    equal = sum(1 for v in pool_values if v == value)
    return (below + 0.5 * equal) / len(pool_values) * 100


def compute_player_sizes(players):
    """Return {player_id: size} for every player in `players` that has both
    height_cm and weight_kg in its body dict -- size is the average of the
    player's height/weight percentile, computed empirically WITHIN THIS
    SPECIFIC players LIST (0 = shortest/lightest in the list, 100 =
    tallest/heaviest). See module header for why this must run on players'
    original raw body data, before anything (e.g.
    body_fit.percentile_normalize_body) overwrites height_cm/weight_kg with
    a different percentile meant for a different purpose.

    Players missing height_cm or weight_kg are omitted from the result; look
    up with player_sizes.get(player_id) and treat a miss as "no size data".
    (This function has no caller left in production code since 2026-10's
    classify_archetype_by_majority removal -- only its own tests use it now;
    see the module header for why it's kept anyway.)
    """
    with_body = [
        p for p in players
        if "height_cm" in p.get("body", {}) and "weight_kg" in p.get("body", {})
    ]
    height_pool = [p["body"]["height_cm"] for p in with_body]
    weight_pool = [p["body"]["weight_kg"] for p in with_body]
    return {
        p["id"]: (
            _empirical_percentile(p["body"]["height_cm"], height_pool)
            + _empirical_percentile(p["body"]["weight_kg"], weight_pool)
        ) / 2
        for p in with_body
    }


ARCHETYPE_SPREAD_THRESHOLD = 25.0  # 暫定，見 spec item 5：每軸兩題平均，分數
# 只會是 12.5 的倍數，高低差小於 25 代表五軸全部落在相鄰兩格以內。
STYLE_AXES_FOR_SPREAD = ("A", "B1", "B2", "C1", "C2")  # D excluded -- athletic
# ability isn't part of "which skill are you strongest at".


def style_axis_spread(coordinates):
    """max - min over the five trainable style axes (A/B1/B2/C1/C2) -- D is
    excluded, same set skill_gap trains on. Used to decide whether a user
    has a real standout strength (classify by shape) or not (classify by
    body alone) -- see classify_archetype_for_user."""
    values = [coordinates[axis] for axis in STYLE_AXES_FOR_SPREAD]
    return max(values) - min(values)


def _recentered(coordinates):
    mean = sum(coordinates[axis] for axis in STYLE_AXES_FOR_SPREAD) / len(STYLE_AXES_FOR_SPREAD)
    return {axis: coordinates[axis] - mean for axis in STYLE_AXES_FOR_SPREAD}


def _relative_strength_distance(coordinates, archetype, size):
    user_centered = _recentered(coordinates)
    archetype_centered = _recentered(archetype["coordinates"])
    squared = sum(
        (user_centered[axis] - archetype_centered[axis]) ** 2 for axis in STYLE_AXES_FOR_SPREAD
    )
    if size is not None and "size" in archetype:
        squared += (archetype["size"] - size) ** 2 * SIZE_AXIS_WEIGHT
    return math.sqrt(squared)


def _pool_normal_fit_percentile(value, pool_values):
    """Percentile (0-100) of value under a normal distribution fit to
    pool_values' OWN mean/sd (computed from pool_values itself, not a fixed
    external constant), via the standard erf-based CDF.

    Unlike a plain rank-within-pool percentile (compute_player_sizes'
    method), this extrapolates smoothly below the pool's observed minimum
    (or above its maximum) instead of collapsing every value past the edge
    to the same 0 or 100 -- see compute_user_size's docstring for why this
    matters (2026-10, Task 7 checkpoint finding).

    Raises ValueError if pool_values has fewer than 2 values, or its
    variance is 0 (a normal fit is undefined when every value is
    identical).
    """
    if len(pool_values) < 2:
        raise ValueError("pool must have at least 2 values; percentile fit is undefined")
    mean = sum(pool_values) / len(pool_values)
    variance = sum((v - mean) ** 2 for v in pool_values) / len(pool_values)
    if variance == 0:
        raise ValueError("pool has zero variance; normal fit is undefined")
    sd = math.sqrt(variance)
    z = (value - mean) / sd
    return 50 * (1 + math.erf(z / math.sqrt(2)))


def compute_user_size(user_body, players):
    """Return the user's body size (0-100) on the SAME 0-100 scale the
    archetype "size" anchors (data/zh/原型.json, 25-87) were calibrated on.

    2026-10 (Task 7 checkpoint finding): this does NOT rank the user within
    the player pool the way compute_player_sizes ranks a player -- a plain
    empirical rank collapses almost every self-reporting user to
    percentile ~0, because a typical user (~175cm) falls below the
    shortest real NBA player (~185cm), below the entire pool's observed
    floor. Simulating 300 users with a flat answer profile (so this
    function was the ONLY thing deciding their archetype) showed 99-100%
    landing on the same single archetype regardless of their actual height
    or weight -- the body-only branch carried no real signal.

    Instead, this fits a NORMAL distribution to THIS SPECIFIC players
    pool's own real height_cm/weight_kg (mean & sd computed from the pool
    itself -- the current and all-time pools have different real
    distributions, so this is never a fixed constant) and reads the user's
    percentile off that curve via _pool_normal_fit_percentile. This agrees
    closely with compute_player_sizes' empirical rank for values WITHIN the
    pool's own observed range, but -- unlike that rank -- extrapolates
    smoothly below/above the pool's floor/ceiling instead of collapsing
    every out-of-range value to the same number.

    Returns None if user_body is missing height_cm or weight_kg, if fewer
    than 2 players in `players` have both fields, or if the pool's
    height/weight values have zero variance (a degenerate pool where a
    normal fit is undefined).
    """
    if "height_cm" not in user_body or "weight_kg" not in user_body:
        return None
    with_body = [
        p for p in players
        if "height_cm" in p.get("body", {}) and "weight_kg" in p.get("body", {})
    ]
    if len(with_body) < 2:
        return None
    height_pool = [p["body"]["height_cm"] for p in with_body]
    weight_pool = [p["body"]["weight_kg"] for p in with_body]
    try:
        height_pct = _pool_normal_fit_percentile(user_body["height_cm"], height_pool)
        weight_pct = _pool_normal_fit_percentile(user_body["weight_kg"], weight_pool)
    except ValueError:
        return None
    return (height_pct + weight_pct) / 2


def classify_archetype_for_user(coordinates, archetypes, size=None, spread_threshold=ARCHETYPE_SPREAD_THRESHOLD):
    """Classify the USER's own coordinates directly against the archetype
    anchors -- replaces the old neighbor-majority-vote approach (2026-10,
    spec item 5): a user who answers every question the same way no longer
    gets dumped into whatever archetype their nearest (equally-flat)
    neighbors happen to be voted into.

    style_axis_spread(coordinates) >= spread_threshold (a real standout
    strength exists): classify by SHAPE -- both the user and each
    archetype are recentered (each axis minus that entity's own five-axis
    mean) before comparing, so overall level cancels out and only "which
    block are you strongest in" matters. Body size still factors in
    exactly as classify_archetype already does (added to the squared
    distance when both `size` and the archetype's own "size" field are
    present).

    style_axis_spread(coordinates) < spread_threshold (no standout -- a
    flat or near-flat answer profile): classify by BODY SIZE ALONE among
    archetypes that have a "size" field, picking the closest; ties (or a
    genuinely missing `size`) break on ascending archetype id for
    determinism. If `size` itself is None (no body data to compare), this
    falls back to the shape-based classification above instead -- there is
    no signal to pick a body-only answer from.

    Returns (archetype, mode) where mode is the literal string
    "relative_strength" or "body_only", so callers can choose the matching
    UI copy. Raises ValueError if archetypes is empty.
    """
    if not archetypes:
        raise ValueError("archetypes must not be empty; classification is undefined")

    spread = style_axis_spread(coordinates)
    if spread >= spread_threshold or size is None:
        winner = min(archetypes, key=lambda a: _relative_strength_distance(coordinates, a, size))
        return winner, "relative_strength"

    with_size = [a for a in archetypes if "size" in a]
    if not with_size:
        winner = min(archetypes, key=lambda a: _relative_strength_distance(coordinates, a, size))
        return winner, "relative_strength"

    winner = min(with_size, key=lambda a: (abs(a["size"] - size), a["id"]))
    return winner, "body_only"
