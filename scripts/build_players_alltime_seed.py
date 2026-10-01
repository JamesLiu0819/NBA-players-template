#!/usr/bin/env python3
# 用途：估算歷史知名球員(已退役、跨 1960s-2010s)的六軸座標跟其他資料,
# 產生 data/players_alltime.json,給「歷史球員模板(All-time)」模式用。
# v3(2026-10)：跟 build_players_seed.py 同步改成六軸,coordinates 改用 2K
# 歷史/All-Time 卡的屬性值算百分位——詳見 build_players_seed.py 檔頭說明。跟
# scripts/build_players_seed.py(現役球員池)是同一套 schema、同一套
# derive_body_measurements/mock_axis_answers/mock_skill_answers 邏輯(直接
# import 重用,不重複定義),差別只有：(1) 球員名單換成退役傳奇球星,不跟
# 現役池重複;(2) "team" 欄位放的是代表年份(字串,例如球員巔峰球季),不是
# 球隊縮寫——因為歷史球員橫跨多支球隊、用球隊代碼意義不大,用年份標示「這個
# 座標估算大概對應他生涯哪個階段」比較有參考價值。下游(engine、server、
# 前端)完全不用改,因為程式邏輯本來就只是把 "team" 欄位原樣印出來,不管裡面
# 放的是字串還是年份。
# 這是第一批,先收錄約 65 位廣為人知的歷史球星,涵蓋 1960s-2010s 各年代跟
# 各種打法原型;不是詳盡的歷史球員資料庫,之後可以再擴充(參照現役球員池
# 20→50→150 的擴充模式)。
# v2(2026-09-11)：跟現役球員池同步改成 mock-answer 驅動——PLAYERS 常數裡
# 手寫的 coordinates 只是目標座標,main() 會反推成模擬作答再用
# score_axis_coordinates 算出真正的座標,同時補上 15 題技能行為模擬作答,
# 詳見 scripts/build_players_seed.py 檔頭說明。
# 可手動調整的變數：PLAYERS(整份球員清單,每位球員的 coordinates/body/
# notable_traits/signature_skill_id/learnability_flag/team(年份) 都可以
# 直接改,coordinates 現在的意義是「目標座標」,不是最終值)。
"""Generates data/players_alltime.json from hand-estimated seed data for
retired, widely-known historical players.

Coordinates, body measurements (wingspan especially), and skill/defensive
characterizations below are ESTIMATES for engine bring-up -- informed by
public knowledge of these players' style of play, not derived from real
play-by-play statistics. See scripts/build_players_seed.py for the same
disclosure on the current-player pool this mirrors.

Usage:
    python3 scripts/build_players_alltime_seed.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from engine.axis_position import score_axis_coordinates  # noqa: E402
from scripts.build_players_seed import derive_body_measurements  # noqa: E402
from scripts.mock_answers import mock_axis_answers, mock_skill_answers  # noqa: E402

_BASIS = "2K 公開歷史/All-Time 卡屬性數值換算百分位推算,非真實比賽數據推導"
_BASIS_NO_2K_CARD = "沒有 2K 歷史卡(未取得授權),改用公開球評印象手動估算,再套進同一套百分位池子,非真實數據推導"

PLAYERS = [
    {
        "id": "michael_jordan", "name": "Michael Jordan", "team": "1996",
        "coordinates": {"A": 81, "B1": 93, "B2": 96, "C1": 93, "C2": 29, "D": 83},
        "body": {"height_cm": 198, "wingspan_cm": 207},
        "notable_traits": ["中距離急停跳投致命", "一對一單防很難被過", "轉換快攻終結能力強"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "low",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "kobe_bryant", "name": "Kobe Bryant", "team": "2006",
        "coordinates": {"A": 82, "B1": 82, "B2": 50, "C1": 64, "C2": 33, "D": 91},
        "body": {"height_cm": 198, "wingspan_cm": 200},
        "notable_traits": ["中距離跟後仰跳投多樣", "高強度訓練出來的得分手感", "關鍵時刻單打選擇多"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "magic_johnson", "name": "Magic Johnson", "team": "1987",
        "coordinates": {"A": 97, "B1": 69, "B2": 88, "C1": 68, "C2": 56, "D": 87},
        "body": {"height_cm": 206, "wingspan_cm": 210},
        "notable_traits": ["大體型控衛視野極佳", "快攻推進傳球華麗", "禁區低位單打技巧不錯"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "low",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "larry_bird", "name": "Larry Bird", "team": "1986",
        "coordinates": {"A": 54, "B1": 99, "B2": 93, "C1": 80, "C2": 24, "D": 8},
        "body": {"height_cm": 206, "wingspan_cm": 206},
        "notable_traits": ["外線出手範圍極廣", "傳導視野好", "比賽閱讀能力出色"],
        "signature_skill_id": "perimeter_shooting",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "wilt_chamberlain", "name": "Wilt Chamberlain", "team": "1967",
        "coordinates": {"A": 7, "B1": 4, "B2": 80, "C1": 58, "C2": 98, "D": 33},
        "body": {"height_cm": 216, "wingspan_cm": 229},
        "notable_traits": ["禁區得分效率驚人", "籃板控制力強", "體能天賦聯盟史上頂級"],
        "signature_skill_id": "offensive_rebounding",
        "learnability_flag": "low",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "bill_russell", "name": "Bill Russell", "team": "1962",
        "coordinates": {"A": 16, "B1": 3, "B2": 76, "C1": 76, "C2": 100, "D": 87},
        "body": {"height_cm": 208, "wingspan_cm": 221},
        "notable_traits": ["護框覆蓋範圍大", "籃板卡位意識強", "團隊防守指揮官"],
        "signature_skill_id": "rim_protection",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "kareem_abdul_jabbar", "name": "Kareem Abdul-Jabbar", "team": "1977",
        "coordinates": {"A": 12, "B1": 10, "B2": 93, "C1": 36, "C2": 90, "D": 3},
        "body": {"height_cm": 218, "wingspan_cm": 226},
        "notable_traits": ["天勾出手難以防守", "禁區腳步細膩", "生涯得分效率長年穩定"],
        "signature_skill_id": "post_up",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "oscar_robertson", "name": "Oscar Robertson", "team": "1964",
        "coordinates": {"A": 96, "B1": 96, "B2": 55, "C1": 76, "C2": 21, "D": 98},
        "body": {"height_cm": 196, "wingspan_cm": 201},
        "notable_traits": ["場均大三元等級的全面性", "持球推進穩定", "中距離出手可靠"],
        "signature_skill_id": "decision_making_turnover_control",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "jerry_west", "name": "Jerry West", "team": "1965",
        "coordinates": {"A": 86, "B1": 87, "B2": 41, "C1": 96, "C2": 12, "D": 83},
        "body": {"height_cm": 188, "wingspan_cm": 193},
        "notable_traits": ["關鍵時刻得分能力強", "中距離跳投穩定", "持球推進效率高"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "elgin_baylor", "name": "Elgin Baylor", "team": "1962",
        "coordinates": {"A": 66, "B1": 45, "B2": 80, "C1": 68, "C2": 52, "D": 89},
        "body": {"height_cm": 196, "wingspan_cm": 201},
        "notable_traits": ["滯空能力領先時代", "轉換終結能力強", "籃板意識好"],
        "signature_skill_id": "transition_finishing",
        "learnability_flag": "low",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "julius_erving", "name": "Julius Erving", "team": "1980",
        "coordinates": {"A": 72, "B1": 36, "B2": 66, "C1": 80, "C2": 52, "D": 95},
        "body": {"height_cm": 198, "wingspan_cm": 209},
        "notable_traits": ["滯空拉桿終結能力強", "轉換快攻觀賞性高", "運動能力領先同時代"],
        "signature_skill_id": "transition_finishing",
        "learnability_flag": "low",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "moses_malone", "name": "Moses Malone", "team": "1983",
        "coordinates": {"A": 8, "B1": 13, "B2": 98, "C1": 76, "C2": 96, "D": 51},
        "body": {"height_cm": 208, "wingspan_cm": 216},
        "notable_traits": ["前場籃板二次進攻能力頂級", "禁區腳步紮實", "體能耐操"],
        "signature_skill_id": "offensive_rebounding",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "isiah_thomas", "name": "Isiah Thomas", "team": "1990",
        "coordinates": {"A": 99, "B1": 43, "B2": 3, "C1": 74, "C2": 5, "D": 97},
        "body": {"height_cm": 185, "wingspan_cm": 188},
        "notable_traits": ["控場能力強", "關鍵時刻得分手感好", "持球推進速度快"],
        "signature_skill_id": "pick_and_roll_ball_handling",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "george_gervin", "name": "George Gervin", "team": "1980",
        "coordinates": {"A": 58, "B1": 79, "B2": 67, "C1": 85, "C2": 60, "D": 98},
        "body": {"height_cm": 201, "wingspan_cm": 208},
        "notable_traits": ["中距離指尖投籃出手柔和", "得分手段多樣", "單打效率高"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "dominique_wilkins", "name": "Dominique Wilkins", "team": "1986",
        "coordinates": {"A": 41, "B1": 38, "B2": 52, "C1": 68, "C2": 24, "D": 87},
        "body": {"height_cm": 203, "wingspan_cm": 209},
        "notable_traits": ["扣籃能力聯盟頂級", "轉換終結爆發力強", "得分手感好"],
        "signature_skill_id": "transition_finishing",
        "learnability_flag": "low",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "charles_barkley", "name": "Charles Barkley", "team": "1993",
        "coordinates": {"A": 20, "B1": 13, "B2": 71, "C1": 32, "C2": 52, "D": 80},
        "body": {"height_cm": 198, "wingspan_cm": 213},
        "notable_traits": ["籃板卡位意識強", "禁區對抗能力好", "體型不高但終結效率高"],
        "signature_skill_id": "offensive_rebounding",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS_NO_2K_CARD,
    },
    {
        "id": "hakeem_olajuwon", "name": "Hakeem Olajuwon", "team": "1994",
        "coordinates": {"A": 15, "B1": 17, "B2": 98, "C1": 39, "C2": 95, "D": 27},
        "body": {"height_cm": 213, "wingspan_cm": 224},
        "notable_traits": ["禁區腳步全聯盟頂級", "護框跟協防都強", "轉身終結技巧細膩"],
        "signature_skill_id": "post_up",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "karl_malone", "name": "Karl Malone", "team": "1997",
        "coordinates": {"A": 35, "B1": 24, "B2": 98, "C1": 36, "C2": 82, "D": 66},
        "body": {"height_cm": 206, "wingspan_cm": 213},
        "notable_traits": ["擋拆順下終結穩定", "禁區對抗強悍", "生涯效率高且耐操"],
        "signature_skill_id": "pick_and_roll_ball_handling",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "john_stockton", "name": "John Stockton", "team": "1997",
        "coordinates": {"A": 94, "B1": 72, "B2": 1, "C1": 92, "C2": 9, "D": 12},
        "body": {"height_cm": 185, "wingspan_cm": 188},
        "notable_traits": ["擋拆傳導視野聯盟頂級", "失誤控制能力好", "持球推進穩定"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "david_robinson", "name": "David Robinson", "team": "1995",
        "coordinates": {"A": 13, "B1": 10, "B2": 76, "C1": 22, "C2": 94, "D": 48},
        "body": {"height_cm": 216, "wingspan_cm": 224},
        "notable_traits": ["護框覆蓋範圍大", "運動能力領先同位置", "禁區得分效率高"],
        "signature_skill_id": "rim_protection",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "scottie_pippen", "name": "Scottie Pippen", "team": "1996",
        "coordinates": {"A": 90, "B1": 81, "B2": 55, "C1": 95, "C2": 69, "D": 90},
        "body": {"height_cm": 203, "wingspan_cm": 224},
        "notable_traits": ["換防跟防能力全聯盟頂級", "持球推進穩定", "轉換防守到進攻速度快"],
        "signature_skill_id": "perimeter_switch_defense",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "patrick_ewing", "name": "Patrick Ewing", "team": "1990",
        "coordinates": {"A": 1, "B1": 14, "B2": 86, "C1": 9, "C2": 88, "D": 19},
        "body": {"height_cm": 213, "wingspan_cm": 224},
        "notable_traits": ["中距離跳投穩定", "護框能力強", "禁區對抗強悍"],
        "signature_skill_id": "rim_protection",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "clyde_drexler", "name": "Clyde Drexler", "team": "1992",
        "coordinates": {"A": 59, "B1": 62, "B2": 88, "C1": 88, "C2": 49, "D": 62},
        "body": {"height_cm": 198, "wingspan_cm": 206},
        "notable_traits": ["轉換快攻推進速度快", "運動能力全面", "得分手段多樣"],
        "signature_skill_id": "transition_finishing",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "reggie_miller", "name": "Reggie Miller", "team": "1995",
        "coordinates": {"A": 17, "B1": 95, "B2": 0, "C1": 25, "C2": 0, "D": 11},
        "body": {"height_cm": 201, "wingspan_cm": 206},
        "notable_traits": ["無球跑動接球投籃效率頂級", "利用掩護出手節奏好", "關鍵時刻三分穩定"],
        "signature_skill_id": "off_ball_movement",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS_NO_2K_CARD,
    },
    {
        "id": "gary_payton", "name": "Gary Payton", "team": "1996",
        "coordinates": {"A": 97, "B1": 40, "B2": 58, "C1": 100, "C2": 26, "D": 71},
        "body": {"height_cm": 193, "wingspan_cm": 196},
        "notable_traits": ["一對一單防壓迫性強", "持球推進穩定", "防守專注力極高"],
        "signature_skill_id": "on_ball_perimeter_defense",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "dennis_rodman", "name": "Dennis Rodman", "team": "1996",
        "coordinates": {"A": 35, "B1": 5, "B2": 50, "C1": 57, "C2": 78, "D": 78},
        "body": {"height_cm": 201, "wingspan_cm": 213},
        "notable_traits": ["籃板卡位意識聯盟史上頂級", "協防補位判斷好", "防守專注力極高"],
        "signature_skill_id": "defensive_rebounding_boxout",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "chris_webber", "name": "Chris Webber", "team": "1999",
        "coordinates": {"A": 45, "B1": 40, "B2": 60, "C1": 73, "C2": 83, "D": 91},
        "body": {"height_cm": 208, "wingspan_cm": 216},
        "notable_traits": ["高位傳導視野不錯", "禁區腳步柔軟", "轉換終結能力好"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "kevin_garnett", "name": "Kevin Garnett", "team": "2004",
        "coordinates": {"A": 37, "B1": 59, "B2": 98, "C1": 51, "C2": 91, "D": 95},
        "body": {"height_cm": 211, "wingspan_cm": 221},
        "notable_traits": ["協防補位判斷聯盟頂級", "中距離跳投穩定", "防守溝通指揮強"],
        "signature_skill_id": "help_defense_rotation",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "tim_duncan", "name": "Tim Duncan", "team": "2003",
        "coordinates": {"A": 41, "B1": 43, "B2": 95, "C1": 78, "C2": 99, "D": 86},
        "body": {"height_cm": 211, "wingspan_cm": 224},
        "notable_traits": ["擋拆後中距離出手穩定", "護框跟協防判斷好", "籃板卡位意識強"],
        "signature_skill_id": "pick_and_roll_ball_handling",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "shaquille_oneal", "name": "Shaquille O'Neal", "team": "2000",
        "coordinates": {"A": 25, "B1": 1, "B2": 98, "C1": 54, "C2": 96, "D": 93},
        "body": {"height_cm": 216, "wingspan_cm": 226},
        "notable_traits": ["禁區終結力量壓制性強", "籃板卡位能力強", "體能天賦聯盟史上頂級"],
        "signature_skill_id": "post_up",
        "learnability_flag": "low",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "allen_iverson", "name": "Allen Iverson", "team": "2001",
        "coordinates": {"A": 98, "B1": 64, "B2": 47, "C1": 97, "C2": 10, "D": 99},
        "body": {"height_cm": 183, "wingspan_cm": 185},
        "notable_traits": ["面框第一步過人速度快", "小體型高強度得分手", "持球推進突破能力強"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "low",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "steve_nash", "name": "Steve Nash", "team": "2005",
        "coordinates": {"A": 99, "B1": 96, "B2": 80, "C1": 51, "C2": 2, "D": 79},
        "body": {"height_cm": 191, "wingspan_cm": 191},
        "notable_traits": ["擋拆持球判斷聯盟頂級", "三分出手效率高", "失誤控制能力好"],
        "signature_skill_id": "pick_and_roll_ball_handling",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "dirk_nowitzki", "name": "Dirk Nowitzki", "team": "2007",
        "coordinates": {"A": 32, "B1": 98, "B2": 96, "C1": 16, "C2": 67, "D": 1},
        "body": {"height_cm": 213, "wingspan_cm": 213},
        "notable_traits": ["金雞獨立跳投難以防守", "外線出手穩定", "單打腳步細膩"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "manu_ginobili", "name": "Manu Ginobili", "team": "2005",
        "coordinates": {"A": 79, "B1": 66, "B2": 68, "C1": 71, "C2": 33, "D": 61},
        "body": {"height_cm": 198, "wingspan_cm": 201},
        "notable_traits": ["歐洲步終結技巧細膩", "替補奇兵效率高", "傳導視野不錯"],
        "signature_skill_id": "transition_finishing",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "tony_parker", "name": "Tony Parker", "team": "2007",
        "coordinates": {"A": 100, "B1": 28, "B2": 91, "C1": 92, "C2": 5, "D": 100},
        "body": {"height_cm": 188, "wingspan_cm": 188},
        "notable_traits": ["擋拆持球推進速度快", "中距離出手穩定", "轉換終結效率高"],
        "signature_skill_id": "pick_and_roll_ball_handling",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "vince_carter", "name": "Vince Carter", "team": "2000",
        "coordinates": {"A": 77, "B1": 75, "B2": 50, "C1": 57, "C2": 53, "D": 91},
        "body": {"height_cm": 198, "wingspan_cm": 203},
        "notable_traits": ["扣籃能力聯盟頂級", "轉換終結爆發力強", "得分手感好"],
        "signature_skill_id": "transition_finishing",
        "learnability_flag": "low",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "tracy_mcgrady", "name": "Tracy McGrady", "team": "2003",
        "coordinates": {"A": 75, "B1": 41, "B2": 61, "C1": 51, "C2": 24, "D": 89},
        "body": {"height_cm": 203, "wingspan_cm": 213},
        "notable_traits": ["單打得分手段多樣", "運動能力全面", "關鍵時刻爆發得分能力強"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "yao_ming", "name": "Yao Ming", "team": "2006",
        "coordinates": {"A": 17, "B1": 24, "B2": 93, "C1": 32, "C2": 80, "D": 0},
        "body": {"height_cm": 229, "wingspan_cm": 234},
        "notable_traits": ["禁區腳步柔軟", "中距離跳投穩定", "護框覆蓋範圍大"],
        "signature_skill_id": "post_up",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "jason_kidd", "name": "Jason Kidd", "team": "2002",
        "coordinates": {"A": 99, "B1": 47, "B2": 24, "C1": 99, "C2": 2, "D": 99},
        "body": {"height_cm": 193, "wingspan_cm": 201},
        "notable_traits": ["傳導視野聯盟頂級", "快攻推進判斷好", "籃板意識不錯"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "paul_pierce", "name": "Paul Pierce", "team": "2008",
        "coordinates": {"A": 55, "B1": 81, "B2": 83, "C1": 58, "C2": 29, "D": 21},
        "body": {"height_cm": 201, "wingspan_cm": 206},
        "notable_traits": ["單打腳步細膩", "中距離跟三分都穩定", "關鍵時刻得分能力強"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "ray_allen", "name": "Ray Allen", "team": "2008",
        "coordinates": {"A": 55, "B1": 97, "B2": 36, "C1": 47, "C2": 8, "D": 38},
        "body": {"height_cm": 196, "wingspan_cm": 196},
        "notable_traits": ["定點三分出手機制教科書等級", "無球跑動效率高", "罰球穩定"],
        "signature_skill_id": "perimeter_shooting",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "grant_hill", "name": "Grant Hill", "team": "1997",
        "coordinates": {"A": 75, "B1": 54, "B2": 95, "C1": 87, "C2": 10, "D": 99},
        "body": {"height_cm": 203, "wingspan_cm": 206},
        "notable_traits": ["持球推進全面", "轉換終結能力好", "防守肯拚"],
        "signature_skill_id": "transition_finishing",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "penny_hardaway", "name": "Penny Hardaway", "team": "1996",
        "coordinates": {"A": 85, "B1": 41, "B2": 71, "C1": 74, "C2": 12, "D": 71},
        "body": {"height_cm": 201, "wingspan_cm": 211},
        "notable_traits": ["大體型控衛傳導視野好", "單打得分手段多樣", "轉換推進速度快"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "alonzo_mourning", "name": "Alonzo Mourning", "team": "1999",
        "coordinates": {"A": 6, "B1": 15, "B2": 83, "C1": 78, "C2": 98, "D": 8},
        "body": {"height_cm": 208, "wingspan_cm": 218},
        "notable_traits": ["護框意志力強", "禁區對抗強悍", "協防補位判斷好"],
        "signature_skill_id": "rim_protection",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "dikembe_mutombo", "name": "Dikembe Mutombo", "team": "2001",
        "coordinates": {"A": 3, "B1": 2, "B2": 1, "C1": 32, "C2": 93, "D": 4},
        "body": {"height_cm": 218, "wingspan_cm": 236},
        "notable_traits": ["護框覆蓋範圍聯盟史上頂級", "籃板卡位意識強", "協防威懾力強"],
        "signature_skill_id": "rim_protection",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "chris_bosh", "name": "Chris Bosh", "team": "2010",
        "coordinates": {"A": 21, "B1": 72, "B2": 80, "C1": 39, "C2": 53, "D": 18},
        "body": {"height_cm": 211, "wingspan_cm": 213},
        "notable_traits": ["中距離出手穩定", "擋拆順下終結效率高", "協防補位判斷好"],
        "signature_skill_id": "pick_and_roll_ball_handling",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "amare_stoudemire", "name": "Amar'e Stoudemire", "team": "2007",
        "coordinates": {"A": 14, "B1": 19, "B2": 63, "C1": 47, "C2": 69, "D": 38},
        "body": {"height_cm": 208, "wingspan_cm": 218},
        "notable_traits": ["擋拆順下終結爆發力強", "禁區對抗能力好", "轉換終結效率高"],
        "signature_skill_id": "pick_and_roll_ball_handling",
        "learnability_flag": "low",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "pau_gasol", "name": "Pau Gasol", "team": "2009",
        "coordinates": {"A": 15, "B1": 67, "B2": 90, "C1": 54, "C2": 84, "D": 2},
        "body": {"height_cm": 213, "wingspan_cm": 224},
        "notable_traits": ["高位傳導視野不錯", "禁區腳步柔軟", "中距離出手穩定"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "marc_gasol", "name": "Marc Gasol", "team": "2013",
        "coordinates": {"A": 11, "B1": 17, "B2": 77, "C1": 51, "C2": 77, "D": 1},
        "body": {"height_cm": 213, "wingspan_cm": 221},
        "notable_traits": ["高位傳導視野聯盟頂級", "協防補位判斷好", "中距離出手穩定"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "carmelo_anthony", "name": "Carmelo Anthony", "team": "2013",
        "coordinates": {"A": 78, "B1": 50, "B2": 41, "C1": 85, "C2": 66, "D": 89},
        "body": {"height_cm": 203, "wingspan_cm": 211},
        "notable_traits": ["單打腳步細膩", "中距離跟三分出手穩定", "得分手感好"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "elton_brand", "name": "Elton Brand", "team": "2006",
        "coordinates": {"A": 5, "B1": 40, "B2": 87, "C1": 83, "C2": 84, "D": 3},
        "body": {"height_cm": 206, "wingspan_cm": 218},
        "notable_traits": ["禁區腳步紮實", "籃板卡位意識好", "協防補位判斷不錯"],
        "signature_skill_id": "post_up",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "chauncey_billups", "name": "Chauncey Billups", "team": "2004",
        "coordinates": {"A": 87, "B1": 67, "B2": 14, "C1": 57, "C2": 2, "D": 83},
        "body": {"height_cm": 191, "wingspan_cm": 196},
        "notable_traits": ["關鍵時刻得分能力強", "擋拆持球判斷穩定", "三分出手可靠"],
        "signature_skill_id": "pick_and_roll_ball_handling",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "ben_wallace", "name": "Ben Wallace", "team": "2004",
        "coordinates": {"A": 6, "B1": 0, "B2": 9, "C1": 83, "C2": 96, "D": 56},
        "body": {"height_cm": 201, "wingspan_cm": 218},
        "notable_traits": ["護框跟籃板卡位聯盟頂級", "協防補位判斷好", "防守專注力極高"],
        "signature_skill_id": "defensive_rebounding_boxout",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "rasheed_wallace", "name": "Rasheed Wallace", "team": "2004",
        "coordinates": {"A": 16, "B1": 32, "B2": 52, "C1": 42, "C2": 82, "D": 40},
        "body": {"height_cm": 208, "wingspan_cm": 218},
        "notable_traits": ["內外都能出手", "協防補位判斷好", "換防彈性不錯"],
        "signature_skill_id": "help_defense_rotation",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS_NO_2K_CARD,
    },
    {
        "id": "baron_davis", "name": "Baron Davis", "team": "2007",
        "coordinates": {"A": 93, "B1": 35, "B2": 4, "C1": 97, "C2": 12, "D": 91},
        "body": {"height_cm": 188, "wingspan_cm": 196},
        "notable_traits": ["持球推進爆發力強", "三分出手範圍廣", "轉換終結能力好"],
        "signature_skill_id": "pick_and_roll_ball_handling",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "steve_francis", "name": "Steve Francis", "team": "2002",
        "coordinates": {"A": 84, "B1": 57, "B2": 22, "C1": 92, "C2": 45, "D": 91},
        "body": {"height_cm": 188, "wingspan_cm": 196},
        "notable_traits": ["持球突破爆發力強", "轉換終結能力好", "單打得分手段多樣"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "low",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "antawn_jamison", "name": "Antawn Jamison", "team": "2004",
        "coordinates": {"A": 26, "B1": 48, "B2": 60, "C1": 16, "C2": 64, "D": 21},
        "body": {"height_cm": 203, "wingspan_cm": 206},
        "notable_traits": ["中距離出手手感獨特", "籃板卡位意識好", "轉換終結效率高"],
        "signature_skill_id": "offensive_rebounding",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "shawn_marion", "name": "Shawn Marion", "team": "2005",
        "coordinates": {"A": 28, "B1": 69, "B2": 69, "C1": 83, "C2": 60, "D": 33},
        "body": {"height_cm": 201, "wingspan_cm": 213},
        "notable_traits": ["換防彈性好", "轉換終結效率高", "籃板意識不錯"],
        "signature_skill_id": "perimeter_switch_defense",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "rip_hamilton", "name": "Rip Hamilton", "team": "2004",
        "coordinates": {"A": 61, "B1": 83, "B2": 29, "C1": 60, "C2": 8, "D": 21},
        "body": {"height_cm": 198, "wingspan_cm": 198},
        "notable_traits": ["無球跑動效率聯盟頂級", "利用掩護出手節奏好", "中距離出手穩定"],
        "signature_skill_id": "off_ball_movement",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "bill_walton", "name": "Bill Walton", "team": "1977",
        "coordinates": {"A": 25, "B1": 8, "B2": 90, "C1": 71, "C2": 96, "D": 4},
        "body": {"height_cm": 211, "wingspan_cm": 218},
        "notable_traits": ["高位傳導視野出色", "護框能力強", "團隊籃球核心"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "artis_gilmore", "name": "Artis Gilmore", "team": "1978",
        "coordinates": {"A": 7, "B1": 9, "B2": 94, "C1": 30, "C2": 97, "D": 71},
        "body": {"height_cm": 218, "wingspan_cm": 226},
        "notable_traits": ["禁區終結效率高", "籃板卡位意識強", "護框覆蓋範圍大"],
        "signature_skill_id": "rim_protection",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "walt_frazier", "name": "Walt Frazier", "team": "1970",
        "coordinates": {"A": 81, "B1": 41, "B2": 23, "C1": 99, "C2": 19, "D": 76},
        "body": {"height_cm": 191, "wingspan_cm": 196},
        "notable_traits": ["一對一單防能力強", "持球推進穩定", "關鍵時刻得分手感好"],
        "signature_skill_id": "on_ball_perimeter_defense",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "willis_reed", "name": "Willis Reed", "team": "1970",
        "coordinates": {"A": 11, "B1": 11, "B2": 60, "C1": 20, "C2": 87, "D": 7},
        "body": {"height_cm": 206, "wingspan_cm": 211},
        "notable_traits": ["禁區對抗強悍", "中距離出手穩定", "團隊防守指揮官"],
        "signature_skill_id": "post_up",
        "learnability_flag": "medium",
        "_estimate_basis": _BASIS,
    },
    {
        "id": "earl_monroe", "name": "Earl Monroe", "team": "1969",
        "coordinates": {"A": 86, "B1": 66, "B2": 6, "C1": 87, "C2": 5, "D": 68},
        "body": {"height_cm": 191, "wingspan_cm": 193},
        "notable_traits": ["單打腳步花俏難防", "持球創造出手機會能力強", "中距離出手穩定"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "high",
        "_estimate_basis": _BASIS,
    },
]


def main():
    questions = json.load(open(ROOT / "data" / "zh" / "題庫.json", encoding="utf-8"))
    axis_questions = questions["axis_positioning"]
    skill_questions = questions["skill_behavior"]
    skills_by_id = {
        s["id"]: s for s in json.load(open(ROOT / "data" / "zh" / "技能.json", encoding="utf-8"))["skills"]
    }

    for player in PLAYERS:
        target_coordinates = player["coordinates"]
        mock_axis = mock_axis_answers(axis_questions, target_coordinates)
        player["coordinates"] = score_axis_coordinates(axis_questions, mock_axis)
        player["mock_axis_answers"] = mock_axis
        player["mock_skill_answers"] = mock_skill_answers(
            skill_questions, skills_by_id, player["coordinates"], player["signature_skill_id"]
        )
        player["body"].update(
            derive_body_measurements(
                player["body"]["height_cm"], player["body"]["wingspan_cm"], player["coordinates"]
            )
        )

    payload = {
        "_description": (
            "歷史球員種子資料(退役、廣為人知的球星,涵蓋 1960s-2010s)。跟"
            "data/players.json(現役球員池)同一套 schema,是「歷史球員模板"
            "(All-time)」模式用的資料來源。同樣是手動估算,不是真實數據推導"
            "的結果(每位球員的 _estimate_basis 都有說明)。\"team\" 欄位放的"
            "是代表年份(字串),不是球隊縮寫。v2(2026-09-11)：coordinates 是用"
            "PLAYERS 常數裡的目標座標反推成模擬作答(mock_axis_answers)、再用"
            "score_axis_coordinates 算出來的,不是直接手打的座標;"
            "mock_skill_answers 是同樣邏輯推算的 15 題技能行為模擬作答。body"
            "欄位裡的 height_cm/wingspan_cm 是手動估算,其餘四項是用跟現役球員"
            "池一樣的公式(scripts/build_players_seed.py 的"
            "derive_body_measurements)推算出來的。"
        ),
        "_editable_fields": (
            "整份 players 清單都可以改,規則跟 data/players.json 一樣——調"
            "coordinates 改變座標,調 notable_traits/signature_skill_id 改變"
            "輸出文案,調 learnability_flag(low/medium/high)。id 一旦被別的"
            "地方引用就不要改。coordinates/mock_axis_answers/mock_skill_"
            "answers 是 build 產物,不要手改——要調整就改 PLAYERS 常數裡的"
            "目標座標,重跑腳本重新產生。"
        ),
        "players": PLAYERS,
    }
    output_path = ROOT / "data" / "zh" / "歷史球員.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"wrote {len(PLAYERS)} players to {output_path}")


if __name__ == "__main__":
    main()
