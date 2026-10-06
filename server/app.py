# 用途：Flask 後端,三支 API：
#   GET  /api/form-data       給前端渲染問卷用的題庫(六軸定位+身材數值),只回傳必要欄位,
#                             不外洩 axis_relevance/cost_C 等內部校準數字。
#   POST /api/template-results  只吃六軸定位(12題)+ 身材數值(6題,其中身高、
#                             體重必填,其餘 4 題可省略——身高體重是原型分類
#                             體型分數的必要輸入,缺了就直接 400,見
#                             missing_required_body_fields,2026-10 討論),
#                             回傳定位座標、球場定位原型+一句話球探報告、
#                             3 位深度模板、10 人對照表(每筆也帶球員自己的
#                             座標,給前端畫雷達圖疊圖用),以及每位對照球員
#                             的訓練計劃(training_plans,依環境代碼分三組,每組
#                             前 5 項技能,內含難度級別與訓練菜單內容)。
#                             不需要使用者另外作答技能行為題或選環境,環境是
#                             前端在結果頁底部切換,不用重新送出。原型不是直接拿使用者
#                             座標比對 archetypes.json 的原型錨點,而是
#                             把 10 人對照表前 5 位最相似的真人球員各自分類到
#                             最近的原型後投票多數決(engine/archetype.py 的
#                             classify_archetype_by_majority),確保原型標籤
#                             一定跟畫面上顯示的球員一致,不會各算各的
#                             (2026-09-13 討論)。一句話球探報告就是原型的
#                             flavor 文案,不含成長建議——成長建議已經會顯示
#                             在 10 人表#1 的卡片上,headline 再講一次是重複
#                             資訊(2026-10 清掉 build_scouting_report 裡算了
#                             沒用到的 growth 變數時順便把這段註解改成跟現在
#                             的行為一致)。
#                             10 人對照表用六軸+身材一起算距離(沒填身材數值
#                             題就自動退化成純六軸),避免推薦身材差異很大的
#                             球員當模板;3 位深度模板維持純六軸/純身材距離,
#                             刻意不受這個改動影響(第一版本來多加了一張跟 10
#                             人對照表#1 相同的「整體模板」卡,但根本就是重複
#                             資訊,2026-09-11 移除)。
#                             身材裡的身高/體重會先用 percentile_normalize_body
#                             換算成百分位再比,不然幾乎所有使用者都比全部 NBA
#                             球員矮/輕,身材模板永遠是最矮的後衛。天花板的定義
#                             是「D 軸接近、主導差距在某個技能軸
#                             (A/B1/B2/C1/C2)」,是一個身體條件跟你差不多、
#                             但技術更成熟的球員(2026-09-11 重新設計,原本的
#                             反面對照段落因為用同一套「D 軸差距最大」邏輯、
#                             找到的其實是天賦不同的人而非天花板,已經移除)。
#   POST /api/feedback          站內使用意見:1-5 星準確度(選填)+ 50 字以內的文字
#                             (選填),匿名存進 feedback 表,不收聯絡方式。
#   POST /api/site-visit        每次呼叫讓瀏覽人次計數器 +1,回傳遞增後的
#                             總數,給首頁右上角顯示用(2026-09-15 新增,見
#                             docs/superpowers/specs/2026-09-15-visit-counter-design.md)。
#                             計數邏輯在 db.py,沒有 DATABASE_URL 環境變數
#                             時退化成記憶體計數器(本機開發/測試)。
# 三語系統(2026-09 新增):三支 POST API 都吃一個選填的 "lang" 欄位
# ("zh"預設值、"zh-Hans"、"en",見 SUPPORTED_LANGUAGES),決定資料從
# data/zh/、data/zh-Hans/、data/en/ 哪個資料夾讀——三個資料夾裡的五個檔案
# (questions/skills/players/players_alltime/archetypes,各語言檔名不同,見
# DATA_FILENAMES)結構必須完全對應,由 tests/engine/test_i18n_parity.py 把關,
# 所有計算邏輯完全不受語言影響,只有讀哪份文案資料不同。
# /api/template-results 另吃一個選填的 "pool" 欄位("current"預設值 或
# "alltime"),決定球員池要用該語言資料夾下的 players.json(現役)還是
# players_alltime.json(歷史,2026-09-11 新增)。兩份資料同一套 schema,
# 差別只有歷史池的 "team" 欄位放代表年份而不是球隊縮寫,所以 compute_
# template_results 完全不用改,load_data 吃 pool 跟 lang 兩個參數決定讀哪個
# 語言資料夾裡的哪個檔案。
# 同時把 /src/ui 的靜態前端檔案服務出去。**刻意不**把 data/ 整個目錄當靜態
# 檔案服務——data/answers/ 裡面是真實使用者的個人作答資料,不能公開存取。
# 計算邏輯全部重用 src/engine 跟 scripts/run_player_match.py 已經拆出來的函數,這支檔案只做請求解析、資料載入、
# 呼叫、組裝回應,不重寫任何計算規則。
# 可手動調整的變數：DATA_FILENAMES(每個語言資料夾裡,每種資料的檔名,要再加
# 新語言就在這裡加一筆)。
"""Flask app: GET /api/form-data, POST /api/template-results,
static file serving for /src/ui.

Local dev:
    source .venv/bin/activate
    python3 server/app.py
    open http://localhost:5001

(Port 5001, not 5000 -- macOS's AirPlay Receiver squats on 5000 by default
and returns a bare 403 that looks like a server bug but isn't one.)

Deployment: gunicorn app:app (see server/requirements.txt, Render config).
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

from db import increment_visit_count, init_db, save_feedback  # noqa: E402
from engine.archetype import classify_archetype_by_majority, compute_player_sizes  # noqa: E402
from engine.axis_position import score_axis_coordinates  # noqa: E402
from engine.body_fit import (  # noqa: E402
    collect_body_measurements,
    missing_required_body_fields,
    percentile_normalize_body,
)
from engine.player_matching import (  # noqa: E402
    ALLTIME_POOL_STAR_THRESHOLDS,
    CURRENT_POOL_STAR_THRESHOLDS,
    find_body_fit_template,
    find_ceiling_template,
    find_skill_fit_template,
    rank_similar_players_by_style_and_body,
)
from engine.training_plan import build_training_plan, representative_skill_by_axis  # noqa: E402
from scripts.run_player_match import (  # noqa: E402
    build_scouting_report,
    describe_growth_recommendation,
)

UI_DIR = ROOT / "src" / "ui"
TEMPLATE_REQUIRED_FIELDS = ("axis_answers",)
TRAINING_PLAN_TOP_N = 5
SUPPORTED_LANGUAGES = ("zh", "zh-Hans", "en")
POOLS = ("current", "alltime")

DATA_FILENAMES = {
    "zh": {
        "questions": "題庫.json",
        "skills": "技能.json",
        "archetypes": "原型.json",
        "players_current": "球員.json",
        "players_alltime": "歷史球員.json",
        "drills": "訓練菜單.json",
    },
    "zh-Hans": {
        "questions": "题库.json",
        "skills": "技能.json",
        "archetypes": "原型.json",
        "players_current": "球员.json",
        "players_alltime": "历史球员.json",
        "drills": "训练菜单.json",
    },
    "en": {
        "questions": "questions.json",
        "skills": "skills.json",
        "archetypes": "archetypes.json",
        "players_current": "players.json",
        "players_alltime": "players_alltime.json",
        "drills": "drills.json",
    },
}

app = Flask(__name__, static_folder=None)
init_db()


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_data(pool="current", lang="zh"):
    files = DATA_FILENAMES[lang]
    questions = load_json(ROOT / "data" / lang / files["questions"])
    skills = load_json(ROOT / "data" / lang / files["skills"])["skills"]
    players = load_json(ROOT / "data" / lang / files[f"players_{pool}"])["players"]
    return questions, skills, players


def load_archetypes(lang="zh"):
    return load_json(ROOT / "data" / lang / DATA_FILENAMES[lang]["archetypes"])["archetypes"]


def load_drills(lang="zh"):
    """Training drills for one language, grouped by (skill_id, level)."""
    drills = load_json(ROOT / "data" / lang / DATA_FILENAMES[lang]["drills"])["drills"]
    grouped = {}
    for drill in drills:
        grouped.setdefault((drill["skill_id"], drill["level"]), []).append(drill)
    return grouped


def environment_codes():
    return [code for code in ENV_WEIGHTS if not code.startswith("_")]


# 每種聯賽環境對每項技能的倍率 E(data/env_weights.json,只放數字,文字在前端)。
ENV_WEIGHTS = load_json(ROOT / "data" / "env_weights.json")


def player_brief(player):
    if not player:
        return None
    return {"name": player["name"], "team": player["team"]}


def missing_fields(payload, required):
    return [field for field in required if field not in payload]


def format_training_plan(plan, skills_by_id, drills_by_key):
    """Turn build_training_plan's raw items into the API shape the UI renders."""
    formatted = []
    for item in plan:
        skill = skills_by_id[item["skill_id"]]
        level = item["level"]
        metric = skill["metric"]
        formatted.append({
            "skill_id": item["skill_id"],
            "name_zh": skill["name_zh"],
            "P": item["P"],
            "level": level,
            "metric": {
                "action": metric["action"],
                "denominator": metric["denominator"],
                "direction": metric["direction"],
                "threshold": metric["thresholds"][level],
            },
            "drills": drills_by_key.get((item["skill_id"], level), []),
        })
    return formatted


