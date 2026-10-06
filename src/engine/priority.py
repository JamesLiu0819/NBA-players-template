# 用途：L4 訓練優先序。P = G × E ÷ C,排序後由高到低。
# 可手動調整的變數：無——公式本身不含校準數字。G 來自 skill_level.skill_gap,
# E 來自 data/env_weights.json(所選聯賽環境的倍率),C 來自 data/zh/技能.json 的 cost_C。
# R(自然位置相關性)不再乘進來：G 已經用 axis_relevance 加權過,再乘會重複計算
# (2026-10 討論)。

"""L4 training priority: P = (G × E) / C, sorted descending.

Pure functions only.
"""


def compute_priority(g, e, c):
    """P = G × E ÷ C. Raises ValueError if cost C is non-positive."""
    if c <= 0:
        raise ValueError(f"cost C must be positive, got {c}")
    return (g * e) / c


def rank_priorities(items):
    """Attach P to each item and sort descending by P.

    items: list of {"skill_id", "G", "E", "C", ...}.
    Ties break on ascending skill_id so the order is deterministic.
    Returns new dicts; inputs are not mutated.
    """
    ranked = [
        {**item, "P": compute_priority(item["G"], item["E"], item["C"])}
        for item in items
    ]
    ranked.sort(key=lambda item: (-item["P"], item["skill_id"]))
    return ranked
