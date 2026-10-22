# 用途：解析 Basketball-Reference 頁面裡的表格（scripts/fetch_bbref.py 下載的快取），
# 以及把球員名字正規化成可以比對的形式（去掉重音符號、標點、Jr./III 等字尾）。
# 純函數，不讀檔不連網；讀檔由呼叫端負責。
# 可手動調整的變數：NAME_ALIASES（我們的名字跟 Basketball-Reference 寫法不同時，
# 在這裡加一筆對照）。
"""Parse Basketball-Reference HTML tables and normalise player names."""

import re
import unicodedata
from html import unescape

NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}
# Our spelling -> Basketball-Reference spelling, for names normalisation can't reconcile.
NAME_ALIASES = {
    "Lu Dort": "Luguentz Dort",
    "Cam Johnson": "Cameron Johnson",
    "Cameron Thomas": "Cam Thomas",
    "Penny Hardaway": "Anfernee Hardaway",
    "Rip Hamilton": "Richard Hamilton",
}


def normalize_name(name):
    """'Nikola Jokić' / 'Nikola Jokic' -> 'nikola jokic'; drops Jr./III suffixes and punctuation."""
    name = NAME_ALIASES.get(name, name)
    folded = unicodedata.normalize("NFKD", unescape(name))
    folded = "".join(c for c in folded if not unicodedata.combining(c)).lower()
    folded = re.sub(r"[^a-z\s-]", "", folded).replace("-", " ")
    words = [w for w in folded.split() if w not in NAME_SUFFIXES]
    return " ".join(words)


def _uncomment(html):
    # Basketball-Reference ships some tables inside HTML comments.
    return html.replace("<!--", "").replace("-->", "")


def parse_table(html, table_id):
    """Rows of the table with this id, as dicts keyed by each cell's data-stat.

    Header/separator rows are skipped. Every row also gets "_player_link"
    when its player cell links to a player page. Returns [] if the table
    isn't on the page.
    """
    html = _uncomment(html)
    m = re.search(rf'<table[^>]*\bid="{re.escape(table_id)}"[^>]*>(.*?)</table>', html, re.S)
    if not m:
        return []
    body = m.group(1)
    tbody = re.search(r"<tbody>(.*?)</tbody>", body, re.S)
    rows = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody.group(1) if tbody else body, re.S):
        cells = re.findall(r'<(?:td|th)[^>]*data-stat="([^"]+)"[^>]*>(.*?)</(?:td|th)>', row_html, re.S)
        if not cells:
            continue
        row = {}
        for stat, raw in cells:
            link = re.search(r'href="(/players/\w/\w+\.html)"', raw)
            if link and "_player_link" not in row:
                row["_player_link"] = link.group(1)
            row[stat] = unescape(re.sub(r"<[^>]+>", "", raw)).strip()
        label = row.get("player") or row.get("name_display")
        if label and label not in ("Player", "Team Totals", "League Average"):  # skip repeated header/summary rows
            rows.append(row)
    return rows


def to_float(value):
    """'.512' -> 0.512, '' -> None, '1,234' -> 1234.0."""
    if value is None:
        return None
    value = str(value).replace(",", "").strip()
    if value in ("", "—"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def height_to_cm(text):
    """'6-11' -> 211 (rounded cm); None if unparseable."""
    m = re.match(r"^\s*(\d+)-(\d+)\s*$", text or "")
    if not m:
        return None
    return round((int(m.group(1)) * 12 + int(m.group(2))) * 2.54)


def lb_to_kg(text):
    value = to_float(text)
    return None if value is None else round(value * 0.45359237)
