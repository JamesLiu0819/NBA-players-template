# 用途：把使用者分類到最接近的球場定位原型(data/archetypes.json)。
# classify_archetype 是最基本的最近鄰(Euclidean distance)比對,跟
# player_matching.py 找最像球員的邏輯是同一套精神,只是比對對象換成原型
# 錨點。classify_archetype_by_majority 是結果頁實際使用的版本：不直接拿
# 使用者座標比對原型,而是把 10 人對照表裡前 N 位最相似的「真人球員」各自
# 分類到最近的原型,再取多數決——理由是使用者座標 vs 原型錨點、使用者 vs
# 真人球員資料庫這兩套比對邏輯,原本各自獨立計算,可能導致原型標籤跟結果頁
# 顯示的球員對不上(例如標籤說背框中鋒,顯示的球員卻是控球後衛);改成多數決
# 後,原型一定是從畫面上實際顯示的球員群裡投票出來的,保證兩者一致
# (2026-09-13 討論)。
# 可手動調整的變數：ARCHETYPE_MAJORITY_TOP_N(多數決要看前幾位最相似球員,
# 目前 5——10 人對照表的前一半)。原型本身的數量/座標/文案在
# data/archetypes.json 裡調整,不在這支檔案。
#
# size 參數(2026-10 討論)：classify_archetype 原本純看 A/B/C/D 四軸,完全不看
# 身材,結果矮個子只要打法平均就會被分類到「全能鋒線」之類隱含高大身材的原型,
# 高個子打控球風格也會被分類到「控場指揮官」——原型名稱在使用者認知裡跟身材
# 綁在一起,但計算本身完全沒有身材這個維度。size 是身高百分位跟體重百分位的
# 平均(不是直接算 BMI——BMI=體重/身高^2 會把身高訊號本身抵銷掉,而身高才是
# 真正決定「後衛 vs 中鋒」觀感的主因),跟 A/B/C/D 一樣是 0-100 尺度,所以直接
# 併入同一個歐氏距離,不用額外正規化。size 是選填參數,沒傳或原型缺 size 欄位
# 就完全退化成原本的純四軸距離。
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
# 算好,呼叫端(server/app.py、scripts/run_player_match.py)要自己保留這個時機
# 差。archetypes.json 裡現有的 size 錨點數值(25-87)就是用這套「球員池內部
# 排名」校準出來的,不用跟著改。
# classify_archetype_by_majority 的計票也在同一次討論改成距離加權：原本不管
# 名次一律 1 票,會出現「前 2 名最像的球員都同意 A 原型,但後 3 名更遠的球員湊
# 3 票投給 B 原型,B 就贏」的情況——跟畫面上顯示最像的球員直接矛盾。改成第 1
# 近的球員權重 top_n、第 2 近 top_n-1,以此類推,離使用者越近的球員意見越重,
# 平票時的 tie-break 邏輯(選最近球員的原型)不變。

"""L3-adjacent matching layer: nearest-neighbor archetype classification.

Pure functions only.
"""

import math

AXES = ("A", "B1", "B2", "C1", "C2", "D")
ARCHETYPE_MAJORITY_TOP_N = 5
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
        distance alongside A/B/C/D, so archetypes whose real-world body
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
    up with player_sizes.get(player_id) and treat a miss as "no size data"
    (classify_archetype_by_majority already does this).
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


def classify_archetype_by_majority(ranked_players, archetypes, player_sizes=None, top_n=ARCHETYPE_MAJORITY_TOP_N):
    """Classify by distance-weighted vote: classify each of the top_n closest
    ranked players (already sorted by distance to the user, ascending) into
    its own nearest archetype via classify_archetype (size-aware when
    player_sizes has an entry for that player), then return whichever
    archetype the closer players favor most.

    ranked_players: list of dicts, each with at least "id" and
        "coordinates": {"A".."D"}.
    player_sizes: optional {player_id: size} from compute_player_sizes,
        computed over the full pool ranked_players was drawn from (not just
        this top_n slice). A player missing from player_sizes (or when
        player_sizes itself is None) falls back to the plain style-only
        distance for that player.
        Each of the top_n players' votes is weighted by its rank -- the
        closest player gets weight top_n, the next top_n-1, and so on --
        so a plurality among the closest players outweighs a larger count
        among more distant ones. Ties are broken by the archetype of the
        single closest player among the tied archetypes, so the result
        stays deterministic.

    Raises ValueError if ranked_players is empty.
    """
    if not ranked_players:
        raise ValueError("ranked_players must not be empty; classification is undefined")

    player_archetypes = [
        classify_archetype(
            player["coordinates"], archetypes,
            size=(player_sizes.get(player["id"]) if player_sizes else None),
        )
        for player in ranked_players[:top_n]
    ]

    weights = {}
    for rank, archetype in enumerate(player_archetypes):
        weight = top_n - rank
        weights[archetype["id"]] = weights.get(archetype["id"], 0) + weight
    max_weight = max(weights.values())
    tied_ids = {archetype_id for archetype_id, weight in weights.items() if weight == max_weight}

    return next(archetype for archetype in player_archetypes if archetype["id"] in tied_ids)
