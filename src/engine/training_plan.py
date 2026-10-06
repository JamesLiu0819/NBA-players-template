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
from engine.priority import rank_priorities
from engine.skill_level import TRAINABLE_AXES, skill_gap

LEVEL_ENTRY = "entry"
LEVEL_ADVANCED = "advanced"
LEVEL_MASTERY = "mastery"

DIFFICULTY_ENTRY_BELOW = 40  # 暫定
DIFFICULTY_MASTERY_ABOVE = 70  # 暫定


def skill_difficulty_level(axis_score):
    """Map the user's 0-100 score on a skill's dominant axis to a level."""
    if axis_score < DIFFICULTY_ENTRY_BELOW:
        return LEVEL_ENTRY
    if axis_score > DIFFICULTY_MASTERY_ABOVE:
        return LEVEL_MASTERY
    return LEVEL_ADVANCED


def build_training_plan(skills, env_weights, user_coords, target_coords, top_n=5):
    """Rank skills by P = G × E ÷ C and return the top_n with G > 0.

    skills: list of skill dicts (id, axis_relevance, cost_C), e.g. from 技能.json.
    env_weights: {skill_id: E} for the chosen league environment.
    user_coords / target_coords: {"A"..."D": 0-100}.

    Each returned item has skill_id, G, E, C, P, dominant_axis and level.
    Returns an empty list when no skill has a positive gap -- the caller shows
    the "already ahead on these" message in that case.
    """
    items = []
    for skill in skills:
        g = skill_gap(skill["axis_relevance"], user_coords, target_coords)
        if g <= 0:
            continue
        if skill["id"] not in env_weights:
            raise ValueError(f"env weights missing skill: {skill['id']}")
        dominant_axis = skill_dominant_axis(skill["axis_relevance"])
        items.append({
            "skill_id": skill["id"],
            "G": g,
            "E": env_weights[skill["id"]],
            "C": skill["cost_C"],
            "dominant_axis": dominant_axis,
            "user_axis_score": user_coords[dominant_axis],
        })

    ranked = rank_priorities(items)[:top_n]
    for item in ranked:
        item["level"] = skill_difficulty_level(item["user_axis_score"])
    return ranked


def representative_skill_by_axis(skills):
    """For each trainable axis, the skill that leans on it most.

    Among skills whose dominant axis is that axis, pick the one with the
    highest weight there; ties break on skill id so the result is stable.
    Returns {axis: skill_id}. D is never trainable, so it is not included.
    """
    result = {}
    for axis in TRAINABLE_AXES:
        candidates = [s for s in skills if skill_dominant_axis(s["axis_relevance"]) == axis]
        if not candidates:
            candidates = list(skills)
        best_weight = max(s["axis_relevance"][axis] for s in candidates)
        result[axis] = min(s["id"] for s in candidates if s["axis_relevance"][axis] == best_weight)
    return result
