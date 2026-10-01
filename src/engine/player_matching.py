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
# 整就直接改這個數字)、_DISTANCE_STAR_THRESHOLDS(貼合度星級的距離門檻——
# 2026-09-11 實測校準過兩次,都是整數星級(1-5)。2026-10 改成半顆星精度
# (1/1.5/2/.../5,9 個級距、8 個門檻),因為使用者想看到「4.5 顆星」這種更
# 細的差異,不想被整數星級抹平。校準方法沿用同一套(四軸座標＝4 個獨立 1-5
# 隨機值取平均;身材數值沿用網站 randomBodyValues() 的推導邏輯,不是獨立均勻
# 抽樣),樣本數從 20 次(200 筆)加倍成 40 次(400 筆)——門檻數量從 4 個變
# 8 個,樣本數跟著加倍才能維持「每個門檻間距大約對應多少筆樣本」跟原本差不多
# 的統計穩定度。取第 44/89/133/178/222/267/311/356 名的距離(400 筆由小到大
# 排序,對應 i*400/9,i=1..8)當門檻,四捨五入成 49/55/60/65/69/72/79/83。
# 之後如果覺得星等分佈不合理,可以重跑同樣的抽樣流程重新校準。

"""L3 matching layer: nearest-neighbor player template matching.

Pure functions only. See SPEC.md §2 (L3), §3.1 (dominant-diff-axis argmax),
and docs/superpowers/specs/2026-09-10-player-template-matching-design.md.
"""

import math

from engine.body_fit import body_distance

AXES = ("A", "B1", "B2", "C1", "C2", "D")
STYLE_AXES_EXCLUDING_D = ("A", "B1", "B2", "C1", "C2")

D_AXIS_WEIGHT = 1.5

_DISTANCE_STAR_THRESHOLDS = (
    (49, 5),
    (55, 4.5),
    (60, 4),
    (65, 3.5),
    (69, 3),
    (72, 2.5),
    (79, 2),
    (83, 1.5),
)


def fit_stars_for_distance(distance):
    """Bucket a distance into a 1-5 star fit rating (half-star increments)
    using fixed thresholds."""
    for threshold, stars in _DISTANCE_STAR_THRESHOLDS:
        if distance <= threshold:
            return stars
    return 1


def rank_similar_players(user_coordinates, players, k=10):
    """Rank players by distance to user_coordinates across all six axes.

    user_coordinates: {axis: 0-100 for axis in AXES}.
    players: list of dicts, each with at least "coordinates": {axis: 0-100 for axis in AXES}.
        All other fields on each player dict pass through unchanged.

    Returns the k nearest players (or fewer, if len(players) < k) sorted by
    ascending distance. Each result dict is the original player dict plus:
        distance: float, unweighted Euclidean distance over all six axes
        diff: {axis: player[axis] - user_coordinates[axis] for axis in AXES} (signed)
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
    fields into the distance alongside the six style axes -- used only
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
        diff: {axis: player[axis] - user_coordinates[axis] for axis in AXES} (signed,
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
    """Return the axis (one of AXES) with the highest relevance weight for a skill."""
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


def _style_distance_excluding_d(diff):
    """Euclidean distance over every axis except D (A/B1/B2/C1/C2) of a diff
    dict -- the axes SPEC.md treats as learnable; D is deliberately excluded,
    since the functions that use this are specifically about "closeness
    ignoring athleticism" (renamed from _abc_distance in the 2026-10 six-axis
    split -- same role, just over 5 style axes instead of 3)."""
    return math.sqrt(sum(diff[axis] ** 2 for axis in STYLE_AXES_EXCLUDING_D))


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

    Candidates must have their overall dominant_diff_axis land on a style
    axis (A/B1/B2/C1/C2, i.e. not D) with diff[axis] > 0 -- a genuine skill
    lead, not just the "least negative" axis when the user actually leads on
    every axis (see rank_similar_players' documented edge case). Among
    candidates, picks whichever has the closest D axis to the user's.

    Returns None if no player in the given pool qualifies.
    """
    ranked = rank_similar_players(user_coordinates, players, k=len(players))
    candidates = [
        p for p in ranked
        if p["dominant_diff_axis"] in STYLE_AXES_EXCLUDING_D and p["diff"][p["dominant_diff_axis"]] > 0
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: abs(p["diff"]["D"]))


def find_skill_fit_template(user_coordinates, players):
    """Find the "skill best-fit" deep template (技能最貼合): the player
    closest to the user on every style axis (A/B1/B2/C1/C2), ignoring D
    entirely -- who plays the most like you already, regardless of
    athleticism.

    Returns None if players is empty.
    """
    ranked = rank_similar_players(user_coordinates, players, k=len(players))
    if not ranked:
        return None
    return min(ranked, key=lambda p: _style_distance_excluding_d(p["diff"]))


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
