#!/usr/bin/env python3
# 用途：照 engine/player_matching.py 檔頭記載的校準方法，對指定球員池重新算出
# 星等門檻的八個切點。40 次模擬、k=10，共 400 筆距離樣本，取第
# 44/89/133/178/222/267/311/356 名（由小到大排序）當門檻，四捨五入到整數。
# 2026-10 改動：抽樣用的身高體重從 GENERAL_POPULATION_BODY_STATS 的 180/78
# 改成接近真實使用者的 175/7（身高）、70/12（體重）——兩者是不同用途，故意
# 不共用同一個數字，見 scripts/simulate_results.py 開頭的說明。
# 不是 engine 的一部分，不含校準公式本身的邏輯判斷，只是重複呼叫既有函數。
"""Recalibrate the 8 star-rating threshold cut points for one player pool.

Usage:
    python3 scripts/calibrate_star_thresholds.py --pool current
    python3 scripts/calibrate_star_thresholds.py --pool alltime
"""
import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import json  # noqa: E402

from engine.axis_position import score_axis_coordinates  # noqa: E402
from engine.body_fit import percentile_normalize_body  # noqa: E402
from engine.player_matching import rank_similar_players_by_style_and_body  # noqa: E402

CALIBRATION_HEIGHT_MEAN = 175.0
CALIBRATION_HEIGHT_SD = 7.0
CALIBRATION_WEIGHT_MEAN = 70.0
CALIBRATION_WEIGHT_SD = 12.0
N_SIMULATIONS = 40
K = 10
CUT_RANKS = [44, 89, 133, 178, 222, 267, 311, 356]  # i*400/9 for i in 1..8
STAR_LABELS = [5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=["current", "alltime"], required=True)
    parser.add_argument("--seed", type=int, default=20261007)
    args = parser.parse_args()

    questions = load_json(ROOT / "data" / "zh" / "題庫.json")
    players_file = "球員.json" if args.pool == "current" else "歷史球員.json"
    players = load_json(ROOT / "data" / "zh" / players_file)["players"]
    body_field_ranges = {q["field"]: (q["min"], q["max"]) for q in questions["body_measurements"]}

    rng = random.Random(args.seed)
    all_distances = []
    for _ in range(N_SIMULATIONS):
        axis_answers = [
            {"question_id": q["id"], "score": rng.randint(1, 5)}
            for q in questions["axis_positioning"]
        ]
        coordinates = score_axis_coordinates(questions["axis_positioning"], axis_answers)
        height = max(
            body_field_ranges["height_cm"][0],
            min(body_field_ranges["height_cm"][1], rng.gauss(CALIBRATION_HEIGHT_MEAN, CALIBRATION_HEIGHT_SD)),
        )
        weight = max(
            body_field_ranges["weight_kg"][0],
            min(body_field_ranges["weight_kg"][1], rng.gauss(CALIBRATION_WEIGHT_MEAN, CALIBRATION_WEIGHT_SD)),
        )
        user_body = {"height_cm": height, "weight_kg": weight}
        user_body_pct, players_pct, field_ranges_pct = percentile_normalize_body(
            user_body, players, body_field_ranges
        )
        ranked = rank_similar_players_by_style_and_body(
            coordinates, user_body_pct, players_pct, field_ranges_pct, k=K
        )
        all_distances.extend(p["distance"] for p in ranked)

    all_distances.sort()
    print(f"pool={args.pool}  n_samples={len(all_distances)}")
    thresholds = []
    for rank, stars in zip(CUT_RANKS, STAR_LABELS):
        distance = round(all_distances[rank - 1])
        thresholds.append((distance, stars))
        print(f"  rank {rank:3d} -> distance {all_distances[rank - 1]:.1f} -> rounded {distance}  ({stars} stars)")
    print(f"\n  tuple to paste into player_matching.py:\n  {tuple(thresholds)}")


if __name__ == "__main__":
    main()
