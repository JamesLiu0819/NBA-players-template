# 10 人球員模板對照表 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 給定使用者的四軸座標,找出貼合度最高的 10 位現役球員,產生含相似處/差異/最值得學的一件事/貼合度的文字對照表。

**Architecture:** 延續現有 `/src/engine`(純函數)+ `/scripts`(讀資料、印報表)的分層方式。新增一份手動估算的球員種子資料(透過 `scripts/build_players_seed.py` 產生,不手改 `data/players.json`)、一個純函數模組 `src/engine/player_matching.py` 做最近鄰距離計算,跟一支 `scripts/run_player_match.py` 負責讀資料、呼叫 engine、印出文字報表。

**Tech Stack:** Python 3 標準函式庫(`unittest`、`json`、`math`、`argparse`、`pathlib`),沿用專案既有的 `PYTHONPATH=src python3 -m unittest discover -t . -s tests` 測試方式。

## Global Constraints

- `/src/engine` 內不得有任何 I/O、隨機、時間依賴,全部純函數(CLAUDE.md)。
- 每個 engine 函數都要有單元測試(CLAUDE.md)。
- `data/players.json` 是離線建置產物,不可手改,只能透過 `scripts/build_players_seed.py` 產生(CLAUDE.md + 設計文件 §3.1)。
- 不加新的相依套件,只用標準函式庫(延續專案既有慣例)。
- 不做即時外部 API 查詢、不寫任何自動化爬蟲(CLAUDE.md 規則 3;設計文件 §3.1 已跟使用者確認排除 NBA2K 自動抓取)。
- 每份新檔案開頭要用繁體中文寫一段「用途」+「可手動調整的變數」說明(使用者在本次工作中新增的慣例)。
- 這個專案目錄目前不是 git repository,使用者已確認略過版本控制——以下任務**不含 git commit 步驟**,每個任務改成「確認測試通過」作為檢查點。
- 距離公式用不加權歐幾里得距離;差異軸用**帶符號**的 `argmax(球員−使用者)`,不取絕對值(設計文件 §3.2、§3.3)。

---

## Task 1: 球員種子資料 (`scripts/build_players_seed.py` → `data/players.json`)

**Files:**
- Create: `scripts/build_players_seed.py`
- Create (由上面腳本產生,不手寫): `data/players.json`
- Test: `tests/engine/test_players_data.py`

**Interfaces:**
- Produces: `data/players.json`,結構為
  `{"_description": str, "_editable_fields": str, "players": [ {"id": str, "name": str, "team": str, "coordinates": {"A": number, "B": number, "C": number, "D": number}, "body": {"height_cm": number, "wingspan_cm": number}, "notable_traits": [str, ...], "signature_skill_id": str | None, "learnability_flag": "low" | "medium" | "high", "_estimate_basis": str}, ... ] }`
  這個結構會被 Task 2 的測試(用假資料,不依賴這個檔案)跟 Task 3 的 `scripts/run_player_match.py`(直接讀這個檔案)使用。

- [ ] **Step 1: 寫失敗測試 `tests/engine/test_players_data.py`**

