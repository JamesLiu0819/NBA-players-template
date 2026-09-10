#!/usr/bin/env python3
# 用途：讀取匯出的作答檔跟 data/players.json,算出四軸座標後印出「3 位深度模板」
# (技能最貼合/身體最貼合/天花板方向)、「10 人對照表」、「反面對照」三段文字報表。
# 10 人對照表用 rank_similar_players_by_style_and_body,四軸+身材一起算距離,
# 避免推薦身材差異很大的球員當模板(2026-09-11);3 位深度模板跟反面對照維持
# 用四軸(或純身材)距離,刻意不受這個改動影響。
# 跟 scripts/run_priority.py 一樣,是唯一權威的計算結果(沒有另外的 UI 或即時預覽
# 版本)。
# 可手動調整的變數：AXIS_LABELS(中文顯示用詞,可依用詞習慣調整,不影響計算)、
# GENERIC_GROWTH_TEMPLATE(沒有技能對得上差異軸時使用的通用句型文字)、
# D_AXIS_GROWTH_TEMPLATE(D軸無法訓練時使用的專用句型文字)、
# ANTI_TEMPLATE_NOT_FOUND_MESSAGE / CEILING_NOT_FOUND_MESSAGE(找不到符合條件的
# 反面對照/天花板方向時顯示的訊息)、BODY_MEASUREMENTS_NOT_ANSWERED_MESSAGE(作答檔
# 沒有身材數值題時顯示的訊息)。
"""Renders the 10-player template comparison table plus the 3 deep templates
and the anti-template.

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
from engine.body_fit import collect_body_measurements  # noqa: E402
from engine.player_matching import (  # noqa: E402
    find_anti_template,
    find_body_fit_template,
    find_ceiling_template,
    find_skill_fit_template,
    matching_skill_id,
    rank_similar_players_by_style_and_body,
)

AXIS_LABELS = {
    "A": "持球創造",
    "B": "空間位置",
    "C": "防守對位",
    "D": "運動能力層級",
}

GENERIC_GROWTH_TEMPLATE = "可以多留意 {label} 這個方向的練習"
D_AXIS_GROWTH_TEMPLATE = "這是身體天賦上的落差,不是能單靠練習補起來的方向,可以把這位球員當作天花板參考,而不是訓練目標"
ANTI_TEMPLATE_NOT_FOUND_MESSAGE = (
    "目前的球員種子資料裡,找不到符合「A/B/C 軸接近、D 軸差距最大、"
    "且核心優勢不可複製」條件的球員。"
)
CEILING_NOT_FOUND_MESSAGE = (
    "目前的球員種子資料裡,找不到符合「A/B/C 軸接近、D 軸差距最大、"
    "且核心優勢可複製」條件的球員。"
)
BODY_MEASUREMENTS_NOT_ANSWERED_MESSAGE = "作答檔沒有身材數值題的作答,無法計算身體最貼合。"


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
    body_field_ranges = {q["field"]: (q["min"], q["max"]) for q in questions["body_measurements"]}

    coordinates = score_axis_coordinates(questions["axis_positioning"], answers["axis_answers"])
    print("你的四軸座標:")
    for axis in AXES:
        print(f"  {axis}: {coordinates[axis]:.1f}")

    print("\n3 位深度模板:")

    skill_fit = find_skill_fit_template(coordinates, players)
    print(f"  技術模板：{skill_fit['name']} ({skill_fit['team']})")
    print("      排除運動能力,技術層面跟你最接近的球員（打法風格）。")

    ceiling = find_ceiling_template(coordinates, players)
    if ceiling:
        print(f"  天花板：{ceiling['name']} ({ceiling['team']})")
        print("      運動能力差距最大,但同類型裡上限最高的球員")
    else:
        print(f"  天花板：{CEILING_NOT_FOUND_MESSAGE}")

    body_answers = answers.get("body_answers", [])
    user_body = (
        collect_body_measurements(questions["body_measurements"], body_answers)
        if body_answers else {}
    )
    if user_body:
        body_fit = find_body_fit_template(user_body, players, body_field_ranges)
        if body_fit:
            print(f"  體能模板：{body_fit['name']} ({body_fit['team']})")
            print("      身材數值跟你最接近的球員。")
        else:
            print("  體能模板：目前沒有球員可比對。")
    else:
        print(f"  體能模板：{BODY_MEASUREMENTS_NOT_ANSWERED_MESSAGE}")

    ranked = rank_similar_players_by_style_and_body(
        coordinates, user_body, players, body_field_ranges, k=10
    )

    print("\n10 人對照表:")
    for i, player in enumerate(ranked, start=1):
        stars = "★" * player["fit_stars"] + "☆" * (5 - player["fit_stars"])
        axis = player["dominant_diff_axis"]
        growth = describe_growth_recommendation(player, skills_by_id)
        print(f"  #{i}  {player['name']} ({player['team']})  距離={player['distance']:.1f}  貼合度={stars}")
        print(f"      相似處：{'、'.join(player['notable_traits'])}")
        print(f"      差異：{axis} 軸({AXIS_LABELS[axis]})差距最大 → 最值得學的一件事：{growth}")

    anti_template = find_anti_template(coordinates, players)
    print("\n反面對照:")
    if anti_template:
        print(f"  {anti_template['name']} ({anti_template['team']})")
        print(
            f"      你的 A/B/C 軸都跟他很接近,但 D 軸(運動能力層級)差距最大,"
            "而且他賴以成功的核心特質被標註為「不可複製」。"
        )
        print("      不該把他當模板——那個方向會誘導你去追求很難獲得的身體天賦,而不是可以練出來的技術。")
    else:
        print(f"  {ANTI_TEMPLATE_NOT_FOUND_MESSAGE}")


if __name__ == "__main__":
    main()
