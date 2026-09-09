#!/usr/bin/env python3
# 用途：讀取匯出的作答檔跟 data/players.json,算出四軸座標後找出最近的 10 位
# 現役球員,印出「10 人對照表」文字報表。跟 scripts/run_priority.py 一樣,是
# 唯一權威的計算結果(沒有另外的 UI 或即時預覽版本)。
# 可手動調整的變數：AXIS_LABELS(中文顯示用詞,可依用詞習慣調整,不影響計算)、
# GENERIC_GROWTH_TEMPLATE(沒有技能對得上差異軸時使用的通用句型文字)、
# D_AXIS_GROWTH_TEMPLATE(D軸無法訓練時使用的專用句型文字)。
"""Renders the 10-player template comparison table.

Usage:
    python3 scripts/run_player_match.py [answers_file.json]

With no argument, uses the most recently exported file in data/answers/.

Standard library only.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine.axis_position import AXES, score_axis_coordinates  # noqa: E402
from engine.player_matching import matching_skill_id, rank_similar_players  # noqa: E402

AXIS_LABELS = {
    "A": "持球創造",
    "B": "空間位置",
    "C": "防守對位",
    "D": "運動能力層級",
}

GENERIC_GROWTH_TEMPLATE = "可以多留意 {label} 這個方向的練習"
D_AXIS_GROWTH_TEMPLATE = "這是身體天賦上的落差,不是能單靠練習補起來的方向,可以把這位球員當作天花板參考,而不是訓練目標"


def find_latest_answers_file():
    answers_dir = ROOT / "data" / "answers"
    candidates = sorted(answers_dir.glob("answers_*.json"))
    if not candidates:
        raise SystemExit(
            f"no answers_*.json found in {answers_dir}. "
            "Export one from tools/survey.html first, or pass a path explicitly."
        )
    return candidates[-1]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def describe_growth_recommendation(player, skills_by_id):
    axis = player["dominant_diff_axis"]
    skill_id = matching_skill_id(axis, player.get("signature_skill_id"), skills_by_id)
    if skill_id:
        return skills_by_id[skill_id]["metric"]["action"]
    if axis == "D":
        return D_AXIS_GROWTH_TEMPLATE
    return GENERIC_GROWTH_TEMPLATE.format(label=AXIS_LABELS[axis])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "answers_file",
        nargs="?",
        default=None,
        help="path to an answers.json export; defaults to the latest file in data/answers/",
    )
    args = parser.parse_args()

    answers_path = Path(args.answers_file) if args.answers_file else find_latest_answers_file()
    print(f"作答檔: {answers_path}\n")

    questions = load_json(ROOT / "data" / "questions.json")
    skills = load_json(ROOT / "data" / "skills.json")["skills"]
    players = load_json(ROOT / "data" / "players.json")["players"]
    answers = load_json(answers_path)
    skills_by_id = {s["id"]: s for s in skills}

    coordinates = score_axis_coordinates(questions["axis_positioning"], answers["axis_answers"])
    print("你的四軸座標:")
    for axis in AXES:
        print(f"  {axis}: {coordinates[axis]:.1f}")

    ranked = rank_similar_players(coordinates, players, k=10)

    print("\n10 人對照表:")
    for i, player in enumerate(ranked, start=1):
        stars = "★" * player["fit_stars"] + "☆" * (5 - player["fit_stars"])
        axis = player["dominant_diff_axis"]
        growth = describe_growth_recommendation(player, skills_by_id)
        print(f"  #{i}  {player['name']} ({player['team']})  距離={player['distance']:.1f}  貼合度={stars}")
        print(f"      相似處：{'、'.join(player['notable_traits'])}")
        print(f"      差異：{axis} 軸({AXIS_LABELS[axis]})差距最大 → 最值得學的一件事：{growth}")


if __name__ == "__main__":
    main()
