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

"""L3-adjacent matching layer: nearest-neighbor archetype classification.

Pure functions only.
"""

import math

AXES = ("A", "B", "C", "D")
ARCHETYPE_MAJORITY_TOP_N = 5


def classify_archetype(coordinates, archetypes):
    """Return the archetype (from archetypes) whose coordinates are
    closest to the given coordinates (Euclidean distance over A/B/C/D).

    archetypes: list of dicts, each with at least "coordinates": {"A".."D"}.
        All other fields on the winning archetype pass through unchanged.

    Raises ValueError if archetypes is empty.
    """
    if not archetypes:
        raise ValueError("archetypes must not be empty; classification is undefined")

    def distance(archetype):
        return math.sqrt(
            sum((archetype["coordinates"][axis] - coordinates[axis]) ** 2 for axis in AXES)
        )

    return min(archetypes, key=distance)


def classify_archetype_by_majority(ranked_players, archetypes, top_n=ARCHETYPE_MAJORITY_TOP_N):
    """Classify by majority vote: classify each of the top_n closest ranked
    players (already sorted by distance to the user, ascending) into its own
    nearest archetype via classify_archetype, then return whichever
    archetype most of them share.

    ranked_players: list of dicts, each with at least "coordinates": {"A".."D"}.
        Ties are broken by the archetype of the single closest player among
        the tied archetypes, so the result stays deterministic.

    Raises ValueError if ranked_players is empty.
    """
    if not ranked_players:
        raise ValueError("ranked_players must not be empty; classification is undefined")

    player_archetypes = [
        classify_archetype(player["coordinates"], archetypes) for player in ranked_players[:top_n]
    ]

    counts = {}
    for archetype in player_archetypes:
        counts[archetype["id"]] = counts.get(archetype["id"], 0) + 1
    max_count = max(counts.values())
    tied_ids = {archetype_id for archetype_id, count in counts.items() if count == max_count}

    return next(archetype for archetype in player_archetypes if archetype["id"] in tied_ids)
