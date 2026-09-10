# 用途：L3 匹配層,把使用者的四軸座標拿去跟球員種子資料算最近鄰,並提供「差異
# 軸是否剛好對到某個技能」的判斷。rank_similar_players 是純四軸距離,供 3 位
# 深度模板挑選邏輯使用——技能最貼合(find_skill_fit_template)、身體最貼合
# (find_body_fit_template)、天花板方向(find_ceiling_template)——以及反面對照
# (find_anti_template)。天花板方向跟反面對照是一體兩面：都是「A/B/C 軸接近但
# D 軸差距最大」的球員,差別只在核心優勢可不可複製(learnability_flag)。
# rank_similar_players_by_style_and_body 是另一支「四軸+身材」的混合距離函數,
# 只給 10 人對照表用,刻意不影響上面 4 個深度模板/反面對照函數(它們的設計就是
# 要跟身材無關,或刻意找身材差異最大的球員,見 2026-09-11 body-aware matching
# 討論)。
# 可手動調整的變數：_DISTANCE_STAR_THRESHOLDS(貼合度星級的距離門檻,目前是依
# 常理暫定的 20/40/60/80,等有真實球員資料庫、知道實際距離分佈後應該重新校準;
# 這組門檻兩個排序函數共用,沒有另外針對加了身材維度後更大的距離空間校準)。

"""L3 matching layer: nearest-neighbor player template matching.

Pure functions only. See SPEC.md §2 (L3), §3.1 (dominant-diff-axis argmax),
and docs/superpowers/specs/2026-09-10-player-template-matching-design.md.
"""

import math

from engine.body_fit import body_distance

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


def rank_similar_players_by_style_and_body(user_coordinates, user_body, players, field_ranges, k=10):
    """Like rank_similar_players, but folds normalized body-measurement
    fields into the distance alongside the A/B/C/D style axes -- used only
    for the 10-player comparison table, so a user doesn't see e.g. a tall
    big and a small agile guard both offered as "your template" just
    because their style axes happen to be close (2026-09-11 body-aware
    matching fix).

    user_body: {field: value}, e.g. from body_fit.collect_body_measurements.
        If empty (user skipped the body questions), every player's common
        field set with user_body is empty too, so this degrades to a plain
        style-only distance -- the same numbers rank_similar_players would
        produce.
    field_ranges: {field: (min, max)}, passed straight through to
        body_distance for normalization.
    players: list of dicts, each with "coordinates" and a "body" dict.

    Returns the k nearest players sorted by ascending combined distance.
    Each result dict is the original player dict plus:
        distance: float, combined style+body distance
        diff: {"A"..."D": player[axis] - user_coordinates[axis]} (signed,
            style-only -- growth-recommendation text is keyed off this)
        dominant_diff_axis: axis of the signed max of diff (style-only)
        fit_stars: int 1-5
    """
    ranked = []
    for player in players:
        diff = {axis: player["coordinates"][axis] - user_coordinates[axis] for axis in AXES}
        squared_terms = [diff[axis] ** 2 for axis in AXES]

        common_body_fields = set(user_body) & set(player.get("body", {}))
        for field in common_body_fields:
            low, high = field_ranges[field]
            user_norm = (user_body[field] - low) / (high - low) * 100
            player_norm = (player["body"][field] - low) / (high - low) * 100
            squared_terms.append((player_norm - user_norm) ** 2)

        distance = math.sqrt(sum(squared_terms))
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


def _abc_distance(diff):
    """Euclidean distance over just the A/B/C axes of a diff dict -- the
    axes SPEC.md treats as learnable; D is deliberately excluded, since the
    functions that use this are specifically about "closeness ignoring
    athleticism."""
    return math.sqrt(sum(diff[axis] ** 2 for axis in ("A", "B", "C")))


def find_anti_template(user_coordinates, players):
    """Find the single best "anti-template" (SPEC.md §3.1): a player whose
    A/B/C axes are closest to the user but whose D axis is the dominant
    gap, AND whose core strength is flagged as non-replicable
    (learnability_flag == "low") -- someone who looks like you but succeeds
    on something you don't have and can't train.

    Returns None if no player in the given pool qualifies. This is an
    honest "not found", not relaxed to a looser learnability match -- see
    the 2026-09-10 anti-template scoping discussion.
    """
    ranked = rank_similar_players(user_coordinates, players, k=len(players))
    candidates = [
        p for p in ranked
        if p["dominant_diff_axis"] == "D" and p.get("learnability_flag") == "low"
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: _abc_distance(p["diff"]))


def find_ceiling_template(user_coordinates, players):
    """Find the "ceiling direction" deep template (天花板方向): the mirror
    image of find_anti_template. Same shape -- A/B/C close, D the dominant
    gap -- but here the advantage IS flagged as replicable
    (learnability_flag in {"medium", "high"}), i.e. this is a realistic,
    trainable direction to grow toward rather than an unreachable outlier.

    Returns None if no player in the given pool qualifies.
    """
    ranked = rank_similar_players(user_coordinates, players, k=len(players))
    candidates = [
        p for p in ranked
        if p["dominant_diff_axis"] == "D" and p.get("learnability_flag") in ("medium", "high")
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: _abc_distance(p["diff"]))


def find_skill_fit_template(user_coordinates, players):
    """Find the "skill best-fit" deep template (技能最貼合): the player
    closest to the user on just the A/B/C axes, ignoring D entirely --
    who plays the most like you already, regardless of athleticism.

    Returns None if players is empty.
    """
    ranked = rank_similar_players(user_coordinates, players, k=len(players))
    if not ranked:
        return None
    return min(ranked, key=lambda p: _abc_distance(p["diff"]))


def find_body_fit_template(user_body, players, field_ranges):
    """Find the "body best-fit" deep template (身體最貼合): the player whose
    body measurements are closest to the user's, per body_distance.

    user_body: {field: value}, e.g. from body_fit.collect_body_measurements.
    players: list of dicts, each with a "body": {field: value} entry.
    field_ranges: {field: (min, max)}, passed straight through to
        body_distance for normalization.

    Returns None if players is empty. Assumes every player's "body" dict
    shares at least one field with user_body (true for all of today's seed
    data -- see data/players.json and tests/engine/test_players_data.py).
    """
    if not players:
        return None
    return min(players, key=lambda p: body_distance(user_body, p["body"], field_ranges))
