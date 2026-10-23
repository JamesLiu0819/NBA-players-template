#!/usr/bin/env python3
# 用途：依每個原型的「代表球員」(data/zh/原型.json 每個原型的 exemplars，球員 id 清單)，
# 重新算出原型的錨點座標(coordinates)跟體型(size)，寫回繁中跟英文的原型檔；簡中由
# scripts/build_zh_hans_data.py 從繁中轉出來。球員資料或代表球員改了之後執行：
#   python3 scripts/build_archetype_anchors.py
# 錨點 = 代表球員六軸座標的平均；體型 = 代表球員「在自己球員池裡」身高體重百分位平均
# (跟 engine/archetype.py 的 compute_player_sizes 同一套)的平均。這樣原型跟球員用的是
# 同一把尺：球員資料換算方式改了，原型會跟著代表球員一起移動，不用重新手打數字
# (2026-10-23 討論：手打的錨點跟 Basketball-Reference 重算後的資料對不上)。
# tests/engine/test_archetypes_data.py 會檢查錨點跟代表球員的平均一致，忘了重跑會失敗。
# 可手動調整的變數：無——要調的是代表球員名單(原型檔裡的 exemplars)，可以在
# tools/player-editor.html 勾選後下載修改檔交給 Claude。
"""Recompute archetype anchors from each archetype's exemplar players."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine.archetype import compute_player_sizes  # noqa: E402

AXES = ("A", "B1", "B2", "C1", "C2", "D")
PLAYER_FILES = ("球員.json", "歷史球員.json")


def compute_anchors(archetypes, pools):
    """archetypes: list with "exemplars" (player ids). pools: list of player lists
    (each pool's sizes are computed within that pool). Returns {archetype id:
    {"coordinates": {...}, "size": int}}. Raises on an unknown exemplar id or an
    archetype with no exemplars."""
    players, sizes = {}, {}
    for pool in pools:
        sizes.update(compute_player_sizes(pool))
        players.update({p["id"]: p for p in pool})
    out = {}
    for archetype in archetypes:
        ids = archetype.get("exemplars") or []
        if not ids:
            raise ValueError(f"archetype {archetype['id']} has no exemplars")
        unknown = [pid for pid in ids if pid not in players]
        if unknown:
            raise ValueError(f"archetype {archetype['id']} lists unknown players: {unknown}")
        out[archetype["id"]] = {
            "coordinates": {a: round(sum(players[pid]["coordinates"][a] for pid in ids) / len(ids), 1) for a in AXES},
            "size": round(sum(sizes[pid] for pid in ids) / len(ids)),
        }
    return out


def write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    zh_path, en_path = ROOT / "data" / "zh" / "原型.json", ROOT / "data" / "en" / "archetypes.json"
    zh, en = json.load(open(zh_path, encoding="utf-8")), json.load(open(en_path, encoding="utf-8"))
    pools = [json.load(open(ROOT / "data" / "zh" / name, encoding="utf-8"))["players"] for name in PLAYER_FILES]
    anchors = compute_anchors(zh["archetypes"], pools)
    exemplars = {a["id"]: a["exemplars"] for a in zh["archetypes"]}
    for doc in (zh, en):
        for archetype in doc["archetypes"]:
            archetype.update(anchors[archetype["id"]])
            archetype["exemplars"] = exemplars[archetype["id"]]
    write(zh_path, zh)
    write(en_path, en)
    for archetype in zh["archetypes"]:
        print(f"{archetype['name_zh']}: {archetype['coordinates']} size {archetype['size']} ({len(archetype['exemplars'])} 位代表)")


if __name__ == "__main__":
    main()
