#!/usr/bin/env python3
# 用途：用 Basketball-Reference 的一般數據、進階數據、投籃分布和身高體重（先用
# scripts/fetch_bbref.py 下載到 data/raw/bbref/），重新估算全部球員的六軸目標座標、
# 身高、體重，以及現役球員的球隊，並寫回兩支種子腳本的 PLAYERS：
#   python3 scripts/build_players_from_bbref.py            # 只產生報告，不改任何檔案
#   python3 scripts/build_players_from_bbref.py --apply    # 寫回種子腳本
# 之後照常執行兩支種子腳本跟 build_zh_hans_data.py 重新產生 data/。
#
# 換算方法（全部固定算式，同樣的快取永遠得到同樣結果）：
#   1. 每位球員取一個球季：現役用 CURRENT_SEASON（上場不足 MIN_MINUTES 分鐘就改用
#      FALLBACK_SEASON）；歷史球員用資料裡的代表年份。
#   2. 每項數據先換成「該球季聯盟內」的百分位（只跟同季上場滿 MIN_MINUTES 的球員比），
#      這樣 1987 年的三分出手數不會跟 2026 年直接比，年代差異被抵銷。
#   3. 依 AXIS_RECIPES 把幾項百分位加權成六軸各自的分數。某項數據那個年代還沒有
#      （三分線 1980 才有、抄截阻攻 1974 才有、投籃距離 1997 才有），就改用該軸
#      原本的估算值補上那一部分。「原本的估算」固定讀 scripts/pre_bbref_estimates.json
#      （2026-10-23 從 main 凍結的手動/2K 估算），不是種子腳本裡的現值——種子腳本已經
#      被這支腳本改寫過，拿它當基準重跑會一直疊加在自己的結果上。
#      持球創造與禁區得分的分工（2026-10-23）：二分球裡「沒有被助攻」的比例算進持球
#      創造（後衛切入上籃是自己創造的），「被助攻」的比例算進禁區得分（中鋒接傳球、
#      補籃），所以很會切入的後衛不會拿到跟中鋒一樣的禁區得分。
#   4. 最後在我們 224 人的球員池裡排名、換成 0-100 百分位，當作新的目標座標——
#      跟原本 2K 屬性換算用的是同一種排名法，分數分布不會整個偏掉。
#   5. 每一軸的分數只有 STATS_SHARE 比例來自數據，其餘保留原本的估算：傳導、投射、
#      禁區得分這些數據量得很準就全用數據；禁區防守（阻攻、籃板）還算可靠；外圍防守
#      跟運動表現在數據上幾乎看不出來（抄截多不等於防守好，例如 Jrue Holiday 抄截不多
#      但是頂級外圍防守者），所以大部分保留原本的估算。
#   6. 最後套上 scripts/manual_overrides.json（tools/player-editor.html 的手動修改，由
#      scripts/apply_player_edits.py 寫入）：手動改過的六軸或身材永遠優先，重算不會蓋掉。
#   臂展 Basketball-Reference 沒有，維持原值；體重改用真實數據。
# 可手動調整的變數：CURRENT_SEASON / FALLBACK_SEASON、MIN_MINUTES、AXIS_RECIPES 的權重、
# STATS_SHARE（每一軸有多少比例來自數據）。
"""Rebuild player coordinates and body data from cached Basketball-Reference pages."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.bbref_tables import height_to_cm, lb_to_kg, normalize_name, parse_table, to_float  # noqa: E402
from scripts.fetch_bbref import BBREF_TEAM, CURRENT_SEASON, FALLBACK_SEASON, cache_path  # noqa: E402

AXES = ("A", "B1", "B2", "C1", "C2", "D")
MIN_MINUTES = 500
# How much of each axis comes from box-score stats; the rest keeps the existing estimate.
STATS_SHARE = {"A": 1.0, "B1": 1.0, "B2": 1.0, "C1": 0.35, "C2": 0.75, "D": 0.5}
OUR_TEAM = {v: k for k, v in BBREF_TEAM.items()}

# axis -> list of (feature, weight). A feature missing for that season is
# replaced by the player's existing estimate for the axis (see module header).
AXIS_RECIPES = {
    # usg_pct alone rewards post-up bigs (e.g. Shaq); the unassisted share of 2-point makes
    # separates players who create their own shot from players who finish others' passes.
    "A": [("ast_pct", 0.45), ("unassisted_fg2", 0.35), ("usg_pct", 0.20)],
    "B1": [("fg3a_per36", 0.45), ("fg3_pct_shrunk", 0.35), ("ft_pct", 0.20)],
    # Big-man-style interior finishing: putbacks/offensive boards and finishing teammates'
    # passes at the rim. Guards' self-created drives count toward A instead.
    "B2": [("orb_pct", 0.30), ("assisted_fg2", 0.25), ("rim_fga_per36", 0.25), ("fg2_pct", 0.20)],
    "C1": [("stl_pct", 1.0)],
    "C2": [("blk_pct", 0.55), ("drb_pct", 0.25), ("dbpm", 0.20)],
    "D": [("dunks_per36", 0.4), ("blk_pct", 0.2), ("stl_pct", 0.2), ("orb_pct", 0.2)],
}


def read(url_path):
    path = cache_path(url_path)
    return path.read_text(encoding="utf-8") if path.exists() else None


def first_row_per_player(rows):
    """Traded players have a combined row (2TM/3TM/TOT) listed first; keep it."""
    out = {}
    for row in rows:
        name = normalize_name(row.get("name_display") or row.get("player", ""))
        if name and name not in out:
            out[name] = row
    return out


def last_team_per_player(rows):
    out = {}
    for row in rows:
        name = normalize_name(row.get("name_display") or row.get("player", ""))
        team = row.get("team_name_abbr") or row.get("team_id")
        if name and team and not re.match(r"^\d?TM$|^TOT$", team):
            out[name] = team  # later rows are later stints
    return out


def season_features(year):
    """{normalized name: {feature: raw value}} for one season, plus each player's minutes and last team."""
    per_game = read(f"/leagues/NBA_{year}_per_game.html")
    advanced = read(f"/leagues/NBA_{year}_advanced.html")
    if per_game is None or advanced is None:
        return None
    pg_rows = parse_table(per_game, "per_game_stats")
    pg, adv = first_row_per_player(pg_rows), first_row_per_player(parse_table(advanced, "advanced"))
    shooting_html = read(f"/leagues/NBA_{year}_shooting.html")
    sh = first_row_per_player(parse_table(shooting_html, "shooting")) if shooting_html else {}
    teams = last_team_per_player(pg_rows)

    out = {}
    for name, a in adv.items():
        p = pg.get(name, {})
        mp_total = to_float(a.get("mp"))
        mpg = to_float(p.get("mp_per_g"))
        games = to_float(p.get("games"))
        if not mp_total or not mpg:
            continue
        per36 = lambda v: None if v is None else v / mpg * 36  # noqa: E731
        fga, fta = to_float(p.get("fga_per_g")), to_float(p.get("fta_per_g"))
        fg3, fg3a = to_float(p.get("fg3_per_g")), to_float(p.get("fg3a_per_g"))
        f = {
            "ast_pct": to_float(a.get("ast_pct")),
            "usg_pct": to_float(a.get("usg_pct")),
            "ft_pct": to_float(p.get("ft_pct")),
            "fg2_pct": to_float(p.get("fg2_pct")) or to_float(p.get("fg_pct")),
            "fta_rate": (fta / fga) if fta is not None and fga else None,
            "orb_pct": to_float(a.get("orb_pct")),
            "drb_pct": to_float(a.get("drb_pct")),
            "stl_pct": to_float(a.get("stl_pct")),
            "blk_pct": to_float(a.get("blk_pct")),
            "dbpm": to_float(a.get("dbpm")),
            "fg3a_per36": per36(fg3a) if year >= 1980 else None,
            "fg3_pct_shrunk": None,
            "rim_fga_per36": None,
            "dunks_per36": None,
            "unassisted_fg2": None,
            "assisted_fg2": None,
        }
        if year >= 1980 and fg3 is not None and fg3a is not None and games:
            made, att = fg3 * games, fg3a * games
            f["fg3_pct_shrunk"] = (made + 0.33 * 100) / (att + 100)  # pull low-volume shooters toward average
        s = sh.get(name)
        if s:
            share = to_float(s.get("pct_fga_00_03"))
            f["rim_fga_per36"] = per36(fga * share) if fga is not None and share is not None else None
            assisted = to_float(s.get("pct_ast_fg2"))
            f["unassisted_fg2"] = 1 - assisted if assisted is not None else None
            f["assisted_fg2"] = assisted
            dunks = to_float(s.get("fg_dunk"))
            f["dunks_per36"] = dunks / mp_total * 36 if dunks is not None else None
        elif year < 1997:
            f["rim_fga_per36"] = per36(to_float(p.get("fg2a_per_g")))  # no shot locations yet: 2-point volume
        out[name] = {"features": f, "mp": mp_total, "team": teams.get(name), "link": a.get("_player_link") or p.get("_player_link")}
    return out


