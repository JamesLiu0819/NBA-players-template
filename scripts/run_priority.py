#!/usr/bin/env python3
# 用途：讀取匯出的作答檔,呼叫 src/engine 算出四軸座標與優先序,是唯一權威的
# 計算結果(tools/survey.html 的即時預覽只是給人看趨勢,不是正式結果)。
# 可手動調整的變數：FACTOR_LABELS(中文標籤文字,可依用詞習慣調整,不影響計算)。
# 其餘像 eps、排序邏輯都在 src/engine 裡,不要在這支腳本裡重複定義計算規則。
"""Authoritative priority calculator — the sole source of truth for P_i.

tools/survey.html has a JS reimplementation of this same math purely for a
live in-browser preview; whenever they disagree, THIS script is right (see
tools/README.md for how to check the two haven't drifted apart).

Usage:
    python3 scripts/run_priority.py [answers_file.json]

With no argument, uses the most recently exported file in data/answers/
(the one with the lexicographically-largest answers_<timestamp>.json name).

Standard library only.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine.axis_position import AXES, score_axis_coordinates  # noqa: E402
from engine.priority import explain_dominant_factor, rank_priorities  # noqa: E402
from engine.relevance import compute_relevance  # noqa: E402
from engine.skill_level import compute_gap, score_skill_current_level  # noqa: E402

FACTOR_LABELS = {
    "G": "能力缺口(G)",
    "E": "聯賽環境權重(E)",
    "R": "自然位置相關性(R)",
    "C": "習得成本(C)",
}


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


def build_priority_items(questions, skills, axis_answers, skill_answers, env):
    coordinates = score_axis_coordinates(questions["axis_positioning"], axis_answers)

    items = []
    for skill in skills:
        current = score_skill_current_level(questions["skill_behavior"], skill_answers, skill["id"])
        gap = compute_gap(current)
        relevance = compute_relevance(coordinates, skill["axis_relevance"])
        if skill["id"] not in env:
            raise SystemExit(f"answers file is missing an env weight for skill: {skill['id']}")
        items.append({
            "skill_id": skill["id"],
            "name_zh": skill["name_zh"],
            "G": gap,
            "E": env[skill["id"]],
            "R": relevance,
            "C": skill["cost_C"],
        })
    return coordinates, items


def format_dominant_factor_sentence(ranked):
    if len(ranked) < 2:
        return None
    higher, lower = ranked[0], ranked[1]
    result = explain_dominant_factor(higher, lower)
    dominant = result["factor"]
    others = [FACTOR_LABELS[f] for f in ("G", "E", "R", "C") if f != dominant]
    return (
        f"{higher['name_zh']}排在{lower['name_zh']}之前，"
        f"主因是{FACTOR_LABELS[dominant]}高出 {result['ratio']:.2f} 倍，"
        f"而非{'、'.join(others)}的差異。"
    )


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
    answers = load_json(answers_path)

    coordinates, items = build_priority_items(
        questions, skills, answers["axis_answers"], answers["skill_answers"], answers["env"]
    )

    print("四軸座標:")
    for axis in AXES:
        print(f"  {axis}: {coordinates[axis]:.1f}")

    ranked = rank_priorities(items)
    print("\n優先序:")
    header = f"  {'#':<3}{'技能':<14}{'P':>8}{'G':>8}{'E':>8}{'R':>8}{'C':>8}"
    print(header)
    for i, item in enumerate(ranked, start=1):
        print(
            f"  {i:<3}{item['name_zh']:<14}{item['P']:>8.3f}"
            f"{item['G']:>8.2f}{item['E']:>8.2f}{item['R']:>8.2f}{item['C']:>8.2f}"
        )

    sentence = format_dominant_factor_sentence(ranked)
    if sentence:
        print(f"\n{sentence}")


if __name__ == "__main__":
    main()
