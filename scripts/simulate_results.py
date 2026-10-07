#!/usr/bin/env python3
# 用途：模擬大量假使用者跑過完整的 compute_template_results 管線，印出
# 校準門檻、驗收標準需要的統計數字。固定種子，每次重跑結果完全一樣。
# 不是 engine 的一部分（會匯入 server.app），不含任何正式計算規則本身，
# 只是重複呼叫既有的 pure function 管線並統計輸出。
# 可手動調整的變數：DEFAULT_HEIGHT_MEAN/SD、DEFAULT_WEIGHT_MEAN/SD（抽樣用的
# 使用者身高體重分布，2026-10 校準改成接近真實使用者的 175/7、70/12，不是
# body_fit.GENERAL_POPULATION_BODY_STATS 的 180/8、78/12 —— 兩者是不同的
# 用途：GENERAL_POPULATION_BODY_STATS 是「一般打球的人母體」的參考基準，這裡
# 是「我們假設真實使用者長什麼樣」的抽樣來源，故意不共用同一個數字）。
"""Mock-user simulation harness for calibration and acceptance checking.

Usage:
    python3 scripts/simulate_results.py --pool current --n 900 --seed 20261007
    python3 scripts/simulate_results.py --pool alltime --n 900 --seed 20261007

Standard library only except reusing server.app's existing pipeline.
"""
import argparse
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server"))

from app import (  # noqa: E402
    ENV_WEIGHTS,
    compute_template_results,
    environment_codes,
    load_archetypes,
    load_data,
    load_drills,
)

DEFAULT_HEIGHT_MEAN = 175.0
DEFAULT_HEIGHT_SD = 7.0
DEFAULT_WEIGHT_MEAN = 70.0
DEFAULT_WEIGHT_SD = 12.0


def mock_payload(rng, axis_questions, body_questions):
    """One synthetic respondent: every axis question answered with a fresh
    random 1-5 score (independent per question, matching how a real BARS
    respondent answers each question on its own merits), height/weight
    drawn from a normal distribution and clamped into the question's own
    [min, max] (so a sampled value is never rejected by collect_body_
    measurements' range check), the other four body questions skipped
    (optional on the real site; skipping them exercises the same code path
    missing_required_body_fields already allows).
    """
    axis_answers = [{"question_id": q["id"], "score": rng.randint(1, 5)} for q in axis_questions]

    body_by_field = {q["field"]: q for q in body_questions}
    height_q = body_by_field["height_cm"]
    weight_q = body_by_field["weight_kg"]
    height = min(height_q["max"], max(height_q["min"], rng.gauss(DEFAULT_HEIGHT_MEAN, DEFAULT_HEIGHT_SD)))
    weight = min(weight_q["max"], max(weight_q["min"], rng.gauss(DEFAULT_WEIGHT_MEAN, DEFAULT_WEIGHT_SD)))
    body_answers = [
        {"question_id": height_q["id"], "value": round(height, 1)},
        {"question_id": weight_q["id"], "value": round(weight, 1)},
    ]
    return {"axis_answers": axis_answers, "body_answers": body_answers}, height


def pearson_correlation(xs, ys):
    n = len(xs)
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / (var_x * var_y) ** 0.5


def run_simulation(pool, n, seed, lang="zh"):
    rng = random.Random(seed)
    questions, skills, players = load_data(pool=pool, lang=lang)
    archetypes = load_archetypes(lang)
    drills_by_key = load_drills(lang)
    env = ENV_WEIGHTS[environment_codes()[0]]

    all_one_star_count = 0
    best_star_histogram = Counter()
    top1_name_counter = Counter()
    heights = []
    avg_top10_heights = []
    empty_plan_count = 0
    total_plan_count = 0
    menu_variety_samples = []

    for _ in range(n):
        payload, height = mock_payload(rng, questions["axis_positioning"], questions["body_measurements"])
        payload["pool"] = pool
        results = compute_template_results(payload, questions, players, skills, archetypes, drills_by_key, lang, pool)
        top10 = results["top_10"]

        stars = [p["fit_stars"] for p in top10]
        if all(s == 1 for s in stars):
            all_one_star_count += 1
        best_star_histogram[stars[0]] += 1
        top1_name_counter[top10[0]["name"]] += 1

        heights.append(height)
        # top_10 entries (built in compute_template_results) don't carry an
        # "id" key -- only name/team/coordinates/etc -- so look players up
        # by name instead of id.
        by_name = {p["name"]: p for p in players}
        avg_top10_heights.append(
            statistics.mean(by_name[p["name"]]["body"]["height_cm"] for p in top10)
        )

        env_code = environment_codes()[0]
        all_pairs = set()
        for p in top10:
            plan = p["training_plans"][env_code]
            total_plan_count += 1
            if not plan:
                empty_plan_count += 1
            all_pairs.update((item["skill_id"], item["level"]) for item in plan)
        menu_variety_samples.append(len(all_pairs))

    n_runs = n
    print(f"pool={pool} n={n_runs} seed={seed}")
    print(f"  all-10-one-star %: {all_one_star_count / n_runs * 100:.1f}")
    print(f"  best-match star histogram: {dict(sorted(best_star_histogram.items()))}")
    top1_name, top1_count = top1_name_counter.most_common(1)[0]
    print(f"  top-1 concentration: {top1_name} at {top1_count / n_runs * 100:.1f}%")
    print(f"  height correlation (user vs top-10 avg player height): {pearson_correlation(heights, avg_top10_heights):.2f}")
    print(f"  empty-training-plan %: {empty_plan_count / total_plan_count * 100:.1f}")
    print(f"  menu variety (distinct skill+level pairs across a user's top 10): mean={statistics.mean(menu_variety_samples):.1f}")


def check_206_113_case(pool, lang="zh"):
    questions, skills, players = load_data(pool=pool, lang=lang)
    archetypes = load_archetypes(lang)
    drills_by_key = load_drills(lang)
    axis_answers = [{"question_id": q["id"], "score": 3} for q in questions["axis_positioning"]]
    body_by_field = {q["field"]: q for q in questions["body_measurements"]}
    body_answers = [
        {"question_id": body_by_field["height_cm"]["id"], "value": 206},
        {"question_id": body_by_field["weight_kg"]["id"], "value": 113},
    ]
    payload = {"axis_answers": axis_answers, "body_answers": body_answers, "pool": pool}
    results = compute_template_results(payload, questions, players, skills, archetypes, drills_by_key, lang, pool)
    body_fit = results["deep_templates"]["body_fit"]
    print(f"206cm/113kg body-fit template ({pool}): {body_fit}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=["current", "alltime"], default="current")
    parser.add_argument("--n", type=int, default=900)
    parser.add_argument("--seed", type=int, default=20261007)
    parser.add_argument("--lang", default="zh")
    args = parser.parse_args()

    run_simulation(args.pool, args.n, args.seed, args.lang)
    check_206_113_case(args.pool, args.lang)


if __name__ == "__main__":
    main()
