# 用途：Flask 後端,兩支 API：GET /api/form-data(給前端渲染問卷用的題庫跟技能
# 名稱,只回傳必要欄位,不外洩 axis_relevance/cost_C 等內部校準數字)、
# POST /api/results(把作答轉成完整結果 JSON：四軸座標、優先序、3 位深度模板、
# 10 人對照表、反面對照)。同時把 /src/ui 的靜態前端檔案服務出去。**刻意不**
# 把 data/ 整個目錄當靜態檔案服務——data/answers/ 裡面是真實使用者的個人作答
# 資料,不能公開存取。計算邏輯全部重用 src/engine 跟 scripts/run_priority.py、
# scripts/run_player_match.py 已經拆出來的函數,這支檔案只做請求解析、資料載入、
# 呼叫、組裝回應,不重寫任何計算規則。
# 可手動調整的變數：無——欄位驗證規則來自 src/engine 各函數本來就有的
# ValueError,不在這裡另外定義一套。
"""Flask app: GET /api/form-data, POST /api/results, static file serving for /src/ui.

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

from engine.body_fit import collect_body_measurements  # noqa: E402
from engine.player_matching import (  # noqa: E402
    find_anti_template,
    find_body_fit_template,
    find_ceiling_template,
    find_skill_fit_template,
    rank_similar_players,
)
from engine.priority import rank_priorities  # noqa: E402
from scripts.run_player_match import describe_growth_recommendation  # noqa: E402
from scripts.run_priority import build_priority_items, format_dominant_factor_sentence  # noqa: E402

UI_DIR = ROOT / "src" / "ui"
REQUIRED_FIELDS = ("axis_answers", "skill_answers", "env")

app = Flask(__name__, static_folder=None)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_data():
    questions = load_json(ROOT / "data" / "questions.json")
    skills = load_json(ROOT / "data" / "skills.json")["skills"]
    players = load_json(ROOT / "data" / "players.json")["players"]
    return questions, skills, players


def player_brief(player):
    if not player:
        return None
    return {"name": player["name"], "team": player["team"]}


def compute_results(payload, questions, skills, players):
    coordinates, items = build_priority_items(
        questions, skills, payload["axis_answers"], payload["skill_answers"], payload["env"]
    )
    ranked_priorities = rank_priorities(items)

    skills_by_id = {s["id"]: s for s in skills}

    body_answers = payload.get("body_answers") or []
    user_body = (
        collect_body_measurements(questions["body_measurements"], body_answers)
        if body_answers else {}
    )

    top_10 = []
    for rank, player in enumerate(rank_similar_players(coordinates, players, k=10), start=1):
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
        "priorities": [
            {
                "skill_id": item["skill_id"], "name_zh": item["name_zh"], "P": item["P"],
                "G": item["G"], "E": item["E"], "R": item["R"], "C": item["C"],
            }
            for item in ranked_priorities
        ],
        "dominant_factor_sentence": format_dominant_factor_sentence(ranked_priorities),
        "deep_templates": {
            "skill_fit": player_brief(find_skill_fit_template(coordinates, players)),
            "body_fit": player_brief(find_body_fit_template(user_body, players)) if user_body else None,
            "ceiling": player_brief(find_ceiling_template(coordinates, players)),
        },
        "top_10": top_10,
        "anti_template": player_brief(find_anti_template(coordinates, players)),
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


@app.route("/api/results", methods=["POST"])
def api_results():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "request body must be JSON"}), 400

    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        return jsonify({"error": f"missing required field(s): {', '.join(missing)}"}), 400

    questions, skills, players = load_data()
    try:
        results = compute_results(payload, questions, skills, players)
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(results)


@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def serve_ui(path):
    return send_from_directory(UI_DIR, path)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5001)))
