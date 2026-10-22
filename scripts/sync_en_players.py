#!/usr/bin/env python3
# 用途：把 data/zh/ 球員檔裡「不是文字」的欄位（球隊、六軸座標、身材、模擬作答、
# 指定原型）複製到 data/en/ 的對應球員，英文的名字以外文字（特點）不動。
# 繁中由種子腳本產生、簡中由 build_zh_hans_data.py 整包轉換，只有英文檔是另外維護的，
# 改了球員數值後執行這支，三語一致性測試才會過：
#   python3 scripts/sync_en_players.py
# 可手動調整的變數：SYNCED_FIELDS（要從繁中複製過去的欄位）。
"""Copy non-text player fields from data/zh to data/en."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIRS = (("球員.json", "players.json"), ("歷史球員.json", "players_alltime.json"))
SYNCED_FIELDS = ("team", "coordinates", "body", "mock_axis_answers", "signature_skill_id", "learnability_flag", "archetype_id")


def sync_players(zh_players, en_players):
    """Return en_players with SYNCED_FIELDS copied from the zh player of the same id.
    An archetype_id absent in zh is removed from en too. Raises if the id sets differ."""
    zh_by_id = {p["id"]: p for p in zh_players}
    if set(zh_by_id) != {p["id"] for p in en_players}:
        raise ValueError("zh and en player id sets differ; add/remove players in both first")
    out = []
    for en in en_players:
        zh, merged = zh_by_id[en["id"]], dict(en)
        for field in SYNCED_FIELDS:
            if field in zh:
                merged[field] = zh[field]
            else:
                merged.pop(field, None)
        out.append(merged)
    return out


def main():
    for zh_name, en_name in PAIRS:
        zh = json.load(open(ROOT / "data" / "zh" / zh_name, encoding="utf-8"))
        en_path = ROOT / "data" / "en" / en_name
        en = json.load(open(en_path, encoding="utf-8"))
        en["players"] = sync_players(zh["players"], en["players"])
        with open(en_path, "w", encoding="utf-8") as f:
            json.dump(en, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"synced {len(en['players'])} players into data/en/{en_name}")


if __name__ == "__main__":
    main()
