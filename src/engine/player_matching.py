# 用途：L3 匹配層,把使用者的四軸座標拿去跟球員種子資料算最近鄰,並提供「差異
# 軸是否剛好對到某個技能」的判斷。rank_similar_players 是純四軸距離,供 3 位
# 深度模板挑選邏輯使用——技能最貼合(find_skill_fit_template)、身體最貼合
# (find_body_fit_template)、天花板(find_ceiling_template)。
# 天花板的定義是「D 軸(運動能力)接近,但主導差距在 A/B/C 某個技能軸」——找一個
# 跟你身體條件差不多、但技術更成熟的球員,代表一個真正練得到的目標。原本的定義
# 是反過來(A/B/C 接近、D 軸差距最大),但那樣找到的其實是「天賦跟你不一樣的
# 人」,不是天花板;連帶反面對照(find_anti_template)也一起移除了,因為它用的
# 是同一套「D 軸差距最大」邏輯,一樣沒有意義(2026-09-11 重新設計討論)。
# rank_similar_players_by_style_and_body 是另一支「四軸+身材」的混合距離函數,
# 給 10 人對照表跟「整體模板」用,刻意不影響上面 3 個深度模板函數(它們的設計
# 就是要跟身材無關,見 2026-09-11 body-aware matching 討論)。這支函數裡 D 軸
# (運動能力)的平方項會乘上 D_AXIS_WEIGHT——身體條件的差距被認為比技巧差距
# 影響大更多,所以刻意讓 D 軸差距在距離裡佔比更重,不是四軸平權(2026-09-11
# 討論,倍率先抓 2、後來調成 1.5,之後看效果再調)。技能最貼合/天花板刻意不受
# 影響,因為它們本來就不是「四軸平權距離」的結構。
# 可手動調整的變數：D_AXIS_WEIGHT(D 軸平方項的權重倍率,目前是 1.5,之後要調
# 整就直接改這個數字)、_DISTANCE_STAR_THRESHOLDS(貼合度星級的距離門檻,目前
# 是 15/35/55/75,兩個排序函數共用,沒有另外針對加了身材維度或 D 軸加權後更大
# 的距離空間分開校準)。

"""L3 matching layer: nearest-neighbor player template matching.

Pure functions only. See SPEC.md §2 (L3), §3.1 (dominant-diff-axis argmax),
and docs/superpowers/specs/2026-09-10-player-template-matching-design.md.
"""

import math

from engine.body_fit import body_distance

AXES = ("A", "B", "C", "D")

D_AXIS_WEIGHT = 1.5

_DISTANCE_STAR_THRESHOLDS = (
    (15, 5),
    (35, 4),
    (55, 3),
    (75, 2),
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
        distance: float, combined style+body distance (D axis weighted
            D_AXIS_WEIGHT times more heavily than A/B/C/body fields)
        diff: {"A"..."D": player[axis] - user_coordinates[axis]} (signed,
            style-only -- growth-recommendation text is keyed off this)
        dominant_diff_axis: axis of the signed max of diff (style-only)
        fit_stars: int 1-5
    """
    ranked = []
    for player in players:
        diff = {axis: player["coordinates"][axis] - user_coordinates[axis] for axis in AXES}
        squared_terms = [
            (diff[axis] ** 2) * (D_AXIS_WEIGHT if axis == "D" else 1)
            for axis in AXES
        ]

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


def representative_skill_id_for_axis(axis, skills_by_id):
    """Return the skill_id most associated with the given axis (highest
    axis_relevance[axis] across every skill in skills_by_id) -- a fallback
    for when a template player's own signature_skill_id doesn't target the
    differentiation axis (matching_skill_id returns None), so the growth
    recommendation can still name a concrete, practicable action instead of
    a generic "practice this axis" sentence.

    Ties break on ascending skill_id for determinism. skills_by_id must be
    non-empty.
    """
    return min(
        skills_by_id,
        key=lambda skill_id: (-skills_by_id[skill_id]["axis_relevance"][axis], skill_id),
    )


def _abc_distance(diff):
    """Euclidean distance over just the A/B/C axes of a diff dict -- the
    axes SPEC.md treats as learnable; D is deliberately excluded, since the
    functions that use this are specifically about "closeness ignoring
    athleticism."""
    return math.sqrt(sum(diff[axis] ** 2 for axis in ("A", "B", "C")))


def find_ceiling_template(user_coordinates, players):
    """Find the "ceiling" deep template (天花板): a player with roughly the
    user's own athletic tools (D axis close) whose game is far more
    developed -- the dominant gap is a skill axis (A/B/C), not athleticism.
    This is meant to be a genuinely achievable target: what you could
    become if you maxed out your technique with the tools you already have
    (2026-09-11 redesign -- the old definition, "A/B/C close, D the
    dominant gap", just returned someone with different genetics, which
    isn't a real ceiling since athletic ability isn't something you train
    into. That old shape is also why find_anti_template was removed
    entirely, rather than kept as a separate function: it was the same "D
    axis is the biggest gap" logic with no real use once ceiling stopped
    meaning that).

    Candidates must have their overall dominant_diff_axis land on A, B, or
    C with diff[axis] > 0 -- a genuine skill lead, not just the "least
    negative" axis when the user actually leads on every axis (see
    rank_similar_players' documented edge case). Among candidates, picks
    whichever has the closest D axis to the user's.

    Returns None if no player in the given pool qualifies.
    """
    ranked = rank_similar_players(user_coordinates, players, k=len(players))
    candidates = [
        p for p in ranked
        if p["dominant_diff_axis"] in ("A", "B", "C") and p["diff"][p["dominant_diff_axis"]] > 0
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: abs(p["diff"]["D"]))


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