def percentile_within(values, value):
    below = sum(1 for v in values if v < value)
    equal = sum(1 for v in values if v == value)
    return (below + 0.5 * equal) / len(values)


def season_percentiles(season):
    """Replace each raw feature with its percentile among players with >= MIN_MINUTES that season."""
    qualified = [r for r in season.values() if r["mp"] >= MIN_MINUTES]
    pools = {}
    for r in qualified:
        for k, v in r["features"].items():
            if v is not None:
                pools.setdefault(k, []).append(v)
    out = {}
    for name, r in season.items():
        out[name] = {k: (percentile_within(pools[k], v) if v is not None and k in pools else None)
                     for k, v in r["features"].items()}
    return out


def axis_score(axis, pcts, old_value):
    """Weighted percentile mix for one axis; missing features fall back to old_value/100."""
    total = 0.0
    for feature, weight in AXIS_RECIPES[axis]:
        value = pcts.get(feature) if pcts else None
        total += weight * (value if value is not None else old_value / 100)
    share = STATS_SHARE[axis]
    return share * total + (1 - share) * old_value / 100


def pool_percentiles(scores):
    """{id: score} -> {id: 0-100 integer percentile within the pool} (mean-rank)."""
    values = list(scores.values())
    return {pid: round(percentile_within(values, s) * 100) for pid, s in scores.items()}


