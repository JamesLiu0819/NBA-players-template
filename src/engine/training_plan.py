# 用途：L4 訓練計劃。對一位目標球員、一個聯賽環境,挑出 P 最高的前幾項技能,
# 並判定每項該練的難度(entry/advanced/mastery)。
# 可手動調整的變數(兩個門檻都是暫定值,還沒有用真實資料校準過):
#   DIFFICULTY_ENTRY_BELOW：使用者在該軸的分數低於這個數字 → entry(入門)。
#   DIFFICULTY_MASTERY_ABOVE：分數高於這個數字 → mastery(精熟);介於兩者之間 → advanced。
# 要改難度分界就改這兩個常數,不用改判定邏輯。

"""L4 training plan: top-N skills by priority, each with a difficulty level.

Pure functions only.
"""

from engine.player_matching import skill_dominant_axis
from engine.priority import compute_priority, rank_priorities
from engine.skill_level import skill_gap

LEVEL_ENTRY = "entry"
LEVEL_ADVANCED = "advanced"
LEVEL_MASTERY = "mastery"

DIFFICULTY_ENTRY_BELOW = 40  # 暫定
DIFFICULTY_MASTERY_ABOVE = 70  # 暫定

TRAINING_PLAN_RELATIVE_THRESHOLD = 0.25  # 暫定


def skill_difficulty_level(axis_score):
    """Map the user's 0-100 score on a skill's dominant axis to a level."""
    if axis_score < DIFFICULTY_ENTRY_BELOW:
        return LEVEL_ENTRY
    if axis_score > DIFFICULTY_MASTERY_ABOVE:
        return LEVEL_MASTERY
    return LEVEL_ADVANCED


def _priority_item(skill, env_weights, user_coords, target_coords, is_signature):
    if skill["id"] not in env_weights:
        raise ValueError(f"env weights missing skill: {skill['id']}")
    g = skill_gap(skill["axis_relevance"], user_coords, target_coords)
    dominant_axis = skill_dominant_axis(skill["axis_relevance"])
    return {
        "skill_id": skill["id"],
        "G": g,
        "E": env_weights[skill["id"]],
        "C": skill["cost_C"],
        "dominant_axis": dominant_axis,
        "user_axis_score": user_coords[dominant_axis],
        "is_signature": is_signature,
    }


def build_training_plan(skills, env_weights, user_coords, target_coords, signature_skill_id, top_n=5):
    """Rank skills by P = G x E / C, with the target player's signature
    skill forced into slot 1 regardless of its own gap, cost, or the
    relative threshold below -- see SPEC.md / the 2026-10 design doc item
    2/3/4: a training plan must never be empty (the signature skill is
    always a valid "something to work on"), and switching target players
    must always change at least the first item shown.

    skills: list of skill dicts (id, axis_relevance, cost_C), e.g. from 技能.json.
    env_weights: {skill_id: E} for the chosen league environment. Must contain
        an entry for EVERY skill in `skills`, signature included.
    user_coords / target_coords: {"A"..."D": 0-100}.
    signature_skill_id: the target player's signature_skill_id. Must be the
        id of one of the skills in `skills`.
    top_n: total item cap INCLUDING the signature skill (so at most
        top_n - 1 other items are added).

    Returns a list of 1 to top_n items (never empty), each with skill_id, G,
    E, C, P, dominant_axis, level, and is_signature. Item 0 is always the
    signature skill. The rest are sorted by P descending, excluding any
    non-signature skill whose own gap is <= 0, and further excluding any
    whose P is below TRAINING_PLAN_RELATIVE_THRESHOLD of the highest P
    among the OTHER (non-signature) items.

    Raises ValueError if signature_skill_id doesn't match any skill in
    `skills`, or if env_weights is missing an entry for any skill this
    function needs a weight for (signature included).
    """
    skills_by_id = {skill["id"]: skill for skill in skills}
    if signature_skill_id not in skills_by_id:
        raise ValueError(f"unknown signature_skill_id: {signature_skill_id}")

    signature_item = _priority_item(
        skills_by_id[signature_skill_id], env_weights, user_coords, target_coords, is_signature=True
    )
    signature_item["P"] = compute_priority(signature_item["G"], signature_item["E"], signature_item["C"])
    signature_item["level"] = skill_difficulty_level(signature_item["user_axis_score"])

    other_items = []
    for skill in skills:
        if skill["id"] == signature_skill_id:
            continue
        item = _priority_item(skill, env_weights, user_coords, target_coords, is_signature=False)
        if item["G"] <= 0:
            continue
        other_items.append(item)

    ranked_others = rank_priorities(other_items)
    if ranked_others:
        threshold = ranked_others[0]["P"] * TRAINING_PLAN_RELATIVE_THRESHOLD
        ranked_others = [item for item in ranked_others if item["P"] >= threshold]
    ranked_others = ranked_others[: max(0, top_n - 1)]

    plan = [signature_item] + ranked_others
    for item in plan:
        item["level"] = skill_difficulty_level(item["user_axis_score"])
    return plan