```python
# 用途：驗證 data/players.json 的資料完整性(欄位齊全、座標範圍、id 唯一、
# signature_skill_id 對應到真的存在的技能)。這份資料是 scripts/build_players_seed.py
# 的產出,不是這支測試檔要驗證的邏輯本身。
# 可手動調整的變數：MIN_PLAYERS(至少要有幾位球員才能湊出 10 人對照表)。

import json
import unittest
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
AXES = ("A", "B", "C", "D")
VALID_LEARNABILITY_FLAGS = {"low", "medium", "high"}
MIN_PLAYERS = 10


def load_json(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class PlayersDataTest(unittest.TestCase):
    def setUp(self):
        self.players = load_json("players.json")["players"]
        self.skill_ids = {s["id"] for s in load_json("skills.json")["skills"]}

    def test_has_at_least_min_players(self):
        self.assertGreaterEqual(len(self.players), MIN_PLAYERS)

    def test_ids_are_unique(self):
        ids = [p["id"] for p in self.players]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_player_has_required_fields(self):
        required = {
            "id", "name", "team", "coordinates", "body",
            "notable_traits", "signature_skill_id", "learnability_flag",
            "_estimate_basis",
        }
        for player in self.players:
            self.assertTrue(required.issubset(player.keys()), player.get("id"))

    def test_coordinates_are_within_zero_to_hundred(self):
        for player in self.players:
            for axis in AXES:
                value = player["coordinates"][axis]
                self.assertGreaterEqual(value, 0, player["id"])
                self.assertLessEqual(value, 100, player["id"])

    def test_notable_traits_are_two_to_four_concrete_items(self):
        for player in self.players:
            traits = player["notable_traits"]
            self.assertGreaterEqual(len(traits), 2, player["id"])
            self.assertLessEqual(len(traits), 4, player["id"])

    def test_learnability_flag_is_valid(self):
        for player in self.players:
            self.assertIn(player["learnability_flag"], VALID_LEARNABILITY_FLAGS, player["id"])

    def test_signature_skill_id_if_present_exists_in_skills_json(self):
        for player in self.players:
            skill_id = player["signature_skill_id"]
            if skill_id is not None:
                self.assertIn(skill_id, self.skill_ids, player["id"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 執行測試,確認因為 `data/players.json` 不存在而失敗(RED)**

Run: `cd "/Users/james/Desktop/NBA球員模板" && PYTHONPATH=src python3 -m unittest tests.engine.test_players_data -v`
Expected: `FileNotFoundError`(找不到 `data/players.json`)

- [ ] **Step 3: 寫 `scripts/build_players_seed.py`(20 位球員的手動估算資料)**

```python
#!/usr/bin/env python3
# 用途：手動估算約 20 位現役球員的四軸座標跟其他資料,產生 data/players.json。
# 這是 P1 最小版本的種子資料,不是離線爬蟲——CLAUDE.md 規定 players.json 是
# 建置產物、不能手改,所以估算資料放在這支腳本的 PLAYERS 常數裡,不是直接寫進
# JSON 檔。之後要換成 nba_api / Basketball-Reference 的真數據時,換掉這支腳本
# 產生 PLAYERS 的方式即可,下游(engine、報表腳本)不用動。
# 可手動調整的變數：PLAYERS(整份球員清單,每位球員的 coordinates/body/
# notable_traits/signature_skill_id/learnability_flag 都可以直接改)。
"""Generates data/players.json from hand-estimated seed data.

Coordinates, body measurements (wingspan especially), and skill/defensive
characterizations below are ESTIMATES for engine bring-up -- informed by
public knowledge of these players' style of play (and, per the design doc,
optionally cross-checked against published NBA2K attribute values by hand,
never scraped), not derived from real play-by-play statistics. See SPEC.md
§6 for the real, stats-derived build pipeline this will eventually be
replaced with.

Usage:
    python3 scripts/build_players_seed.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PLAYERS = [
    {
        "id": "amen_thompson", "name": "Amen Thompson", "team": "HOU",
        "coordinates": {"A": 55, "B": 25, "C": 70, "D": 95},
        "body": {"height_cm": 201, "wingspan_cm": 213},
        "notable_traits": ["轉換進攻速度快", "禁區終結能力強", "防守可以覆蓋多個位置"],
        "signature_skill_id": "perimeter_switch_defense",
        "learnability_flag": "low",
        "_estimate_basis": "公開球評印象 + 一般認知的運動能力表現,手動估算,非真實數據推導",
    },
    {
        "id": "nikola_jokic", "name": "Nikola Jokic", "team": "DEN",
        "coordinates": {"A": 85, "B": 35, "C": 20, "D": 30},
        "body": {"height_cm": 211, "wingspan_cm": 213},
        "notable_traits": ["高位傳導視野極佳", "低位單打腳步細膩", "策應型中鋒"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "low",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "stephen_curry", "name": "Stephen Curry", "team": "GSW",
        "coordinates": {"A": 70, "B": 95, "C": 30, "D": 40},
        "body": {"height_cm": 188, "wingspan_cm": 191},
        "notable_traits": ["超遠三分出手", "無球跑動接球即投", "持球投籃節奏獨特"],
        "signature_skill_id": "perimeter_shooting",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "rudy_gobert", "name": "Rudy Gobert", "team": "MIN",
        "coordinates": {"A": 15, "B": 5, "C": 5, "D": 55},
        "body": {"height_cm": 216, "wingspan_cm": 239},
        "notable_traits": ["護框覆蓋範圍大", "擋拆順下終結", "禁區卡位能力強"],
        "signature_skill_id": "rim_protection",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象 + 臂展等公開身體數據,手動估算,非真實數據推導",
    },
    {
        "id": "luka_doncic", "name": "Luka Doncic", "team": "DAL",
        "coordinates": {"A": 90, "B": 55, "C": 60, "D": 45},
        "body": {"height_cm": 201, "wingspan_cm": 208},
        "notable_traits": ["持球創造能力強", "後撤步跳投製造空間", "傳導視野好"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "low",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "draymond_green", "name": "Draymond Green", "team": "GSW",
        "coordinates": {"A": 60, "B": 40, "C": 75, "D": 50},
        "body": {"height_cm": 198, "wingspan_cm": 208},
        "notable_traits": ["高位傳導組織進攻", "換防彈性大", "防守溝通指揮強"],
        "signature_skill_id": "perimeter_switch_defense",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "klay_thompson", "name": "Klay Thompson", "team": "DAL",
        "coordinates": {"A": 25, "B": 90, "C": 40, "D": 35},
        "body": {"height_cm": 198, "wingspan_cm": 201},
        "notable_traits": ["無球跑動投射效率高", "定點接球出手快", "擋拆後外拉投籃"],
        "signature_skill_id": "perimeter_shooting",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "giannis_antetokounmpo", "name": "Giannis Antetokounmpo", "team": "MIL",
        "coordinates": {"A": 75, "B": 15, "C": 55, "D": 90},
        "body": {"height_cm": 211, "wingspan_cm": 221},
        "notable_traits": ["快攻轉換終結力強", "禁區強力終結", "防守覆蓋範圍大"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "low",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "victor_wembanyama", "name": "Victor Wembanyama", "team": "SAS",
        "coordinates": {"A": 50, "B": 40, "C": 65, "D": 85},
        "body": {"height_cm": 224, "wingspan_cm": 245},
        "notable_traits": ["護框跟外圍換防都能做", "臂展跟移動能力罕見組合", "身材加持的多位置防守"],
        "signature_skill_id": "rim_protection",
        "learnability_flag": "low",
        "_estimate_basis": "公開球評印象 + 臂展等公開身體數據,手動估算,非真實數據推導",
    },
    {
        "id": "jrue_holiday", "name": "Jrue Holiday", "team": "BOS",
        "coordinates": {"A": 45, "B": 55, "C": 80, "D": 55},
        "body": {"height_cm": 193, "wingspan_cm": 196},
        "notable_traits": ["貼身跟防能力強", "換防不吃虧", "無球跑動投射穩定"],
        "signature_skill_id": "perimeter_switch_defense",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "domantas_sabonis", "name": "Domantas Sabonis", "team": "SAC",
        "coordinates": {"A": 70, "B": 10, "C": 15, "D": 25},
        "body": {"height_cm": 211, "wingspan_cm": 221},
        "notable_traits": ["高位/低位策應能力強", "禁區卡位拿板穩定", "傳導視野好"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "mikal_bridges", "name": "Mikal Bridges", "team": "NYK",
        "coordinates": {"A": 35, "B": 60, "C": 70, "D": 60},
        "body": {"height_cm": 198, "wingspan_cm": 206},
        "notable_traits": ["3&D 側翼定位清楚", "貼身跟防外線持球者", "無球跑動投射穩定"],
        "signature_skill_id": "perimeter_switch_defense",
        "learnability_flag": "high",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "kevin_durant", "name": "Kevin Durant", "team": "PHX",
        "coordinates": {"A": 55, "B": 60, "C": 35, "D": 55},
        "body": {"height_cm": 208, "wingspan_cm": 226},
        "notable_traits": ["中距離跳投難防守", "面框單打腳步好", "身材優勢下的投籃選擇多"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象 + 臂展等公開身體數據,手動估算,非真實數據推導",
    },
    {
        "id": "nikola_vucevic", "name": "Nikola Vucevic", "team": "CHI",
        "coordinates": {"A": 55, "B": 35, "C": 15, "D": 15},
        "body": {"height_cm": 211, "wingspan_cm": 223},
        "notable_traits": ["高位傳導組織進攻", "中距離跳投穩定", "禁區卡位拿板"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "high",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "alex_caruso", "name": "Alex Caruso", "team": "OKC",
        "coordinates": {"A": 30, "B": 45, "C": 85, "D": 50},
        "body": {"height_cm": 196, "wingspan_cm": 201},
        "notable_traits": ["抄截嗅覺強", "貼身跟防持球者", "換防彈性大"],
        "signature_skill_id": "perimeter_switch_defense",
        "learnability_flag": "high",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "bam_adebayo", "name": "Bam Adebayo", "team": "MIA",
        "coordinates": {"A": 50, "B": 15, "C": 60, "D": 60},
        "body": {"height_cm": 206, "wingspan_cm": 216},
        "notable_traits": ["護框跟外圍換防都能做", "高位策應能力好", "防守溝通指揮強"],
        "signature_skill_id": "rim_protection",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "buddy_hield", "name": "Buddy Hield", "team": "GSW",
        "coordinates": {"A": 30, "B": 92, "C": 25, "D": 30},
        "body": {"height_cm": 196, "wingspan_cm": 201},
        "notable_traits": ["純射手型側翼", "無球跑動接球即投", "出手速度快"],
        "signature_skill_id": "perimeter_shooting",
        "learnability_flag": "high",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "anthony_davis", "name": "Anthony Davis", "team": "LAL",
        "coordinates": {"A": 45, "B": 20, "C": 30, "D": 70},
        "body": {"height_cm": 208, "wingspan_cm": 231},
        "notable_traits": ["護框覆蓋範圍大", "換防外拉也能守", "身材加持的多位置防守"],
        "signature_skill_id": "rim_protection",
        "learnability_flag": "low",
        "_estimate_basis": "公開球評印象 + 臂展等公開身體數據,手動估算,非真實數據推導",
    },
    {
        "id": "chris_paul", "name": "Chris Paul", "team": "SAS",
        "coordinates": {"A": 80, "B": 45, "C": 50, "D": 15},
        "body": {"height_cm": 183, "wingspan_cm": 188},
        "notable_traits": ["持球節奏掌控力強", "傳導視野好", "地板型但決策速度快"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "high",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "deaaron_fox", "name": "De'Aaron Fox", "team": "SAC",
        "coordinates": {"A": 65, "B": 35, "C": 55, "D": 80},
        "body": {"height_cm": 191, "wingspan_cm": 193},
        "notable_traits": ["轉換速度快", "面框第一步過人銳利", "貼身跟防能力不錯"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
]


def main():
    payload = {
        "_description": (
            "球員種子資料。P1 最小版本用手動估算的方式產生,只是為了讓最近鄰配對"
            "(src/engine/player_matching.py)有真實資料可以測試,不是真實統計數據"
            "推導的結果(每位球員的 _estimate_basis 都有說明)。"
        ),
        "_editable_fields": (
            "整份 players 清單都可以改——調 coordinates 改變座標,調 notable_traits/"
            "signature_skill_id 改變輸出文案,調 learnability_flag(low/medium/high)"
            "留給之後的反面對照功能用。id 一旦被別的地方引用就不要改。"
        ),
        "players": PLAYERS,
    }
    output_path = ROOT / "data" / "players.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"wrote {len(PLAYERS)} players to {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 執行腳本產生 `data/players.json`**

Run: `cd "/Users/james/Desktop/NBA球員模板" && python3 scripts/build_players_seed.py`
Expected: `wrote 20 players to .../data/players.json`

- [ ] **Step 5: 重新執行測試,確認通過(GREEN)**

Run: `cd "/Users/james/Desktop/NBA球員模板" && PYTHONPATH=src python3 -m unittest tests.engine.test_players_data -v`
Expected: 7 個測試全部 `ok`

- [ ] **Step 6: 檢查點**(沒有 git,略過 commit——確認上一步全綠即可進 Task 2)

---

## Task 2: 最近鄰配對純函數 (`src/engine/player_matching.py`)

**Files:**
- Create: `src/engine/player_matching.py`
- Test: `tests/engine/test_player_matching.py`

**Interfaces:**
- Consumes：無跨任務相依(這個任務只用假資料測試,不讀真的 `players.json`/`skills.json`)。
- Produces（Task 3 會用到這些確切名稱跟型別）：
  - `rank_similar_players(user_coordinates: dict, players: list[dict], k: int = 10) -> list[dict]`——每個回傳的 dict 是原始 player dict 展開後加上 `distance: float`、`diff: dict`、`dominant_diff_axis: str`、`fit_stars: int`。
  - `fit_stars_for_distance(distance: float) -> int`
  - `skill_dominant_axis(axis_relevance: dict) -> str`
  - `matching_skill_id(dominant_diff_axis: str, signature_skill_id: str | None, skills_by_id: dict) -> str | None`

- [ ] **Step 1: 寫失敗測試 `tests/engine/test_player_matching.py`**

```python
# 用途：測試 rank_similar_players(最近鄰配對)、fit_stars_for_distance(貼合度
# 星級門檻)、skill_dominant_axis(技能的主導相關軸)、matching_skill_id(差異軸
# 是否剛好對到某個技能的主導軸)這四個函數的計算邏輯與邊界情況。
# 可手動調整的變數：無——這支檔案裡的座標/技能數字都是為了驗證公式而設計的
# 測試案例,不是要調的參數。

import unittest

from engine.player_matching import (
    fit_stars_for_distance,
    matching_skill_id,
    rank_similar_players,
    skill_dominant_axis,
)


class RankSimilarPlayersTest(unittest.TestCase):
    def test_computes_distance_and_signed_diff_correctly(self):
        user = {"A": 50, "B": 50, "C": 50, "D": 50}
        players = [
            {"id": "p1", "name": "P1", "coordinates": {"A": 60, "B": 40, "C": 50, "D": 50}},
        ]

        ranked = rank_similar_players(user, players, k=10)

        self.assertEqual(len(ranked), 1)
        result = ranked[0]
        self.assertEqual(result["diff"], {"A": 10, "B": -10, "C": 0, "D": 0})
        self.assertAlmostEqual(result["distance"], 200 ** 0.5)
        self.assertEqual(result["dominant_diff_axis"], "A")
        self.assertEqual(result["fit_stars"], 5)
        # original player fields pass through untouched
        self.assertEqual(result["id"], "p1")
        self.assertEqual(result["name"], "P1")

    def test_sorts_ascending_by_distance_and_truncates_to_k(self):
        user = {"A": 0, "B": 0, "C": 0, "D": 0}
        players = [
            {"id": "far", "name": "Far", "coordinates": {"A": 90, "B": 0, "C": 0, "D": 0}},
            {"id": "near", "name": "Near", "coordinates": {"A": 10, "B": 0, "C": 0, "D": 0}},
            {"id": "mid", "name": "Mid", "coordinates": {"A": 50, "B": 0, "C": 0, "D": 0}},
        ]

        ranked = rank_similar_players(user, players, k=2)

        self.assertEqual([p["id"] for p in ranked], ["near", "mid"])

    def test_returns_all_players_when_fewer_than_k(self):
        user = {"A": 0, "B": 0, "C": 0, "D": 0}
        players = [
            {"id": "only1", "name": "Only1", "coordinates": {"A": 10, "B": 0, "C": 0, "D": 0}},
            {"id": "only2", "name": "Only2", "coordinates": {"A": 20, "B": 0, "C": 0, "D": 0}},
        ]

        ranked = rank_similar_players(user, players, k=10)

        self.assertEqual(len(ranked), 2)

    def test_dominant_diff_axis_when_user_leads_on_every_axis(self):
        # Known edge case (design doc §3.3): when the user out-scores the
        # player on every axis, all diffs are negative. argmax still returns
        # the *least negative* axis -- not a real "direction to grow toward".
        # This test documents that behavior explicitly rather than hiding it.
        user = {"A": 90, "B": 90, "C": 90, "D": 90}
        players = [
            {"id": "weaker", "name": "Weaker", "coordinates": {"A": 10, "B": 20, "C": 30, "D": 40}},
        ]

        ranked = rank_similar_players(user, players, k=10)

        self.assertEqual(ranked[0]["dominant_diff_axis"], "D")
        self.assertEqual(ranked[0]["diff"]["D"], -50)


class FitStarsForDistanceTest(unittest.TestCase):
    def test_boundary_values(self):
        self.assertEqual(fit_stars_for_distance(20), 5)
        self.assertEqual(fit_stars_for_distance(21), 4)
        self.assertEqual(fit_stars_for_distance(40), 4)
        self.assertEqual(fit_stars_for_distance(41), 3)
        self.assertEqual(fit_stars_for_distance(60), 3)
        self.assertEqual(fit_stars_for_distance(61), 2)
        self.assertEqual(fit_stars_for_distance(80), 2)
        self.assertEqual(fit_stars_for_distance(81), 1)


class SkillDominantAxisTest(unittest.TestCase):
    def test_returns_the_axis_with_highest_relevance(self):
        self.assertEqual(
            skill_dominant_axis({"A": 0.1, "B": 0.9, "C": 0.1, "D": 0.2}), "B"
        )


class MatchingSkillIdTest(unittest.TestCase):
    def setUp(self):
        self.skills_by_id = {
            "perimeter_shooting": {"axis_relevance": {"A": 0.3, "B": 0.9, "C": 0.1, "D": 0.2}},
            "rim_protection": {"axis_relevance": {"A": 0.1, "B": 0.1, "C": 0.9, "D": 0.6}},
        }

    def test_returns_skill_id_when_its_dominant_axis_matches(self):
        result = matching_skill_id("B", "perimeter_shooting", self.skills_by_id)
        self.assertEqual(result, "perimeter_shooting")

    def test_returns_none_when_dominant_axis_does_not_match(self):
        result = matching_skill_id("D", "perimeter_shooting", self.skills_by_id)
        self.assertIsNone(result)

    def test_returns_none_when_no_signature_skill(self):
        result = matching_skill_id("B", None, self.skills_by_id)
        self.assertIsNone(result)

    def test_returns_none_when_signature_skill_not_in_skills_by_id(self):
        result = matching_skill_id("B", "does_not_exist", self.skills_by_id)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 執行測試,確認因為模組不存在而失敗(RED)**

Run: `cd "/Users/james/Desktop/NBA球員模板" && PYTHONPATH=src python3 -m unittest tests.engine.test_player_matching -v`
Expected: `ModuleNotFoundError: No module named 'engine.player_matching'`

- [ ] **Step 3: 寫 `src/engine/player_matching.py`**

```python
# 用途：L3 匹配層,把使用者的四軸座標拿去跟球員種子資料算最近鄰,並提供「差異
# 軸是否剛好對到某個技能」的判斷,供 scripts/run_player_match.py 產生 10 人對照表。
# 可手動調整的變數：_DISTANCE_STAR_THRESHOLDS(貼合度星級的距離門檻,目前是依
# 常理暫定的 20/40/60/80,等有真實球員資料庫、知道實際距離分佈後應該重新校準)。

"""L3 matching layer: nearest-neighbor player template matching.