def compute_template_results(payload, questions, players, skills, archetypes, drills_by_key, lang="zh", pool="current"):
    star_thresholds = ALLTIME_POOL_STAR_THRESHOLDS if pool == "alltime" else CURRENT_POOL_STAR_THRESHOLDS
    coordinates = score_axis_coordinates(questions["axis_positioning"], payload["axis_answers"])

    body_answers = payload.get("body_answers") or []
    user_body = (
        collect_body_measurements(questions["body_measurements"], body_answers)
        if body_answers else {}
    )
    body_field_ranges = {q["field"]: (q["min"], q["max"]) for q in questions["body_measurements"]}
    player_sizes = compute_player_sizes(players)
    user_body_pct, players_pct, body_field_ranges_pct = percentile_normalize_body(
        user_body, players, body_field_ranges
    )

    skills_by_id = {s["id"]: s for s in skills}
    top_10 = []
    ranked_players = rank_similar_players_by_style_and_body(
        coordinates, user_body_pct, players_pct, body_field_ranges_pct, k=10, star_thresholds=star_thresholds
    )
    for rank, player in enumerate(ranked_players, start=1):
        top_10.append({
            "rank": rank,
            "name": player["name"],
            "team": player["team"],
            "coordinates": player["coordinates"],
            "distance": player["distance"],
            "fit_stars": player["fit_stars"],
            "notable_traits": player["notable_traits"],
            "dominant_diff_axis": player["dominant_diff_axis"],
            "growth_recommendation": describe_growth_recommendation(player, skills_by_id, lang),
            "training_plans": {
                env: format_training_plan(
                    build_training_plan(
                        skills, ENV_WEIGHTS[env], coordinates, player["coordinates"],
                        top_n=TRAINING_PLAN_TOP_N,
                    ),
                    skills_by_id,
                    drills_by_key,
                )
                for env in environment_codes()
            },
        })

    archetype = classify_archetype_by_majority(ranked_players, archetypes, player_sizes=player_sizes)

    return {
        "coordinates": coordinates,
        # 六角圖每個頂點旁邊標的代表技能(各可訓練軸權重最高的那一項),依語言顯示
        "axis_skills": {
            axis: skills_by_id[skill_id]["name_zh"]
            for axis, skill_id in representative_skill_by_axis(skills).items()
        },
        "archetype": {"name_zh": archetype["name_zh"], "flavor": archetype["flavor"]},
        "scouting_report": (
            build_scouting_report(archetype) if ranked_players else None
        ),
        "deep_templates": {
            "skill_fit": player_brief(find_skill_fit_template(coordinates, players)),
            "body_fit": (
                player_brief(find_body_fit_template(user_body_pct, players_pct, body_field_ranges_pct))
                if user_body else None
            ),
            "ceiling": player_brief(find_ceiling_template(coordinates, players)),
        },
        "top_10": top_10,
    }


