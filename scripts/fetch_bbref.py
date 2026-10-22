#!/usr/bin/env python3
# 用途：離線下載 Basketball-Reference 的公開數據頁面，存成本機快取，給
# scripts/build_players_from_bbref.py 換算球員的六軸座標和身材。只在本機手動執行，
# 網站執行時不會跑（符合 CLAUDE.md「不做即時外部查詢」）。
# 下載的原始頁面存在 data/raw/bbref/，不進 git（見 .gitignore）：那是
# Basketball-Reference 的資料，放上公開的 GitHub 等於重新散布。
# 禮貌規則：遵守對方 robots.txt 的 Crawl-delay（3 秒），這裡每次請求間隔
# REQUEST_DELAY_SECONDS 秒；已經下載過的頁面直接讀快取，不重抓。
# 可手動調整的變數：CURRENT_SEASON / FALLBACK_SEASON（現役球員用哪一季，
# Basketball-Reference 用球季結束的年份，2025-26 球季 = 2026）、REQUEST_DELAY_SECONDS。
"""Download and cache the Basketball-Reference pages the player rebuild needs."""

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "bbref"
BASE = "https://www.basketball-reference.com"
USER_AGENT = "Mozilla/5.0 (personal basketball side project; offline batch; respects Crawl-delay)"
REQUEST_DELAY_SECONDS = 4.0
CURRENT_SEASON = 2026
FALLBACK_SEASON = 2025
# Our team codes -> Basketball-Reference's.
BBREF_TEAM = {"BKN": "BRK", "CHA": "CHO", "PHX": "PHO"}
NBA_TEAMS = ["ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW", "HOU", "IND", "LAC", "LAL",
             "MEM", "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"]

_last_request = [0.0]


def cache_path(url_path):
    return CACHE / (url_path.strip("/").replace("/", "__"))


def fetch(url_path):
    """Return the page HTML, from cache when possible. Raises on HTTP errors."""
    path = cache_path(url_path)
    if path.exists():
        return path.read_text(encoding="utf-8")
    wait = REQUEST_DELAY_SECONDS - (time.time() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(BASE + url_path, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", "replace")
    finally:
        _last_request[0] = time.time()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return html


def season_pages(year):
    pages = [f"/leagues/NBA_{year}_per_game.html", f"/leagues/NBA_{year}_advanced.html"]
    if year >= 1997:  # shot-location data starts in 1996-97
        pages.append(f"/leagues/NBA_{year}_shooting.html")
    return pages


def player_links(html):
    """{bbref player id: /players/x/xxxxx01.html} from a league table page."""
    return {m.group(2): m.group(1) for m in re.finditer(r'href="(/players/\w/(\w+)\.html)"', html)}


def main():
    alltime = json.load(open(ROOT / "data" / "zh" / "歷史球員.json", encoding="utf-8"))["players"]
    years = sorted({int(p["team"]) for p in alltime})

    plan = []
    for year in (CURRENT_SEASON, FALLBACK_SEASON):
        plan += season_pages(year)
    plan += [f"/teams/{BBREF_TEAM.get(t, t)}/{CURRENT_SEASON}.html" for t in NBA_TEAMS]
    for year in years:
        plan += season_pages(year)

    done = 0
    for url_path in plan:
        try:
            fetch(url_path)
        except Exception as e:  # keep going; the build step reports what's missing
            print(f"FAILED {url_path}: {e}", file=sys.stderr)
        done += 1
        print(f"[{done}/{len(plan)}] {url_path}", flush=True)

    # Player pages (height/weight) for historical players, found by name in their season's table.
    from scripts.bbref_tables import normalize_name  # noqa: E402  (after sys.path setup below)
    for p in alltime:
        html = fetch(f"/leagues/NBA_{p['team']}_per_game.html")
        target = normalize_name(p["name"])
        link = None
        for m in re.finditer(r'<a href="(/players/\w/\w+\.html)">([^<]+)</a>', html):
            if normalize_name(m.group(2)) == target:
                link = m.group(1)
                break
        if link is None:
            print(f"NO PLAYER LINK for {p['name']} in {p['team']}", file=sys.stderr)
            continue
        try:
            fetch(link)
        except Exception as e:
            print(f"FAILED {link}: {e}", file=sys.stderr)
        print(f"player page {p['name']} -> {link}", flush=True)


def fetch_current_player_pages():
    """Player pages for current players missing from every current roster (usually
    injured all season), so their height/weight can still be read."""
    from scripts.bbref_tables import normalize_name, parse_table
    current = json.load(open(ROOT / "data" / "zh" / "球員.json", encoding="utf-8"))["players"]
    on_roster = set()
    for t in NBA_TEAMS:
        html = fetch(f"/teams/{BBREF_TEAM.get(t, t)}/{CURRENT_SEASON}.html")
        on_roster |= {normalize_name(r.get("player", "")) for r in parse_table(html, "roster")}
    links = {}
    for year in (FALLBACK_SEASON, CURRENT_SEASON):  # later season wins
        for r in parse_table(fetch(f"/leagues/NBA_{year}_per_game.html"), "per_game_stats"):
            if r.get("_player_link"):
                links[normalize_name(r.get("name_display", ""))] = r["_player_link"]
    for p in current:
        name = normalize_name(p["name"])
        if name in on_roster:
            continue
        link = links.get(name)
        if link is None:
            print(f"NO PLAYER LINK for current player {p['name']}", file=sys.stderr)
            continue
        fetch(link)
        print(f"player page {p['name']} -> {link}", flush=True)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
    fetch_current_player_pages()
