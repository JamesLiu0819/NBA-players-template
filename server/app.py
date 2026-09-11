# 用途：Flask 後端,三支 API：
#   GET  /api/form-data       給前端渲染問卷用的題庫跟技能名稱,只回傳必要欄位,
#                             不外洩 axis_relevance/cost_C 等內部校準數字。
#   POST /api/template-results  只吃球風定位(16題)+ 身材數值(6題,可省略),
#                             回傳定位座標、3 位深度模板、10 人對照表——刻意
#                             不需要技能行為跟環境權重,因為很多使用者沒在打
#                             正式比賽,只想知道自己的球員模板。
#                             10 人對照表用四軸+身材一起算距離(沒填身材數值
#                             題就自動退化成純四軸),避免推薦身材差異很大的
#                             球員當模板;3 位深度模板維持純四軸/純身材距離,
#                             刻意不受這個改動影響(第一版本來多加了一張跟 10
#                             人對照表#1 相同的「整體模板」卡,但根本就是重複
#                             資訊,2026-09-11 移除)。
#                             身材裡的身高/體重會先用 percentile_normalize_body
#                             換算成百分位再比,不然幾乎所有使用者都比全部 NBA
#                             球員矮/輕,身材模板永遠是最矮的後衛。天花板的定義
#                             是「D 軸接近、主導差距在 A/B/C」,是一個身體條件
#                             跟你差不多、但技術更成熟的球員(2026-09-11 重新
#                             設計,原本的反面對照段落因為用同一套「D 軸差距
#                             最大」邏輯、找到的其實是天賦不同的人而非天花板,
#                             已經移除)。
#   POST /api/priority-results  才吃技能行為(15題)+ 環境權重,回傳優先訓練
#                             順序,是使用者自己選擇要不要看的「進階」分析。
# /api/template-results 吃一個選填的 "pool" 欄位("current"預設值 或
# "alltime"),決定球員池要用 data/players.json(現役)還是
# data/players_alltime.json(歷史,2026-09-11 新增)。兩份資料同一套 schema,
# 差別只有歷史池的 "team" 欄位放代表年份而不是球隊縮寫,所以 compute_
# template_results 完全不用改,只有 load_data 多一個參數決定讀哪個檔案。
# 同時把 /src/ui 的靜態前端檔案服務出去。**刻意不**把 data/ 整個目錄當靜態
# 檔案服務——data/answers/ 裡面是真實使用者的個人作答資料,不能公開存取。
# 計算邏輯全部重用 src/engine 跟 scripts/run_priority.py、
# scripts/run_player_match.py 已經拆出來的函數,這支檔案只做請求解析、資料載入、
# 呼叫、組裝回應,不重寫任何計算規則。
# 可手動調整的變數：PLAYER_POOL_FILES(pool 名稱對應的球員資料檔名,要再加
# 新的球員池就在這裡加一筆)。
"""Flask app: GET /api/form-data, POST /api/template-results,
POST /api/priority-results, static file serving for /src/ui.

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

from engine.axis_position import score_axis_coordinates  # noqa: E402
from engine.body_fit import collect_body_measurements, percentile_normalize_body  # noqa: E402
from engine.player_matching import (  # noqa: E402
    find_body_fit_template,
    find_ceiling_template,
    find_skill_fit_template,
    rank_similar_players_by_style_and_body,
)
from engine.priority import rank_priorities  # noqa: E402
from scripts.run_player_match import describe_growth_recommendation  # noqa: E402
from scripts.run_priority import build_priority_items, format_dominant_factor_sentence  # noqa: E402

UI_DIR = ROOT / "src" / "ui"
TEMPLATE_REQUIRED_FIELDS = ("axis_answers",)
PRIORITY_REQUIRED_FIELDS = ("axis_answers", "skill_answers", "env")
PLAYER_POOL_FILES = {
    "current": "players.json",
    "alltime": "players_alltime.json",
}

app = Flask(__name__, static_folder=None)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_data(pool="current"):
    questions = load_json(ROOT / "data" / "questions.json")
    skills = load_json(ROOT / "data" / "skills.json")["skills"]
    players = load_json(ROOT / "data" / PLAYER_POOL_FILES[pool])["players"]
    return questions, skills, players


def player_brief(player):
    if not player:
        return None
    return {"name": player["name"], "team": player["team"]}


def missing_fields(payload, required):
    return [field for field in required if field not in payload]


def compute_template_results(payload, questions, players, skills_by_id):
    coordinates = score_axis_coordinates(questions["axis_positioning"], payload["axis_answers"])

    body_answers = payload.get("body_answers") or []
    user_body = (
        collect_body_measurements(questions["body_measurements"], body_answers)
        if body_answers else {}
    )
    body_field_ranges = {q["field"]: (q["min"], q["max"]) for q in questions["body_measurements"]}
    user_body_pct, players_pct, body_field_ranges_pct = percentile_normalize_body(
        user_body, players, body_field_ranges
    )

    top_10 = []
    ranked_players = rank_similar_players_by_style_and_body(
        coordinates, user_body_pct, players_pct, body_field_ranges_pct, k=10
    )
    for rank, player in enumerate(ranked_players, start=1):
        top_10.append({
            "rank": rank,
            "name": player["name"],
            "team": player["team"],
            "distance": player["distance"],
            "fit_stars": player["fit_stars"],
            "notable_traits": player["notable_traits"],
            "dominant_diff_axis": player["dominant_diff_axis"],
            "growth_recommendation": describe_growth_recommendation(player, skills_by_id),
        })

    return {
        "coordinates": coordinates,
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


def compute_priority_results(payload, questions, skills):
    coordinates, items = build_priority_items(
        questions, skills, payload["axis_answers"], payload["skill_answers"], payload["env"]
    )
    ranked_priorities = rank_priorities(items)

    return {
        "coordinates": coordinates,
        "priorities": [
            {
                "skill_id": item["skill_id"], "name_zh": item["name_zh"], "P": item["P"],
                "G": item["G"], "E": item["E"], "R": item["R"], "C": item["C"],
            }
            for item in ranked_priorities
        ],
        "dominant_factor_sentence": format_dominant_factor_sentence(ranked_priorities),
    }


@app.route("/api/form-data", methods=["GET"])
def api_form_data():
    questions, skills, _players = load_data()
    return jsonify({
        "questions": {
            "axis_positioning": questions["axis_positioning"],
            "skill_behavior": questions["skill_behavior"],
            "body_measurements": questions["body_measurements"],
        },
        "skills": [{"id": s["id"], "name_zh": s["name_zh"]} for s in skills],
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
    if pool not in PLAYER_POOL_FILES:
        return jsonify({"error": f"invalid pool: {pool}"}), 400

    questions, skills, players = load_data(pool)
    skills_by_id = {s["id"]: s for s in skills}
    try:
        results = compute_template_results(payload, questions, players, skills_by_id)
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(results)


@app.route("/api/priority-results", methods=["POST"])
def api_priority_results():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "request body must be JSON"}), 400

    missing = missing_fields(payload, PRIORITY_REQUIRED_FIELDS)
    if missing:
        return jsonify({"error": f"missing required field(s): {', '.join(missing)}"}), 400

    questions, skills, _players = load_data()
    try:
        results = compute_priority_results(payload, questions, skills)
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(results)


@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def serve_ui(path):
    return send_from_directory(UI_DIR, path)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5001)))