def player_page_body(html):
    h = re.search(r'"height"[^>]*>([\d]+-[\d]+)<', html) or re.search(r">(\d+-\d+)</span>,", html)
    w = re.search(r'"weight"[^>]*>(\d+)lb<', html) or re.search(r">(\d+)lb</span>", html)
    return (height_to_cm(h.group(1)) if h else None, lb_to_kg(w.group(1)) if w else None)


def roster_bodies():
    """{normalized name: (height_cm, weight_kg)} from the current-season team rosters."""
    out = {}
    for path in sorted((ROOT / "data" / "raw" / "bbref").glob(f"teams__*__{CURRENT_SEASON}.html")):
        for row in parse_table(path.read_text(encoding="utf-8"), "roster"):
            name = normalize_name(row.get("player", "") or row.get("name_display", ""))
            out.setdefault(name, (height_to_cm(row.get("height")), lb_to_kg(row.get("weight"))))
    return out


BASELINE_PATH = ROOT / "scripts" / "pre_bbref_estimates.json"


def load_baseline():
    with open(BASELINE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {(pool, pid): v for pool in ("current", "alltime") for pid, v in data[pool].items()}


OVERRIDES_PATH = ROOT / "scripts" / "manual_overrides.json"


def load_overrides():
    if not OVERRIDES_PATH.exists():
        return {}
    with open(OVERRIDES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {(pool, pid): v for pool, players in data.items() if pool != "_description" for pid, v in players.items()}


def apply_overrides(new, override):
    """Overlay one player's manual edits on the rebuilt values (both {"coordinates", "height_cm",
    "weight_kg", ...}); other body fields are carried in new["body_extra"]."""
    out = {**new, "coordinates": {**new["coordinates"], **override.get("coordinates", {})}, "body_extra": {}}
    for field, value in override.get("body", {}).items():
        if field in ("height_cm", "weight_kg"):
            out[field] = value
        else:
            out["body_extra"][field] = value
    return out


def build(current_players, alltime_players, baseline=None, overrides=None):
    """baseline: {(pool, id): {"coordinates", "team", "height_cm"}} -- the existing
    estimates used where stats are missing or weak. Players not in it (added later)
    fall back to their seed-script values."""
    baseline = baseline or {}
    overrides = overrides or {}
    seasons = {}

    def season(year):
        if year not in seasons:
            raw = season_features(year)
            seasons[year] = (raw, season_percentiles(raw) if raw else None)
        return seasons[year]

    picks, notes = {}, {}
    for pool, players in (("current", current_players), ("alltime", alltime_players)):
        for p in players:
            key = (pool, p["id"])
            name = normalize_name(p["name"])
            if pool == "current":
                raw, pct = season(CURRENT_SEASON)
                year = CURRENT_SEASON
                if raw is None or name not in raw or raw[name]["mp"] < MIN_MINUTES:
                    raw2, pct2 = season(FALLBACK_SEASON)
                    if raw2 and name in raw2 and (name not in (raw or {}) or raw2[name]["mp"] > raw[name]["mp"]):
                        raw, pct, year = raw2, pct2, FALLBACK_SEASON
            else:
                year = int(p["team"])
                raw, pct = season(year)
            if raw is None or name not in raw:
                picks[key] = None
                notes[key] = f"no {year} stats found"
                continue
            picks[key] = {"year": year, "pcts": pct[name], "raw": raw[name]}
            missing = [k for k, v in pct[name].items() if v is None]
            notes[key] = f"{year} season, {round(raw[name]['mp'])} min" + (f"; missing {', '.join(missing)}" if missing else "")

    all_players = [("current", p) for p in current_players] + [("alltime", p) for p in alltime_players]
    new_coords = {}
    for axis in AXES:
        scores = {}
        for pool, p in all_players:
            pick = picks[(pool, p["id"])]
            old = baseline.get((pool, p["id"]), p)["coordinates"][axis]
            scores[(pool, p["id"])] = axis_score(axis, pick["pcts"] if pick else None, old)
        for key, value in pool_percentiles(scores).items():
            new_coords.setdefault(key, {})[axis] = value

    bodies = roster_bodies()
    result = []
    for pool, p in all_players:
        key = (pool, p["id"])
        pick = picks[key]
        height, weight = None, None
        team = p["team"]
        if pool == "current":
            height, weight = bodies.get(normalize_name(p["name"]), (None, None))
            if pick and pick["raw"]["team"]:
                team = OUR_TEAM.get(pick["raw"]["team"], pick["raw"]["team"])
        if pool == "current" and not height and pick and pick["raw"].get("link"):
            html = read(pick["raw"]["link"])  # not on a current roster: use the player page
            if html:
                height, weight = player_page_body(html)
        elif pool == "alltime" and pick and pick["raw"].get("link"):
            html = read(pick["raw"]["link"])
            if html:
                height, weight = player_page_body(html)
        base = baseline.get(key, {"coordinates": p["coordinates"], "team": p["team"], "height_cm": p["body"]["height_cm"]})
        result.append({
            "pool": pool, "id": p["id"], "name": p["name"],
            "old": {"coordinates": base["coordinates"], "team": base["team"], "height_cm": base["height_cm"]},
            "new": apply_overrides({"coordinates": new_coords[key], "team": team, "height_cm": height, "weight_kg": weight},
                                   overrides.get(key, {})),
            "note": notes[key],
        })
    return result


ENTRY_START = re.compile(r'^(\s*)"id": "([^"]+)", "name": "([^"]+)", "team": "([^"]+)",\s*$', re.M)


def apply_to_seed(path, changes_by_id):
    """Rewrite team/coordinates/body lines of matching PLAYERS entries in a seed script."""
    text = path.read_text(encoding="utf-8")
    starts = list(ENTRY_START.finditer(text))
    pieces, last, done = [], 0, 0
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        change = changes_by_id.get(m.group(2))
        if change is None:
            continue
        block = text[m.start():end]
        c = change["new"]
        block = block.replace(f'"team": "{m.group(4)}",', f'"team": "{c["team"]}",', 1)
        coords = ", ".join(f'"{a}": {c["coordinates"][a]}' for a in AXES)
        block, n1 = re.subn(r'"coordinates": \{[^}]*\}', f'"coordinates": {{{coords}}}', block, count=1)

        def body_sub(bm):
            body = json.loads("{" + bm.group(1) + "}")
            if c["height_cm"]:
                body["height_cm"] = c["height_cm"]
            if c["weight_kg"]:
                body["weight_kg"] = c["weight_kg"]
            body.update(c.get("body_extra", {}))
            return '"body": {' + ", ".join(f'"{k}": {json.dumps(v)}' for k, v in body.items()) + "}"
        block, n2 = re.subn(r'"body": \{([^}]*)\}', body_sub, block, count=1)
        if n1 != 1 or n2 != 1:
            raise ValueError(f"could not rewrite entry {m.group(2)} in {path.name}")
        pieces.append(text[last:m.start()])
        pieces.append(block)
        last = end
        done += 1
    pieces.append(text[last:])
    path.write_text("".join(pieces), encoding="utf-8")
    return done


def main():
    from scripts.build_players_alltime_seed import PLAYERS as ALLTIME
    from scripts.build_players_seed import PLAYERS as CURRENT

    result = build(CURRENT, ALLTIME, load_baseline(), load_overrides())
    report = ROOT / "data" / "raw" / "bbref_rebuild_report.json"
    report.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    missing = [r for r in result if r["note"].startswith("no ")]
    no_height = [r["name"] for r in result if not r["new"]["height_cm"]]
    print(f"{len(result)} players; {len(missing)} without stats; {len(no_height)} without height/weight")
    for r in missing:
        print(f"  NO STATS: {r['pool']} {r['name']}: {r['note']}")
    if no_height:
        print("  NO HEIGHT:", ", ".join(no_height))
    print(f"report: {report.relative_to(ROOT)}")

    if "--apply" in sys.argv:
        for pool, script in (("current", "build_players_seed.py"), ("alltime", "build_players_alltime_seed.py")):
            changes = {r["id"]: r for r in result if r["pool"] == pool and not r["note"].startswith("no ")}
            n = apply_to_seed(ROOT / "scripts" / script, changes)
            print(f"rewrote {n} entries in scripts/{script}")


if __name__ == "__main__":
    main()
