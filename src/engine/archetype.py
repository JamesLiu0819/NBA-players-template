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
# 真正決定「後衛 vs 中鋒」觀感的主因;實測用現有 150 位球員資料算過,身高、
# 體重個別的百分位對現有 12 個原型的區隔力都很乾淨,取平均比算 BMI 更適合這個
# 用途),跟 A/B/C/D 一樣是 0-100 尺度,所以直接併入同一個歐氏距離,不用額外
# 正規化。size 是選填參數,沒傳或原型缺 size 欄位就完全退化成原本的純四軸距離,
# 舊呼叫端跟舊測試都不用改。
# classify_archetype_by_majority 的計票也在同一次討論改成距離加權：原本不管
# 名次一律 1 票,會出現「前 2 名最像的球員都同意 A 原型,但後 3 名更遠的球員湊
# 3 票投給 B 原型,B 就贏」的情況——跟畫面上顯示最像的球員直接矛盾。改成第 1
# 近的球員權重 top_n、第 2 近 top_n-1,以此類推,離使用者越近的球員意見越重,
# 平票時的 tie-break 邏輯(選最近球員的原型)不變。

"""L3-adjacent matching layer: nearest-neighbor archetype classification.

Pure functions only.
"""

import math

AXES = ("A", "B", "C", "D")
ARCHETYPE_MAJORITY_TOP_N = 5
SIZE_AXIS_WEIGHT = 1.0


def classify_archetype(coordinates, archetypes, size=None):
    """Return the archetype (from archetypes) whose coordinates are
    closest to the given coordinates (Euclidean distance over A/B/C/D).

    archetypes: list of dicts, each with at least "coordinates": {"A".."D"}.
        All other fields on the winning archetype pass through unchanged.
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


def _player_size(player):
    """Average of a player's height/weight percentiles (see module header),
    or None if the player has no body data -- classify_archetype then falls
    back to the plain style-only distance for that player."""
    body = player.get("body") or {}
    if "height_cm" not in body or "weight_kg" not in body:
        return None
    return (body["height_cm"] + body["weight_kg"]) / 2


def classify_archetype_by_majority(ranked_players, archetypes, top_n=ARCHETYPE_MAJORITY_TOP_N):
    """Classify by distance-weighted vote: classify each of the top_n closest
    ranked players (already sorted by distance to the user, ascending) into
    its own nearest archetype via classify_archetype (size-aware when the
    player has body data -- see module header), then return whichever
    archetype the closer players favor most.

    ranked_players: list of dicts, each with at least "coordinates": {"A".."D"},
        and optionally "body": {"height_cm", "weight_kg", ...} (percentiles,
        e.g. from body_fit.percentile_normalize_body).
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
        classify_archetype(player["coordinates"], archetypes, size=_player_size(player))
        for player in ranked_players[:top_n]
    ]

    weights = {}
    for rank, archetype in enumerate(player_archetypes):
        weight = top_n - rank
        weights[archetype["id"]] = weights.get(archetype["id"], 0) + weight
    max_weight = max(weights.values())
    tied_ids = {archetype_id for archetype_id, weight in weights.items() if weight == max_weight}

    return next(archetype for archetype in player_archetypes if archetype["id"] in tied_ids)
