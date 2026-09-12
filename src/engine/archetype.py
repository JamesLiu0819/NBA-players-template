# 用途：把使用者的四軸座標分類到最接近的球場定位原型(data/archetypes.json)
# ——用最近鄰(Euclidean distance)比對,跟 player_matching.py 找最像球員的
# 邏輯是同一套精神,只是比對對象換成原型錨點。給結果頁的「一句話球探報告」跟
# 原型標籤用(2026-09-13 討論:球員名字不夠好記,原型標籤才是可以分享出去的
# 身份代號)。
# 可手動調整的變數：無——這裡是通用最近鄰計算,不含需要人工校準的參數。原型
# 本身的數量/座標/文案在 data/archetypes.json 裡調整,不在這支檔案。

"""L3-adjacent matching layer: nearest-neighbor archetype classification.

Pure functions only.
"""

import math

AXES = ("A", "B", "C", "D")


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
