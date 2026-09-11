#!/usr/bin/env python3
# 用途：讀取匯出的作答檔跟 data/players.json,算出四軸座標後印出「3 位深度模板」
# (技術模板/身材模板/天花板)、「10 人對照表」兩段文字報表。
# 10 人對照表用 rank_similar_players_by_style_and_body,四軸+身材一起算距離,
# 避免推薦身材差異很大的球員當模板(2026-09-11);技術模板跟身材模板維持用
# 純四軸/純身材距離,刻意不受這個改動影響。身材裡的身高/體重在比較前會先用
# percentile_normalize_body 換算成百分位(使用者跟球員各自在自己的母體裡排
# 第幾百分位),不然幾乎所有使用者都會比全部 NBA 球員矮/輕,身材模板永遠是
# 最矮的後衛(同樣是 2026-09-11 討論)。
# 天花板的定義是「D 軸接近、主導差距在 A/B/C 某個技能軸」——一個身體條件跟你
# 差不多、但技術更成熟的球員,是一個真正練得到的目標,而不是天賦不同的另一個
# 人;原本的「反面對照」段落用的是「D 軸差距最大」邏輯,找到的其實是後者,所以
# 直接移除,天花板改用前者的定義。曾經多加過一個跟 10 人對照表#1 相同的「整體
# 模板」,但根本是重複資訊,也移除了(以上都是 2026-09-11 討論)。
# 跟 scripts/run_priority.py 一樣,是唯一權威的計算結果(沒有另外的 UI 或即時預覽
# 版本)。
# 可手動調整的變數：AXIS_LABELS(中文顯示用詞,可依用詞習慣調整,不影響計算)、
# GENERIC_GROWTH_TEMPLATE(沒有技能對得上差異軸時使用的通用句型文字)、
# D_AXIS_GROWTH_TEMPLATE(D軸無法訓練時使用的專用句型文字)、
# CEILING_NOT_FOUND_MESSAGE(找不到符合條件的天花板時顯示的訊息)、
# BODY_MEASUREMENTS_NOT_ANSWERED_MESSAGE(作答檔沒有身材數值題時顯示的訊息)。
"""Renders the 10-player template comparison table plus the 3 deep templates.

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
from engine.body_fit import collect_body_measurements, percentile_normalize_body  # noqa: E402
from engine.player_matching import (  # noqa: E402
    find_body_fit_template,
    find_ceiling_template,
    find_skill_fit_template,
    matching_skill_id,
    rank_similar_players_by_style_and_body,
)

AXIS_LABELS = {
    "A": "持球創造",
    "B": "投射能力",
    "C": "防守對位",
    "D": "運動表現",
}

GENERIC_GROWTH_TEMPLATE = "可以多留意 {label} 這個方向的練習"
D_AXIS_GROWTH_TEMPLATE = "身體天賦上有落差,不能單靠練習籃球技能"
CEILING_NOT_FOUND_MESSAGE = (
    "目前的球員種子資料裡,找不到符合「運動能力跟你接近、"
    "但技術層面明顯更成熟」條件的球員。"
)
BODY_MEASUREMENTS_NOT_ANSWERED_MESSAGE = "作答檔沒有身材數值題的作答,無法計算身材模板。"


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

    body_answers = answers.get("body_answers", [])
    user_body = (
        collect_body_measurements(questions["body_measurements"], body_answers)
        if body_answers else {}
    )
    user_body_pct, players_pct, body_field_ranges_pct = percentile_normalize_body(
        user_body, players, body_field_ranges
    )
    ranked = rank_similar_players_by_style_and_body(
        coordinates, user_body_pct, players_pct, body_field_ranges_pct, k=10
    )

    print("\n3 位深度模板:")

    skill_fit = find_skill_fit_template(coordinates, players)
    print(f"  技術模板：{skill_fit['name']} ({skill_fit['team']})")
    print("      排除運動能力,技術層面跟你最接近的球員（打法風格）。")

    if user_body:
        body_fit = find_body_fit_template(user_body_pct, players_pct, body_field_ranges_pct)
        if body_fit:
            print(f"  身材模板：{body_fit['name']} ({body_fit['team']})")
            print("      身材數值跟你最接近的球員。")
        else:
            print("  身材模板：目前沒有球員可比對。")
    else:
        print(f"  身材模板：{BODY_MEASUREMENTS_NOT_ANSWERED_MESSAGE}")

    ceiling = find_ceiling_template(coordinates, players)
    if ceiling:
        print(f"  天花板：{ceiling['name']} ({ceiling['team']})")
        print("      運動能力跟你接近,但技術層面更成熟的球員")
    else:
        print(f"  天花板：{CEILING_NOT_FOUND_MESSAGE}")

    print("\n10 人對照表:")
    for i, player in enumerate(ranked, start=1):
        stars = "★" * player["fit_stars"] + "☆" * (5 - player["fit_stars"])
        axis = player["dominant_diff_axis"]
        growth = describe_growth_recommendation(player, skills_by_id)
        print(f"  #{i}  {player['name']} ({player['team']})  距離={player['distance']:.1f}  貼合度={stars}")
        print(f"      相似處：{'、'.join(player['notable_traits'])}")
        print(f"      差異：{axis} 軸({AXIS_LABELS[axis]})差距最大 → 可以注意：{growth}")


if __name__ == "__main__":
    main()
