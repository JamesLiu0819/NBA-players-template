# 用途：連接 L2 跟 L4，算出 R_i(某項技能跟使用者自然位置座標的相關性,0-1)。
# 可手動調整的變數：無——這裡只是加權平均的通用算法。真正決定 R_i 結果的是
# data/skills.json 裡每個技能的 axis_relevance 數值,不是這支檔案。

"""L2->L4 bridge: R_i, relevance of a skill to the user's natural position.

Pure functions only. See SPEC.md §4 (R_i = L2 coordinates x axis_relevance).
"""

AXES = ("A", "B", "C", "D")


def compute_relevance(axis_coordinates, axis_relevance):
    """R_i = weighted average of axis coordinates (0-1 scale), weighted by
    how relevant each axis is to the skill (skills.json axis_relevance).

    axis_coordinates: {"A"..."D": 0-100} from score_axis_coordinates.
    axis_relevance: {"A"..."D": 0-1} fixed per skill in skills.json.

    Raises ValueError if all relevance weights are zero (undefined average).
    """
    weight_total = sum(axis_relevance[axis] for axis in AXES)
    if weight_total == 0:
        raise ValueError("axis_relevance weights sum to zero; relevance is undefined")

    weighted_sum = sum(
        axis_relevance[axis] * (axis_coordinates[axis] / 100) for axis in AXES
    )

    relevance = weighted_sum / weight_total
    return min(1.0, max(0.0, relevance))
