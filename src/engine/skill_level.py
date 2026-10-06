# 用途：L1 技能缺口。G = Σ(該技能的 axis_relevance[軸] × max(0, 目標球員該軸 − 使用者該軸))，
# D 軸(運動能力)不算——身體條件學不來,不該被列成「要練的技能」。
# 可手動調整的變數：無——這裡只是加權差距的通用算法。真正決定結果的是
# data/zh/技能.json 每個技能的 axis_relevance 數值,不是這支檔案。

"""L1 skill gap G: how far a template player's style sits above the user's,
weighted by how much each skill targets each axis.

Pure functions only. See 2026-10 training-plan redesign (SPEC.md §4 G_i was
previously a self-assessed current level; it is now derived from axis gaps).
"""

TRAINABLE_AXES = ("A", "B1", "B2", "C1", "C2")


def skill_gap(axis_relevance, user_coords, target_coords):
    """G = Σ over trainable axes of axis_relevance[axis] × max(0, target − user).

    axis_relevance: {"A"..."D": 0-1} for one skill (data/zh/技能.json).
    user_coords / target_coords: {"A"..."D": 0-100}.

    A skill whose target is at or below the user on every trainable axis
    returns 0 -- there's nothing to close. The D axis is ignored entirely.
    """
    return sum(
        axis_relevance[axis] * max(0.0, target_coords[axis] - user_coords[axis])
        for axis in TRAINABLE_AXES
    )
