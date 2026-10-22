# 用途：測試 Basketball-Reference 資料換算的純函數：表格解析與名字正規化
# (scripts/bbref_tables.py)、聯盟內百分位、六軸加權、球員池百分位、改寫種子腳本
# (scripts/build_players_from_bbref.py)。不連網、不讀真正的快取檔。
# 可手動調整的變數：無——下面的 HTML 片段和數字都是為了驗證規則設計的測試資料。

import tempfile
import unittest
from pathlib import Path

from scripts.bbref_tables import height_to_cm, lb_to_kg, normalize_name, parse_table, to_float
from scripts.build_players_from_bbref import (
    AXIS_RECIPES,
    STATS_SHARE,
    apply_to_seed,
    axis_score,
    first_row_per_player,
    last_team_per_player,
    percentile_within,
    pool_percentiles,
)

TABLE = """
<table class="stats_table" id="per_game_stats"><thead><tr><th data-stat="name_display">Player</th></tr></thead>
<tbody>
<tr><td data-stat="name_display"><a href="/players/j/jokicni01.html">Nikola Joki&#263;</a></td><td data-stat="team_name_abbr">DEN</td><td data-stat="fg3_pct">.380</td></tr>
<tr class="thead"><td data-stat="name_display">Player</td></tr>
<tr><td data-stat="name_display">Two Teams</td><td data-stat="team_name_abbr">2TM</td><td data-stat="fg3_pct">.300</td></tr>
<tr><td data-stat="name_display">Two Teams</td><td data-stat="team_name_abbr">BOS</td><td data-stat="fg3_pct">.310</td></tr>
<tr><td data-stat="name_display">Two Teams</td><td data-stat="team_name_abbr">MIA</td><td data-stat="fg3_pct">.290</td></tr>
<tr><td data-stat="name_display">League Average</td><td data-stat="fg3_pct">.360</td></tr>
</tbody></table>
"""


class TablesTest(unittest.TestCase):
    def test_parse_table_reads_cells_links_and_skips_header_and_summary_rows(self):
        rows = parse_table(TABLE, "per_game_stats")
        self.assertEqual([r["name_display"] for r in rows], ["Nikola Jokić", "Two Teams", "Two Teams", "Two Teams"])
        self.assertEqual(rows[0]["_player_link"], "/players/j/jokicni01.html")
        self.assertEqual(rows[0]["fg3_pct"], ".380")

    def test_tables_hidden_in_html_comments_are_found(self):
        self.assertEqual(len(parse_table("<!--" + TABLE + "-->", "per_game_stats")), 4)

    def test_missing_table_is_empty(self):
        self.assertEqual(parse_table(TABLE, "advanced"), [])

    def test_normalize_name(self):
        self.assertEqual(normalize_name("Nikola Jokić"), "nikola jokic")
        self.assertEqual(normalize_name("Jaren Jackson Jr."), "jaren jackson")
        self.assertEqual(normalize_name("De'Aaron Fox"), "deaaron fox")
        self.assertEqual(normalize_name("Shai Gilgeous-Alexander"), "shai gilgeous alexander")

    def test_number_conversions(self):
        self.assertEqual(to_float(".512"), 0.512)
        self.assertIsNone(to_float(""))
        self.assertEqual(to_float("1,234"), 1234.0)
        self.assertEqual(height_to_cm("6-11"), 211)
        self.assertIsNone(height_to_cm("tall"))
        self.assertEqual(lb_to_kg("250"), 113)


class RowSelectionTest(unittest.TestCase):
    def test_traded_player_keeps_the_combined_row_but_the_last_team(self):
        rows = parse_table(TABLE, "per_game_stats")
        self.assertEqual(first_row_per_player(rows)["two teams"]["team_name_abbr"], "2TM")
        self.assertEqual(last_team_per_player(rows)["two teams"], "MIA")


class ScoringTest(unittest.TestCase):
    def test_percentile_within_uses_mean_rank(self):
        self.assertEqual(percentile_within([1, 2, 3, 4], 3), 0.625)
        self.assertEqual(percentile_within([1, 2, 2, 3], 2), 0.5)

    def test_axis_score_is_the_weighted_mix(self):
        pcts = {f: 1.0 for f, _ in AXIS_RECIPES["A"]}
        self.assertAlmostEqual(axis_score("A", pcts, old_value=0), 1.0)

    def test_missing_features_fall_back_to_the_old_estimate(self):
        self.assertAlmostEqual(axis_score("C2", {"blk_pct": None, "drb_pct": None, "dbpm": None}, old_value=40), 0.40)
        self.assertAlmostEqual(axis_score("C1", None, old_value=70), 0.70)

    def test_axes_keep_the_non_stats_share_of_the_old_estimate(self):
        for axis in ("C1", "D"):
            pcts = {f: 1.0 for f, _ in AXIS_RECIPES[axis]}
            self.assertAlmostEqual(axis_score(axis, pcts, old_value=0), STATS_SHARE[axis])

    def test_pool_percentiles_spread_scores_over_0_to_100(self):
        self.assertEqual(pool_percentiles({"a": 0.1, "b": 0.5, "c": 0.9}), {"a": 17, "b": 50, "c": 83})


SEED = '''PLAYERS = [
    {
        "id": "amen_thompson", "name": "Amen Thompson", "team": "HOU",
        "coordinates": {"A": 84, "B1": 13, "B2": 71, "C1": 81, "C2": 63, "D": 95},
        "body": {"height_cm": 201, "wingspan_cm": 213},
        "notable_traits": ["x"],
    },
    {
        "id": "untouched", "name": "Untouched", "team": "BOS",
        "coordinates": {"A": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5, "D": 6},
        "body": {"height_cm": 190, "wingspan_cm": 200},
    },
]
'''


class ApplyToSeedTest(unittest.TestCase):
    def test_rewrites_only_matching_entries(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "seed.py"
            path.write_text(SEED, encoding="utf-8")
            change = {"new": {"team": "OKC", "coordinates": {"A": 10, "B1": 20, "B2": 30, "C1": 40, "C2": 50, "D": 60},
                              "height_cm": 203, "weight_kg": 95}}
            self.assertEqual(apply_to_seed(path, {"amen_thompson": change}), 1)
            out = path.read_text(encoding="utf-8")
        self.assertIn('"id": "amen_thompson", "name": "Amen Thompson", "team": "OKC",', out)
        self.assertIn('"coordinates": {"A": 10, "B1": 20, "B2": 30, "C1": 40, "C2": 50, "D": 60}', out)
        self.assertIn('"body": {"height_cm": 203, "wingspan_cm": 213, "weight_kg": 95}', out)
        self.assertIn('"coordinates": {"A": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5, "D": 6}', out)
        self.assertIn('"notable_traits": ["x"]', out)

    def test_missing_height_or_weight_keeps_the_old_values(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "seed.py"
            path.write_text(SEED, encoding="utf-8")
            change = {"new": {"team": "HOU", "coordinates": {a: 50 for a in ("A", "B1", "B2", "C1", "C2", "D")},
                              "height_cm": None, "weight_kg": None}}
            apply_to_seed(path, {"amen_thompson": change})
            self.assertIn('"body": {"height_cm": 201, "wingspan_cm": 213}', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
