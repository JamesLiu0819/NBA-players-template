#!/usr/bin/env python3
# 用途：套用 tools/player-editor.html 下載的修改檔（player-edits/v1）：
#   python3 scripts/apply_player_edits.py ~/Downloads/球員資料修改-20261023-1151.json
# 會做的事：
#   - 六軸 / 身材數值：直接寫進兩支種子腳本的 PLAYERS，同時記在 scripts/manual_overrides.json。
#     scripts/build_players_from_bbref.py 重算後會最後套上這份檔案，所以手動修改永遠優先，
#     不會被下一次 Basketball-Reference 重算蓋掉。
#   - 原型（手動指定）：在種子腳本的球員加上或移除 "archetype_id"。
#   - 代表球員：調整 data/zh/原型.json 與 data/en/archetypes.json 的 exemplars。
#   - 刪除球員：從種子腳本、英文球員檔、manual_overrides、代表球員名單移除。
#   - old 跟 new 一樣的修改會略過。
# 套用完照常執行：兩支種子腳本 → build_archetype_anchors.py → build_zh_hans_data.py →
# sync_en_players.py → build_player_editor.py（這支腳本最後會印出完整指令）。
# 可手動調整的變數：無。
"""Apply a player-editor export file to the seed scripts and data files."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEEDS = {"current": ROOT / "scripts" / "build_players_seed.py", "alltime": ROOT / "scripts" / "build_players_alltime_seed.py"}
EN_PLAYERS = {"current": ROOT / "data" / "en" / "players.json", "alltime": ROOT / "data" / "en" / "players_alltime.json"}
ARCHETYPE_FILES = (ROOT / "data" / "zh" / "原型.json", ROOT / "data" / "en" / "archetypes.json")
OVERRIDES = ROOT / "scripts" / "manual_overrides.json"


# ---------- seed-script text edits (pure: text in, text out) ----------

def entry_span(text, pid):
    """(start, end) of the PLAYERS entry for pid, from its "    {" line through "    },\\n"."""
    m = re.search(r'^    \{\n        "id": "' + re.escape(pid) + r'",.*?^    \},\n', text, re.M | re.S)
    if not m:
        raise KeyError(f"player {pid} not found in seed script")
    return m.start(), m.end()


def delete_entry(text, pid):
    start, end = entry_span(text, pid)
    return text[:start] + text[end:]


def _edit_entry(text, pid, fn):
    start, end = entry_span(text, pid)
    return text[:start] + fn(text[start:end]) + text[end:]


def set_coordinate(text, pid, axis, value):
    def fn(block):
        new, n = re.subn(r'("coordinates": \{[^}]*"' + re.escape(axis) + r'": )[0-9.]+', lambda m: m.group(1) + json.dumps(value), block, count=1)
        if n != 1:
            raise KeyError(f"{pid}: coordinate {axis} not found")
        return new
    return _edit_entry(text, pid, fn)


def set_body(text, pid, field, value):
    def fn(block):
        m = re.search(r'"body": \{([^}]*)\}', block)
        if not m:
            raise KeyError(f"{pid}: body not found")
        body = json.loads("{" + m.group(1) + "}")
        body[field] = value
        rendered = '"body": {' + ", ".join(f'"{k}": {json.dumps(v)}' for k, v in body.items()) + "}"
        return block[:m.start()] + rendered + block[m.end():]
    return _edit_entry(text, pid, fn)


def set_archetype(text, pid, archetype_id):
    """Add, replace or (archetype_id None/"") remove the entry's "archetype_id" line."""
    def fn(block):
        block = re.sub(r'^        "archetype_id": "[^"]*",\n', "", block, flags=re.M)
        if not archetype_id:
            return block
        line = f'        "archetype_id": "{archetype_id}",\n'
        m = re.search(r'^        "signature_skill_id": [^\n]*\n', block, re.M)
        at = m.end() if m else block.index("\n") + 1
        return block[:at] + line + block[at:]
    return _edit_entry(text, pid, fn)


# ---------- grouping the export ----------

def meaningful_changes(changes):
    """Drop no-op edits (old == new) and every other edit for a player that is being deleted."""
    deleted = {(c["pool"], c["id"]) for c in changes if c["field"] == "deleted" and c["new"]}
    out = []
    for c in changes:
        if c["field"] != "deleted" and (c["pool"], c["id"]) in deleted:
            continue
        if c["field"] != "deleted" and c.get("old") == c.get("new"):
            continue
        out.append(c)
    return out


