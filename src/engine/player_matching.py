# 用途：L3 匹配層,把使用者的四軸座標拿去跟球員種子資料算最近鄰,並提供「差異
# 軸是否剛好對到某個技能」的判斷,供 scripts/run_player_match.py 產生 10 人對照表。
# 可手動調整的變數：_DISTANCE_STAR_THRESHOLDS(貼合度星級的距離門檻,目前是依
# 常理暫定的 20/40/60/80,等有真實球員資料庫、知道實際距離分佈後應該重新校準)。

"""L3 matching layer: nearest-neighbor player template matching.

Pure functions only. See SPEC.md §2 (L3), §3.1 (dominant-diff-axis argmax),
and docs/superpowers/specs/2026-09-10-player-template-matching-design.md.
"""

import math

AXES = ("A", "B", "C", "D")

_DISTANCE_STAR_THRESHOLDS = (
    (20, 5),
    (40, 4),
    (60, 3),
    (80, 2),
)


def fit_stars_for_distance(distance):
    """Bucket a distance into a 1-5 star fit rating using fixed thresholds."""
    for threshold, stars in _DISTANCE_STAR_THRESHOLDS:
        if distance <= threshold:
            return stars
    return 1


def rank_similar_players(user_coordinates, players, k=10):
    """Rank players by distance to user_coordinates in A/B/C/D space.

    user_coordinates: {"A"..."D": 0-100}.
    players: list of dicts, each with at least "coordinates": {"A"..."D": 0-100}.
        All other fields on each player dict pass through unchanged.

    Returns the k nearest players (or fewer, if len(players) < k) sorted by
    ascending distance. Each result dict is the original player dict plus:
        distance: float, unweighted Euclidean distance over A/B/C/D
        diff: {"A"..."D": player[axis] - user_coordinates[axis]} (signed)
        dominant_diff_axis: axis of the signed max of diff (see the design
            doc for the known edge case when the user leads on every axis)
        fit_stars: int 1-5
    """
    ranked = []
    for player in players:
        diff = {axis: player["coordinates"][axis] - user_coordinates[axis] for axis in AXES}
        distance = math.sqrt(sum(diff[axis] ** 2 for axis in AXES))
        dominant_diff_axis = max(AXES, key=lambda axis: diff[axis])
        ranked.append({
            **player,
            "distance": distance,
            "diff": diff,
            "dominant_diff_axis": dominant_diff_axis,
            "fit_stars": fit_stars_for_distance(distance),
        })
    ranked.sort(key=lambda item: item["distance"])
    return ranked[:k]


def skill_dominant_axis(axis_relevance):
    """Return the axis (A/B/C/D) with the highest relevance weight for a skill."""
    return max(AXES, key=lambda axis: axis_relevance[axis])


def matching_skill_id(dominant_diff_axis, signature_skill_id, skills_by_id):
    """Return signature_skill_id if that skill's own dominant axis equals
    dominant_diff_axis, else None (see design doc §3.4: a skill is only "the
    one thing worth learning" if it actually targets the axis where the
    template player exceeds the user the most).
    """
    if not signature_skill_id or signature_skill_id not in skills_by_id:
        return None
    skill = skills_by_id[signature_skill_id]
    if skill_dominant_axis(skill["axis_relevance"]) == dominant_diff_axis:
        return signature_skill_id
    return None
