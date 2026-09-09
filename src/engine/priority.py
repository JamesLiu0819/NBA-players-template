# 用途：L4 處方層，算出優先序分數 P_i,以及排序背後是哪個因子(G/E/R/C)在主導。
# 可手動調整的變數：explain_dominant_factor 內的 eps(目前 1e-6)只是防止除以零的
# 極小值,不是給人調的參數,不要為了改結果去動它。_FACTORS 是固定的四個因子名稱,
# 不是可調變數。這支檔案沒有需要人工校準的數字——真正的校準值(G/E/R/C 各自的來源)
# 都在別的檔案(questions.json、skills.json、環境權重)。

"""L4 prescription layer: priority score P_i and its factor breakdown.

Pure functions only. See SPEC.md §4:
    P_i = (G_i x E_i x R_i) / C_i
"""

_FACTORS = ("G", "E", "R", "C")


def compute_priority(g, e, r, c):
    """P_i = (G x E x R) / C. Raises ValueError if cost C is non-positive."""
    if c <= 0:
        raise ValueError(f"cost C must be positive, got {c}")
    return (g * e * r) / c


def rank_priorities(items):
    """Attach P to each item and sort descending by priority.

    items: list of {"skill_id", "G", "E", "R", "C", ...}.
    Returns new dicts (inputs are not mutated), highest priority first.
    """
    ranked = [
        {**item, "P": compute_priority(item["G"], item["E"], item["R"], item["C"])}
        for item in items
    ]
    ranked.sort(key=lambda item: item["P"], reverse=True)
    return ranked


def explain_dominant_factor(higher, lower):
    """Explain why `higher` outranks `lower` in priority (SPEC.md §4 point 2).

    Because P_i is a pure product/quotient, the ratio P_higher / P_lower
    factors exactly into four per-factor ratios:

        P_h / P_l = (G_h/G_l) * (E_h/E_l) * (R_h/R_l) * (C_l/C_h)

    (cost is inverted because a *lower* cost on the higher-ranked item is
    what favors it). The factor with the largest ratio is the one that
    "pulled the ranking apart" the most.

    Raises ValueError if `higher` does not actually outrank `lower`.
    """
    p_higher = compute_priority(higher["G"], higher["E"], higher["R"], higher["C"])
    p_lower = compute_priority(lower["G"], lower["E"], lower["R"], lower["C"])
    if p_higher <= p_lower:
        raise ValueError(
            f"'higher' item (P={p_higher}) does not outrank 'lower' item (P={p_lower})"
        )

    eps = 1e-6
    ratios = {
        "G": higher["G"] / max(lower["G"], eps),
        "E": higher["E"] / max(lower["E"], eps),
        "R": higher["R"] / max(lower["R"], eps),
        "C": lower["C"] / max(higher["C"], eps),
    }

    dominant_factor = max(_FACTORS, key=lambda factor: ratios[factor])

    return {
        "factor": dominant_factor,
        "ratio": ratios[dominant_factor],
        "priority_ratio": p_higher / p_lower,
    }