@app.route("/api/form-data", methods=["GET"])
def api_form_data():
    lang = request.args.get("lang", "zh")
    if lang not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"invalid lang: {lang}"}), 400
    questions, _skills, _players = load_data(lang=lang)
    return jsonify({
        "questions": {
            "axis_positioning": questions["axis_positioning"],
            "body_measurements": questions["body_measurements"],
        },
    })


@app.route("/api/template-results", methods=["POST"])
def api_template_results():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "request body must be JSON"}), 400

    missing = missing_fields(payload, TEMPLATE_REQUIRED_FIELDS)
    if missing:
        return jsonify({"error": f"missing required field(s): {', '.join(missing)}"}), 400

    pool = payload.get("pool", "current")
    if pool not in POOLS:
        return jsonify({"error": f"invalid pool: {pool}"}), 400

    lang = payload.get("lang", "zh")
    if lang not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"invalid lang: {lang}"}), 400

    questions, skills, players = load_data(pool, lang)

    missing_body = missing_required_body_fields(
        questions["body_measurements"], payload.get("body_answers") or []
    )
    if missing_body:
        return jsonify({"error": f"missing required body measurement(s): {', '.join(missing_body)}"}), 400

    archetypes = load_archetypes(lang)
    drills_by_key = load_drills(lang)
    try:
        results = compute_template_results(
            payload, questions, players, skills, archetypes, drills_by_key, lang, pool
        )
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(results)


FEEDBACK_MAX_MESSAGE = 50


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "request body must be JSON"}), 400

    # 蜜罐欄位:前端隱藏、真人不會填。機器人會把所有欄位都填滿,填了就假裝成功、不存。
    if payload.get("website"):
        return jsonify({"ok": True})

    rating = payload.get("rating")
    if rating is not None and (isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5):
        return jsonify({"error": "rating must be an integer from 1 to 5"}), 400

    raw_message = payload.get("message") or ""
    if not isinstance(raw_message, str):
        return jsonify({"error": "message must be a string"}), 400
    message = raw_message.strip()
    if rating is None and not message:
        return jsonify({"error": "give a rating or a message"}), 400
    if len(message) > FEEDBACK_MAX_MESSAGE:
        return jsonify({"error": f"message must be {FEEDBACK_MAX_MESSAGE} characters or fewer"}), 400

    lang = payload.get("lang", "zh")
    if lang not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"invalid lang: {lang}"}), 400

    try:
        save_feedback(rating, message or None, lang)
    except Exception as e:
        print(f"save_feedback failed: {e}", file=sys.stderr)
        return jsonify({"error": "could not save feedback, please try again later"}), 503
    return jsonify({"ok": True})


@app.route("/api/site-visit", methods=["POST"])
def api_site_visit():
    return jsonify({"visit_count": increment_visit_count()})


@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def serve_ui(path):
    return send_from_directory(UI_DIR, path)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5001)))