Pure functions only. See SPEC.md §2 (L3), §3.1 (dominant-diff-axis argmax),
and docs/superpowers/specs/2026-09-10-player-template-matching-design.md.
"""

import math

AXES = ("A", "B", "C", "D")

_DISTANCE_STAR_THRESHOLDS = (
    (20, 5),
    (40, 4),
    (60, 3),
    (80, 2),
)


def fit_stars_for_distance(distance):
    """Bucket a distance into a 1-5 star fit rating using fixed thresholds."""
    for threshold, stars in _DISTANCE_STAR_THRESHOLDS:
        if distance <= threshold:
            return stars
    return 1


def rank_similar_players(user_coordinates, players, k=10):
    """Rank players by distance to user_coordinates in A/B/C/D space.

    user_coordinates: {"A"..."D": 0-100}.
    players: list of dicts, each with at least "coordinates": {"A"..."D": 0-100}.
        All other fields on each player dict pass through unchanged.

    Returns the k nearest players (or fewer, if len(players) < k) sorted by
    ascending distance. Each result dict is the original player dict plus:
        distance: float, unweighted Euclidean distance over A/B/C/D
        diff: {"A"..."D": player[axis] - user_coordinates[axis]} (signed)
        dominant_diff_axis: axis of the signed max of diff (see the design
            doc for the known edge case when the user leads on every axis)
        fit_stars: int 1-5
    """
    ranked = []
    for player in players:
        diff = {axis: player["coordinates"][axis] - user_coordinates[axis] for axis in AXES}
        distance = math.sqrt(sum(diff[axis] ** 2 for axis in AXES))
        dominant_diff_axis = max(AXES, key=lambda axis: diff[axis])
        ranked.append({
            **player,
            "distance": distance,
            "diff": diff,
            "dominant_diff_axis": dominant_diff_axis,
            "fit_stars": fit_stars_for_distance(distance),
        })
    ranked.sort(key=lambda item: item["distance"])
    return ranked[:k]


def skill_dominant_axis(axis_relevance):
    """Return the axis (A/B/C/D) with the highest relevance weight for a skill."""
    return max(AXES, key=lambda axis: axis_relevance[axis])


def matching_skill_id(dominant_diff_axis, signature_skill_id, skills_by_id):
    """Return signature_skill_id if that skill's own dominant axis equals
    dominant_diff_axis, else None (see design doc §3.4: a skill is only "the
    one thing worth learning" if it actually targets the axis where the
    template player exceeds the user the most).
    """
    if not signature_skill_id or signature_skill_id not in skills_by_id:
        return None
    skill = skills_by_id[signature_skill_id]
    if skill_dominant_axis(skill["axis_relevance"]) == dominant_diff_axis:
        return signature_skill_id
    return None
```

- [ ] **Step 4: 執行測試,確認全部通過(GREEN)**

Run: `cd "/Users/james/Desktop/NBA球員模板" && PYTHONPATH=src python3 -m unittest tests.engine.test_player_matching -v`
Expected: 10 個測試全部 `ok`

- [ ] **Step 5: 跑整套測試,確認沒有把之前的東西弄壞**

Run: `cd "/Users/james/Desktop/NBA球員模板" && PYTHONPATH=src python3 -m unittest discover -t . -s tests -p "test_*.py"`
Expected: `OK`(這時應該有 39(原有) + 7(Task 1) + 10(Task 2) = 56 個測試)

- [ ] **Step 6: 檢查點**(沒有 git,略過 commit)

---

## Task 3: 10 人對照表報表 (`scripts/run_player_match.py`)

**Files:**
- Create: `scripts/run_player_match.py`

**Interfaces:**
- Consumes：Task 2 的 `rank_similar_players`、`matching_skill_id`(從 `engine.player_matching` import);既有的 `score_axis_coordinates`(從 `engine.axis_position` import,簽名跟 `scripts/run_priority.py` 用的一樣);Task 1 產生的 `data/players.json`。
- Produces：終端機文字報表,沒有其他程式會 import 這支腳本。

這支腳本是 I/O 組裝層(讀檔、呼叫 engine、印報表),跟現有的 `scripts/run_priority.py` 一樣不寫獨立單元測試——它用到的計算邏輯都已經在 Task 1、Task 2 的測試裡驗證過,這裡只需要跑一次端到端手動驗證。

- [ ] **Step 1: 寫 `scripts/run_player_match.py`**

```python
#!/usr/bin/env python3
# 用途：讀取匯出的作答檔跟 data/players.json,算出四軸座標後找出最近的 10 位
# 現役球員,印出「10 人對照表」文字報表。跟 scripts/run_priority.py 一樣,是
# 唯一權威的計算結果(沒有另外的 UI 或即時預覽版本)。
# 可手動調整的變數：AXIS_LABELS(中文顯示用詞,可依用詞習慣調整,不影響計算)、
# GENERIC_GROWTH_TEMPLATE(沒有技能對得上差異軸時使用的通用句型文字)。
"""Renders the 10-player template comparison table.