def update_exemplars(archetypes, changes, deleted_ids):
    """Return archetypes with exemplars moved per exemplar_of changes, deleted players dropped."""
    out = []
    moves = {c["id"]: c["new"] for c in changes if c["field"] == "exemplar_of"}
    for archetype in archetypes:
        ids = [pid for pid in archetype.get("exemplars", []) if pid not in deleted_ids and pid not in moves]
        ids += [pid for pid, target in moves.items() if target == archetype["id"]]
        out.append({**archetype, "exemplars": ids})
    empty = [a["id"] for a in out if not a["exemplars"]]
    if empty:
        raise ValueError(f"these archetypes would have no representative players: {empty}")
    return out


def update_overrides(overrides, changes, deleted):
    """Record coordinate/body edits in the manual-overrides structure; forget deleted players."""
    out = {pool: dict(players) for pool, players in overrides.items()}
    for pool, pid in deleted:
        out.get(pool, {}).pop(pid, None)
    for c in changes:
        group, _, key = c["field"].partition(".")
        if group not in ("coordinates", "body"):
            continue
        entry = out.setdefault(c["pool"], {}).setdefault(c["id"], {})
        entry.setdefault(group, {})[key] = c["new"]
    return out


def main(path):
    edit = json.load(open(path, encoding="utf-8"))
    if edit.get("format") != "player-edits/v1":
        raise SystemExit("not a player-edits/v1 file")
    changes = meaningful_changes(edit["changes"])
    deleted = {(c["pool"], c["id"]) for c in changes if c["field"] == "deleted" and c["new"]}
    print(f"{len(edit['changes'])} changes in file, {len(changes)} to apply ({len(edit['changes']) - len(changes)} skipped as no-ops or superseded by a deletion)")

    seeds = {pool: p.read_text(encoding="utf-8") for pool, p in SEEDS.items()}
    for c in changes:
        pool, pid, field = c["pool"], c["id"], c["field"]
        if field == "deleted":
            seeds[pool] = delete_entry(seeds[pool], pid)
        elif field == "archetype_id":
            seeds[pool] = set_archetype(seeds[pool], pid, c["new"])
        elif field.startswith("coordinates."):
            seeds[pool] = set_coordinate(seeds[pool], pid, field.split(".")[1], c["new"])
        elif field.startswith("body."):
            seeds[pool] = set_body(seeds[pool], pid, field.split(".")[1], c["new"])
    for pool, p in SEEDS.items():
        p.write_text(seeds[pool], encoding="utf-8")

    for pool, p in EN_PLAYERS.items():
        doc = json.load(open(p, encoding="utf-8"))
        doc["players"] = [pl for pl in doc["players"] if (pool, pl["id"]) not in deleted]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")

    deleted_ids = {pid for _, pid in deleted}
    for p in ARCHETYPE_FILES:
        doc = json.load(open(p, encoding="utf-8"))
        doc["archetypes"] = update_exemplars(doc["archetypes"], changes, deleted_ids)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")

    overrides = json.load(open(OVERRIDES, encoding="utf-8")) if OVERRIDES.exists() else {}
    overrides.pop("_description", None)
    overrides = update_overrides(overrides, changes, deleted)
    overrides = {"_description": (
        "Hand edits from tools/player-editor.html (applied by scripts/apply_player_edits.py). "
        "scripts/build_players_from_bbref.py applies these last, so they survive every rebuild."), **overrides}
    with open(OVERRIDES, "w", encoding="utf-8") as f:
        json.dump(overrides, f, ensure_ascii=False, indent=1)
        f.write("\n")

    counts = {}
    for c in changes:
        kind = c["field"].split(".")[0]
        counts[kind] = counts.get(kind, 0) + 1
    print("applied:", counts)
    print("next: python3 scripts/build_players_seed.py && python3 scripts/build_players_alltime_seed.py && "
          "python3 scripts/build_archetype_anchors.py && .venv/bin/python3 scripts/build_zh_hans_data.py && "
          "python3 scripts/sync_en_players.py && python3 scripts/build_player_editor.py --compare main")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 scripts/apply_player_edits.py <edits.json>")
    main(sys.argv[1])
