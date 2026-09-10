#!/usr/bin/env python3
# 用途：手動估算 50 位現役球員的四軸座標跟其他資料,產生 data/players.json。
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
    # 2026-09-11 擴充:原本 20 人的 signature_skill_id 全部只落在最早的 5 項
    # 關鍵技能上,代表擴充後的 10 項新技能(post_up 等)在配對輸出裡永遠用不到
    # ——「最值得學的一件事」只會一直套用通用句型。下面 30 人特別涵蓋這 10 項
    # 技能各至少 2 位,讓技能庫擴充真的反映在配對結果上,同時把球員池從 20 人
    # 擴大到 50 人。
    {
        "id": "joel_embiid", "name": "Joel Embiid", "team": "PHI",
        "coordinates": {"A": 55, "B": 25, "C": 45, "D": 70},
        "body": {"height_cm": 213, "wingspan_cm": 229},
        "notable_traits": ["背框腳步細膩", "面框跳投穩定", "護框覆蓋佳"],
        "signature_skill_id": "post_up",
        "learnability_flag": "low",
        "_estimate_basis": "公開球評印象 + 臂展等公開身體數據,手動估算,非真實數據推導",
    },
    {
        "id": "karl_anthony_towns", "name": "Karl-Anthony Towns", "team": "NYK",
        "coordinates": {"A": 45, "B": 55, "C": 25, "D": 45},
        "body": {"height_cm": 213, "wingspan_cm": 224},
        "notable_traits": ["背框腳步柔軟", "外線出手穩定", "換防彈性一般"],
        "signature_skill_id": "post_up",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "tyrese_haliburton", "name": "Tyrese Haliburton", "team": "IND",
        "coordinates": {"A": 80, "B": 50, "C": 35, "D": 40},
        "body": {"height_cm": 196, "wingspan_cm": 196},
        "notable_traits": ["擋拆傳導視野極佳", "節奏掌控好", "跳投穩定"],
        "signature_skill_id": "pick_and_roll_ball_handling",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "trae_young", "name": "Trae Young", "team": "ATL",
        "coordinates": {"A": 85, "B": 55, "C": 20, "D": 35},
        "body": {"height_cm": 183, "wingspan_cm": 185},
        "notable_traits": ["擋拆製造犯規能力強", "遠距離出手穩定", "傳導視野好"],
        "signature_skill_id": "pick_and_roll_ball_handling",
        "learnability_flag": "low",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "desmond_bane", "name": "Desmond Bane", "team": "MEM",
        "coordinates": {"A": 35, "B": 75, "C": 35, "D": 40},
        "body": {"height_cm": 196, "wingspan_cm": 203},
        "notable_traits": ["無球跑動效率高", "定點三分穩定", "擋拆後外拉投籃"],
        "signature_skill_id": "off_ball_movement",
        "learnability_flag": "high",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "duncan_robinson", "name": "Duncan Robinson", "team": "MIA",
        "coordinates": {"A": 15, "B": 90, "C": 20, "D": 20},
        "body": {"height_cm": 201, "wingspan_cm": 201},
        "notable_traits": ["純射手型跑動", "利用掩護效率頂級", "出手速度快"],
        "signature_skill_id": "off_ball_movement",
        "learnability_flag": "high",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "pascal_siakam", "name": "Pascal Siakam", "team": "IND",
        "coordinates": {"A": 55, "B": 35, "C": 40, "D": 75},
        "body": {"height_cm": 203, "wingspan_cm": 226},
        "notable_traits": ["轉換終結能力強", "面框腳步好", "中距離跳投穩定"],
        "signature_skill_id": "transition_finishing",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象 + 臂展等公開身體數據,手動估算,非真實數據推導",
    },
    {
        "id": "herbert_jones", "name": "Herbert Jones", "team": "NOP",
        "coordinates": {"A": 25, "B": 30, "C": 70, "D": 75},
        "body": {"height_cm": 198, "wingspan_cm": 213},
        "notable_traits": ["快攻終結效率高", "貼身跟防能力強", "防守覆蓋範圍大"],
        "signature_skill_id": "transition_finishing",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象 + 臂展等公開身體數據,手動估算,非真實數據推導",
    },
    {
        "id": "damian_lillard", "name": "Damian Lillard", "team": "MIL",
        "coordinates": {"A": 75, "B": 65, "C": 25, "D": 35},
        "body": {"height_cm": 188, "wingspan_cm": 196},
        "notable_traits": ["罰球穩定", "遠距離出手果斷", "擋拆持球判斷好"],
        "signature_skill_id": "free_throw_shooting",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "jayson_tatum", "name": "Jayson Tatum", "team": "BOS",
        "coordinates": {"A": 60, "B": 55, "C": 35, "D": 55},
        "body": {"height_cm": 203, "wingspan_cm": 213},
        "notable_traits": ["罰球穩定", "面框單打腳步好", "中距離跳投多樣"],
        "signature_skill_id": "free_throw_shooting",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "clint_capela", "name": "Clint Capela", "team": "ATL",
        "coordinates": {"A": 15, "B": 10, "C": 25, "D": 65},
        "body": {"height_cm": 208, "wingspan_cm": 226},
        "notable_traits": ["前場籃板嗅覺佳", "擋拆順下終結", "護框補位"],
        "signature_skill_id": "offensive_rebounding",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象 + 臂展等公開身體數據,手動估算,非真實數據推導",
    },
    {
        "id": "steven_adams", "name": "Steven Adams", "team": "HOU",
        "coordinates": {"A": 15, "B": 5, "C": 20, "D": 55},
        "body": {"height_cm": 211, "wingspan_cm": 226},
        "notable_traits": ["前場籃板卡位兇悍", "卡位意識強", "掩護扎實"],
        "signature_skill_id": "offensive_rebounding",
        "learnability_flag": "high",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "marcus_smart", "name": "Marcus Smart", "team": "WAS",
        "coordinates": {"A": 45, "B": 35, "C": 80, "D": 50},
        "body": {"height_cm": 191, "wingspan_cm": 201},
        "notable_traits": ["一對一單防兇悍", "抄截嗅覺強", "防守溝通指揮"],
        "signature_skill_id": "on_ball_perimeter_defense",
        "learnability_flag": "low",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "lu_dort", "name": "Lu Dort", "team": "OKC",
        "coordinates": {"A": 20, "B": 35, "C": 85, "D": 55},
        "body": {"height_cm": 193, "wingspan_cm": 201},
        "notable_traits": ["一對一單防強悍", "體格對抗能力強", "貼身跟防穩定"],
        "signature_skill_id": "on_ball_perimeter_defense",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "derrick_white", "name": "Derrick White", "team": "BOS",
        "coordinates": {"A": 45, "B": 45, "C": 70, "D": 45},
        "body": {"height_cm": 193, "wingspan_cm": 196},
        "notable_traits": ["協防補位判斷好", "換防彈性大", "外線出手穩定"],
        "signature_skill_id": "help_defense_rotation",
        "learnability_flag": "high",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "dorian_finney_smith", "name": "Dorian Finney-Smith", "team": "LAL",
        "coordinates": {"A": 20, "B": 50, "C": 65, "D": 40},
        "body": {"height_cm": 198, "wingspan_cm": 211},
        "notable_traits": ["協防補位到位", "3&D 定位清楚", "無球跑動投射穩定"],
        "signature_skill_id": "help_defense_rotation",
        "learnability_flag": "high",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "jarrett_allen", "name": "Jarrett Allen", "team": "CLE",
        "coordinates": {"A": 15, "B": 10, "C": 35, "D": 55},
        "body": {"height_cm": 211, "wingspan_cm": 226},
        "notable_traits": ["防守籃板卡位扎實", "擋拆順下終結", "護框補位"],
        "signature_skill_id": "defensive_rebounding_boxout",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象 + 臂展等公開身體數據,手動估算,非真實數據推導",
    },
    {
        "id": "nic_claxton", "name": "Nic Claxton", "team": "BKN",
        "coordinates": {"A": 10, "B": 10, "C": 30, "D": 60},
        "body": {"height_cm": 211, "wingspan_cm": 224},
        "notable_traits": ["防守籃板積極", "護框覆蓋不錯", "轉換終結速度快"],
        "signature_skill_id": "defensive_rebounding_boxout",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "josh_hart", "name": "Josh Hart", "team": "NYK",
        "coordinates": {"A": 50, "B": 35, "C": 40, "D": 45},
        "body": {"height_cm": 196, "wingspan_cm": 203},
        "notable_traits": ["持球推進穩定不失誤", "籃板意識好", "防守肯拚"],
        "signature_skill_id": "decision_making_turnover_control",
        "learnability_flag": "high",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "mike_conley", "name": "Mike Conley", "team": "MIN",
        "coordinates": {"A": 70, "B": 45, "C": 35, "D": 20},
        "body": {"height_cm": 185, "wingspan_cm": 191},
        "notable_traits": ["持球節奏掌控力強", "失誤率極低", "傳導視野好"],
        "signature_skill_id": "decision_making_turnover_control",
        "learnability_flag": "high",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "anthony_edwards", "name": "Anthony Edwards", "team": "MIN",
        "coordinates": {"A": 65, "B": 45, "C": 45, "D": 85},
        "body": {"height_cm": 196, "wingspan_cm": 201},
        "notable_traits": ["面框第一步爆發力強", "轉換終結能力強", "身材對抗優勢"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "low",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "shai_gilgeous_alexander", "name": "Shai Gilgeous-Alexander", "team": "OKC",
        "coordinates": {"A": 75, "B": 40, "C": 35, "D": 45},
        "body": {"height_cm": 198, "wingspan_cm": 208},
        "notable_traits": ["面框第一步變速變向", "中距離終結穩定", "罰球製造能力強"],
        "signature_skill_id": "face_up_first_step",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "myles_turner", "name": "Myles Turner", "team": "MIL",
        "coordinates": {"A": 15, "B": 40, "C": 15, "D": 55},
        "body": {"height_cm": 211, "wingspan_cm": 224},
        "notable_traits": ["護框補位效率高", "外線出手穩定", "轉換速度尚可"],
        "signature_skill_id": "rim_protection",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "brook_lopez", "name": "Brook Lopez", "team": "LAC",
        "coordinates": {"A": 15, "B": 45, "C": 10, "D": 35},
        "body": {"height_cm": 213, "wingspan_cm": 224},
        "notable_traits": ["護框覆蓋範圍大", "外線出手穩定", "卡位意識好"],
        "signature_skill_id": "rim_protection",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "og_anunoby", "name": "OG Anunoby", "team": "NYK",
        "coordinates": {"A": 30, "B": 45, "C": 75, "D": 60},
        "body": {"height_cm": 201, "wingspan_cm": 213},
        "notable_traits": ["換防跟防能力強", "3&D 定位清楚", "體格對抗能力好"],
        "signature_skill_id": "perimeter_switch_defense",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象 + 臂展等公開身體數據,手動估算,非真實數據推導",
    },
    {
        "id": "andrew_wiggins", "name": "Andrew Wiggins", "team": "MIA",
        "coordinates": {"A": 35, "B": 40, "C": 70, "D": 65},
        "body": {"height_cm": 201, "wingspan_cm": 221},
        "notable_traits": ["換防彈性大", "轉換終結能力強", "體型優勢明顯"],
        "signature_skill_id": "perimeter_switch_defense",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象 + 臂展等公開身體數據,手動估算,非真實數據推導",
    },
    {
        "id": "julius_randle", "name": "Julius Randle", "team": "MIN",
        "coordinates": {"A": 65, "B": 35, "C": 30, "D": 50},
        "body": {"height_cm": 203, "wingspan_cm": 213},
        "notable_traits": ["高位策應視野不錯", "面框單打腳步好", "籃板意識強"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "evan_mobley", "name": "Evan Mobley", "team": "CLE",
        "coordinates": {"A": 40, "B": 30, "C": 55, "D": 60},
        "body": {"height_cm": 211, "wingspan_cm": 224},
        "notable_traits": ["高位策應傳導不錯", "護框補位效率高", "轉換速度快"],
        "signature_skill_id": "high_post_playmaking",
        "learnability_flag": "low",
        "_estimate_basis": "公開球評印象 + 臂展等公開身體數據,手動估算,非真實數據推導",
    },
    {
        "id": "cj_mccollum", "name": "CJ McCollum", "team": "WAS",
        "coordinates": {"A": 55, "B": 80, "C": 30, "D": 35},
        "body": {"height_cm": 188, "wingspan_cm": 193},
        "notable_traits": ["中距離急停跳投穩定", "無球跑動投射效率高", "擋拆持球判斷好"],
        "signature_skill_id": "perimeter_shooting",
        "learnability_flag": "medium",
        "_estimate_basis": "公開球評印象,手動估算,非真實數據推導",
    },
    {
        "id": "tyler_herro", "name": "Tyler Herro", "team": "MIA",
        "coordinates": {"A": 60, "B": 75, "C": 25, "D": 35},
        "body": {"height_cm": 196, "wingspan_cm": 196},
        "notable_traits": ["持球投籃節奏獨特", "擋拆後外拉投籃", "罰球穩定"],
        "signature_skill_id": "perimeter_shooting",
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