Usage:
    python3 scripts/run_player_match.py [answers_file.json]

With no argument, uses the most recently exported file in data/answers/.

Standard library only.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine.axis_position import AXES, score_axis_coordinates  # noqa: E402
from engine.player_matching import matching_skill_id, rank_similar_players  # noqa: E402

AXIS_LABELS = {
    "A": "持球創造",
    "B": "空間位置",
    "C": "防守對位",
    "D": "運動能力層級",
}

GENERIC_GROWTH_TEMPLATE = "差在 {axis} 軸({label}) → 可以多留意這個方向的練習"


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


def describe_growth_recommendation(player, skills_by_id):
    axis = player["dominant_diff_axis"]
    skill_id = matching_skill_id(axis, player.get("signature_skill_id"), skills_by_id)
    if skill_id:
        return skills_by_id[skill_id]["metric"]["action"]
    return GENERIC_GROWTH_TEMPLATE.format(axis=axis, label=AXIS_LABELS[axis])


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
    players = load_json(ROOT / "data" / "players.json")["players"]
    answers = load_json(answers_path)
    skills_by_id = {s["id"]: s for s in skills}

    coordinates = score_axis_coordinates(questions["axis_positioning"], answers["axis_answers"])
    print("你的四軸座標:")
    for axis in AXES:
        print(f"  {axis}: {coordinates[axis]:.1f}")

    ranked = rank_similar_players(coordinates, players, k=10)

    print("\n10 人對照表:")
    for i, player in enumerate(ranked, start=1):
        stars = "★" * player["fit_stars"] + "☆" * (5 - player["fit_stars"])
        axis = player["dominant_diff_axis"]
        growth = describe_growth_recommendation(player, skills_by_id)
        print(f"  #{i}  {player['name']} ({player['team']})  距離={player['distance']:.1f}  貼合度={stars}")
        print(f"      相似處：{'、'.join(player['notable_traits'])}")
        print(f"      差異：{axis} 軸({AXIS_LABELS[axis]})差距最大 → 最值得學的一件事：{growth}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 端到端手動驗證**

Run: `cd "/Users/james/Desktop/NBA球員模板" && python3 scripts/run_player_match.py`

（沒帶參數會自動用 `data/answers/` 底下最新的一份作答檔——目前已經有一份 `answers_20260908T163834.json`。）

Expected（人工檢查,不是自動比對）：
- 印出「你的四軸座標」四行,數值跟之前 `run_priority.py` 印出的座標一致(因為用同一個 `score_axis_coordinates` 函數、同一份作答檔)
- 印出「10 人對照表」,有 10 位球員(因為 Task 1 產生了 20 位,`k=10` 截斷)
- 每位球員都有距離(由近到遠排序)、貼合度星級、相似處(2-4 條 `notable_traits`)、差異軸+最值得學的一件事
- 手動抽查一位球員：確認印出的「最值得學的一件事」如果引用了某個技能的 `metric.action`,那個技能的 `axis_relevance` 主導軸真的等於印出的差異軸(否則 `matching_skill_id` 邏輯有誤)

- [ ] **Step 3: 檢查點**(沒有 git,略過 commit——確認上一步人工檢查沒問題,這個功能就完成了)

---

## 完成後的狀態

- `data/players.json` 有 20 位手動估算的球員
- `src/engine/player_matching.py` 有 4 個純函數,都有單元測試覆蓋
- `scripts/run_player_match.py` 可以直接對現有的 `data/answers/*.json` 跑出 10 人對照表
- 測試總數從 39 增加到 39 + 7(Task 1) + 10(Task 2) = 56
- 明確不含：3 位深度模板、反面對照、影片庫、真實數據抓取、環境權重整合、任何 UI(見設計文件 §2)
