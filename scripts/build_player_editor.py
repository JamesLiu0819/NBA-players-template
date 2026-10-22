#!/usr/bin/env python3
# 用途：把目前 data/zh/ 的球員資料（現役 + 歷史）、原型錨點、技能名稱，寫進
# tools/player-editor.html 的資料區塊（<!--DATA-START--> 到 <!--DATA-END--> 之間），
# 讓那個本機編輯頁面顯示最新的資料。球員資料更新後執行一次：
#   python3 scripts/build_player_editor.py
#   python3 scripts/build_player_editor.py --compare main   # 另外附上 main 分支的舊資料，頁面會顯示新舊差異
# 每位球員也附上手動指定的原型(archetype_id，沒指定是 null)跟 engine 實際採用的
# 原型(engine_archetype：有指定就是指定的，沒有就是依座標分類的)，編輯頁面會拿它跟頁面裡
# 用 JavaScript 重算的結果比對，不一致就在頁面上顯示警告，避免兩邊算法悄悄分岔。
# 「＊ 不太符合任何原型」：每位球員離最接近的原型錨點的距離（六軸 + 體型，跟原型分類同一套
# 距離），排在全部球員最遠的 MISFIT_SHARE 比例就標星號；門檻在這裡算好寫進頁面，頁面
# 修改數值時用同一個門檻即時重判。
# 可手動調整的變數：MISFIT_SHARE（標星號的比例，目前 0.10 = 最遠的 10%）。
"""Embed the current player data into tools/player-editor.html."""

import json
import math
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine.archetype import SIZE_AXIS_WEIGHT, classify_archetype, compute_player_sizes  # noqa: E402

EDITOR = ROOT / "tools" / "player-editor.html"
DATA_BLOCK = re.compile(r"<!--DATA-START-->.*?<!--DATA-END-->", re.S)
POOLS = (("c", "球員.json"), ("h", "歷史球員.json"))
MISFIT_SHARE = 0.10
AXES = ("A", "B1", "B2", "C1", "C2", "D")


def load(name):
    with open(ROOT / "data" / "zh" / name, encoding="utf-8") as f:
        return json.load(f)


def nearest_archetype_distance(coordinates, archetypes, size):
    """Distance to the closest archetype anchor, same formula as classify_archetype."""
    best = math.inf
    for a in archetypes:
        squared = sum((a["coordinates"][ax] - coordinates[ax]) ** 2 for ax in AXES)
        if size is not None and "size" in a:
            squared += (a["size"] - size) ** 2 * SIZE_AXIS_WEIGHT
        best = min(best, math.sqrt(squared))
    return best


def misfit_threshold(distances, share=MISFIT_SHARE):
    """Smallest distance that is still in the farthest `share` of players."""
    ordered = sorted(distances)
    flagged = max(1, math.ceil(len(ordered) * share))
    index = max(0, len(ordered) - flagged)
    return ordered[index]


def build_payload(pools, archetypes, skill_names, snapshot, previous=None):
    """pools: [(tag, [player dict, ...]), ...] in data-file shape.
    previous: optional {(tag, id): player dict} from an older data snapshot to compare against."""
    players, distances = [], []
    for tag, pool in pools:
        sizes = compute_player_sizes(pool)
        prev_sizes = compute_player_sizes([v for (t, _), v in (previous or {}).items() if t == tag]) if previous else {}
        for p in pool:
            distances.append(nearest_archetype_distance(p["coordinates"], archetypes, sizes.get(p["id"])))
            old = (previous or {}).get((tag, p["id"]))
            players.append({
                "id": p["id"],
                "name": p["name"],
                "team": p["team"],
                "pool": tag,
                "coordinates": p["coordinates"],
                "body": p["body"],
                "traits": p.get("notable_traits", []),
                "signature_skill": skill_names.get(p.get("signature_skill_id"), ""),
                "archetype_id": p.get("archetype_id"),
                "engine_archetype": (
                    p.get("archetype_id")
                    or classify_archetype(p["coordinates"], archetypes, size=sizes.get(p["id"]))["id"]
                ),
                "prev": None if old is None else {
                    "team": old["team"],
                    "coordinates": old["coordinates"],
                    "body": old["body"],
                    "archetype": old.get("archetype_id")
                    or classify_archetype(old["coordinates"], archetypes, size=prev_sizes.get(old["id"]))["id"],
                },
            })
    return {
        "snapshot": snapshot,
        "size_axis_weight": SIZE_AXIS_WEIGHT,
        "misfit_threshold": misfit_threshold(distances),
        "misfit_share": MISFIT_SHARE,
        "compare_label": None,
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


def load_from_git(ref, name):
    out = subprocess.run(["git", "show", f"{ref}:data/zh/{name}"], cwd=ROOT, capture_output=True, check=True)
    return json.loads(out.stdout.decode("utf-8"))


def main():
    archetypes = load("原型.json")["archetypes"]
    skill_names = {s["id"]: s["name_zh"] for s in load("技能.json")["skills"]}
    pools = [(tag, load(name)["players"]) for tag, name in POOLS]
    previous, ref = None, None
    if "--compare" in sys.argv:
        ref = sys.argv[sys.argv.index("--compare") + 1]
        previous = {(tag, p["id"]): p for tag, name in POOLS for p in load_from_git(ref, name)["players"]}
    payload = build_payload(pools, archetypes, skill_names, date.today().isoformat(), previous)
    payload["compare_label"] = ref
    html = EDITOR.read_text(encoding="utf-8")
    EDITOR.write_text(embed(html, payload), encoding="utf-8")
    print(f"寫入 {len(payload['players'])} 位球員到 {EDITOR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
