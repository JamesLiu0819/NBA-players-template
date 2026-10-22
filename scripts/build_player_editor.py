#!/usr/bin/env python3
# 用途：把目前 data/zh/ 的球員資料（現役 + 歷史）、原型錨點、技能名稱，寫進
# tools/player-editor.html 的資料區塊（<!--DATA-START--> 到 <!--DATA-END--> 之間），
# 讓那個本機編輯頁面顯示最新的資料。球員資料更新後執行一次：
#   python3 scripts/build_player_editor.py
# 每位球員也附上 engine 自己算出的原型(engine_archetype)，編輯頁面會拿它跟頁面裡
# 用 JavaScript 重算的結果比對，不一致就在頁面上顯示警告，避免兩邊算法悄悄分岔。
# 可手動調整的變數：無。
"""Embed the current player data into tools/player-editor.html."""

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine.archetype import SIZE_AXIS_WEIGHT, classify_archetype, compute_player_sizes  # noqa: E402

EDITOR = ROOT / "tools" / "player-editor.html"
DATA_BLOCK = re.compile(r"<!--DATA-START-->.*?<!--DATA-END-->", re.S)
POOLS = (("c", "球員.json"), ("h", "歷史球員.json"))


def load(name):
    with open(ROOT / "data" / "zh" / name, encoding="utf-8") as f:
        return json.load(f)


def build_payload(pools, archetypes, skill_names, snapshot):
    """pools: [(tag, [player dict, ...]), ...] in data-file shape."""
    players = []
    for tag, pool in pools:
        sizes = compute_player_sizes(pool)
        for p in pool:
            players.append({
                "id": p["id"],
                "name": p["name"],
                "team": p["team"],
                "pool": tag,
                "coordinates": p["coordinates"],
                "body": p["body"],
                "traits": p.get("notable_traits", []),
                "signature_skill": skill_names.get(p.get("signature_skill_id"), ""),
                "engine_archetype": classify_archetype(p["coordinates"], archetypes, size=sizes.get(p["id"]))["id"],
            })
    return {
        "snapshot": snapshot,
        "size_axis_weight": SIZE_AXIS_WEIGHT,
        "archetypes": [
            {"id": a["id"], "name_zh": a["name_zh"], "coordinates": a["coordinates"], "size": a["size"], "flavor": a["flavor"]}
            for a in archetypes
        ],
        "players": players,
    }


def embed(html, payload):
    """Replace the page's data block with payload. "</" is escaped so no
    string in the data can close the surrounding <script> tag early."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    block = f'<!--DATA-START--><script id="data" type="application/json">{text}</script><!--DATA-END-->'
    if not DATA_BLOCK.search(html):
        raise ValueError("data block markers not found in the editor page")
    return DATA_BLOCK.sub(lambda _m: block, html, count=1)


def main():
    archetypes = load("原型.json")["archetypes"]
    skill_names = {s["id"]: s["name_zh"] for s in load("技能.json")["skills"]}
    pools = [(tag, load(name)["players"]) for tag, name in POOLS]
    payload = build_payload(pools, archetypes, skill_names, date.today().isoformat())
    html = EDITOR.read_text(encoding="utf-8")
    EDITOR.write_text(embed(html, payload), encoding="utf-8")
    print(f"寫入 {len(payload['players'])} 位球員到 {EDITOR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
