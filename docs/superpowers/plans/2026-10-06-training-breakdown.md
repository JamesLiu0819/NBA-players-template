# 點擊球員模板看訓練方式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 10 人對照表的每一張卡片可以點開，顯示使用者跟這位球員完整六軸的
差距，以及每一軸該練什麼技能才補得起來。

**Architecture:** 後端在 `scripts/run_player_match.py` 新增一個純函數
`describe_training_breakdown()`，複用現有的 `matching_skill_id()` /
`representative_skill_id_for_axis()` 技能選擇邏輯，從「只算差距最大那一
軸」擴大成「六軸都算」。`server/app.py` 的 `compute_template_results()`
把這個函數的結果塞進既有 `/api/template-results` 回應的 `top_10` 每一筆
裡（不開新 endpoint）。前端在 `src/ui/index.html` 把每張卡片包成可點擊的
展開/收合觸發器，點開顯示六列差距明細。

**Tech Stack:** Python 3（後端）、vanilla JS + 樣板字串（前端，這個專案沒有
框架也沒有建置流程）。

## Global Constraints

- 所有分析/文案選字邏輯必須是確定性純函數，同樣輸入永遠同樣輸出（CLAUDE.md
  核心規則）——`describe_training_breakdown()` 不得有隨機性或時間依賴。
- 語言相關的文字樣板一律用 `{"zh": ..., "zh-Hans": ..., "en": ...}` 字典
  依 `lang` 參數取值，不准用 if/elif 分支（既有慣例，見
  `D_AXIS_GROWTH_TEMPLATE`/`GROWTH_ACTION_TEMPLATE`）。
- 新的 UI_STRINGS key 三個語言（`zh`/`zh-Hans`/`en`）都要補齊，缺一個都算
  沒做完。
- 不新增 `<table>` 元素——這個檔案目前全部用 div + flex/grid 排版（見
  `.env-row`），新的六列差距明細跟著用同一套風格。
- Python 的新函數要先寫失敗的測試、看著它失敗、再寫最小實作（TDD，
  CLAUDE.md「每個函數都要有單元測試」的既有慣例）。
- 複用 `src/engine/player_matching.py` 既有的 `matching_skill_id()` /
  `representative_skill_id_for_axis()`，不要重新實作同樣的技能選擇邏輯。
- 前端沒有自動化測試框架（這專案目前沒裝 Node），Task 3 用「啟動本機伺服器
  + curl 核對 API 回應」加上 Python 的 balance-check 腳本驗證語法，不用
  JS 測試。

---

### Task 1: `describe_training_breakdown()` 純函數 + 單元測試

**Files:**
- Modify: `scripts/run_player_match.py`
- Test: `tests/scripts/test_run_player_match.py`

**Interfaces:**
- Consumes：`src/engine/player_matching.py` 既有的
  `matching_skill_id(dominant_diff_axis, signature_skill_id, skills_by_id)`
  （回傳 skill_id 或 None）、
  `representative_skill_id_for_axis(axis, skills_by_id)`（回傳 skill_id）；
  `src/engine/axis_position.py` 的 `AXES = ("A", "B1", "B2", "C1", "C2", "D")`；
  `scripts/run_player_match.py` 既有的 `D_AXIS_GROWTH_TEMPLATE`、
  `GROWTH_ACTION_TEMPLATE` 兩個字典常數。
- Produces：`describe_training_breakdown(player, skills_by_id, lang="zh")`
  → `list[dict]`，固定六筆、順序照 `AXES`，每筆
  `{"axis": str, "your_value": float, "player_value": float, "diff": float, "skill_action": str | None}`。
  Task 2 會呼叫這個函數。

`player` 參數必須是 `rank_similar_players_by_style_and_body()`
（`src/engine/player_matching.py`）回傳的球員 dict，裡面已經有
`"coordinates": {axis: float, ...}`（六軸都有）跟
`"diff": {axis: float, ...}`（球員座標 − 使用者座標，六軸都有）這兩個
欄位——`your_value` 用 `player_value - diff` 反推，不需要額外傳使用者
座標進來。

- [ ] **Step 1: 寫會失敗的測試**

在 `tests/scripts/test_run_player_match.py` 裡，`from scripts.run_player_match import ...`
那行加上 `describe_training_breakdown`：

```python
from scripts.run_player_match import (  # noqa: E402
    build_scouting_report,
    describe_growth_recommendation,
    describe_training_breakdown,
)
```

在檔案最後面（`DescribeGrowthRecommendationTest` 類別之後）加上：

```python
SKILLS_BY_ID_MULTI_AXIS = {
    "high_post_playmaking": {
        "id": "high_post_playmaking",
        "axis_relevance": {"A": 1.0, "B1": 0, "B2": 0, "C1": 0, "C2": 0, "D": 0},
        "metric": {"action": "高位傳導視野"},
    },
    "pick_and_roll_ball_handling": {
        "id": "pick_and_roll_ball_handling",
        "axis_relevance": {"A": 0.9, "B1": 0, "B2": 0, "C1": 0, "C2": 0, "D": 0},
        "metric": {"action": "擋拆持球判斷"},
    },
    "perimeter_shooting": {
        "id": "perimeter_shooting",
        "axis_relevance": {"A": 0, "B1": 1.0, "B2": 0, "C1": 0, "C2": 0, "D": 0},
        "metric": {"action": "定點投射三分"},
    },
    "post_up": {
        "id": "post_up",
        "axis_relevance": {"A": 0, "B1": 0, "B2": 1.0, "C1": 0, "C2": 0, "D": 0},
        "metric": {"action": "背框單打腳步"},
    },
    "on_ball_perimeter_defense": {
        "id": "on_ball_perimeter_defense",
        "axis_relevance": {"A": 0, "B1": 0, "B2": 0, "C1": 1.0, "C2": 0, "D": 0},
        "metric": {"action": "一對一外圍單防"},
    },
    "rim_protection": {
        "id": "rim_protection",
        "axis_relevance": {"A": 0, "B1": 0, "B2": 0, "C1": 0, "C2": 1.0, "D": 0},
        "metric": {"action": "護框"},
    },
}


class DescribeTrainingBreakdownTest(unittest.TestCase):
    def test_returns_six_rows_in_fixed_axes_order(self):
        player = {
            "signature_skill_id": None,
            "coordinates": {"A": 80, "B1": 80, "B2": 80, "C1": 80, "C2": 80, "D": 80},
            "diff": {"A": 10, "B1": 10, "B2": 10, "C1": 10, "C2": 10, "D": 10},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS)

        self.assertEqual([row["axis"] for row in result], ["A", "B1", "B2", "C1", "C2", "D"])

    def test_your_value_is_derived_from_player_value_minus_diff(self):
        player = {
            "signature_skill_id": None,
            "coordinates": {"A": 80, "B1": 80, "B2": 80, "C1": 80, "C2": 80, "D": 80},
            "diff": {"A": 10, "B1": 10, "B2": 10, "C1": 10, "C2": 10, "D": 10},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS)

        row_a = next(row for row in result if row["axis"] == "A")
        self.assertEqual(row_a["player_value"], 80)
        self.assertEqual(row_a["diff"], 10)
        self.assertEqual(row_a["your_value"], 70)

    def test_non_positive_diff_has_no_skill_action(self):
        player = {
            "signature_skill_id": None,
            "coordinates": {"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50},
            # user leads (diff<0) on A, ties (diff==0) on B1
            "diff": {"A": -5, "B1": 0, "B2": 10, "C1": 10, "C2": 10, "D": 10},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS)

        by_axis = {row["axis"]: row for row in result}
        self.assertIsNone(by_axis["A"]["skill_action"])
        self.assertIsNone(by_axis["B1"]["skill_action"])

    def test_positive_diff_falls_back_to_representative_skill_for_axis(self):
        player = {
            "signature_skill_id": None,
            "coordinates": {"A": 50, "B1": 80, "B2": 50, "C1": 50, "C2": 50, "D": 50},
            "diff": {"A": 0, "B1": 40, "B2": 0, "C1": 0, "C2": 0, "D": 0},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS)

        row_b1 = next(row for row in result if row["axis"] == "B1")
        self.assertEqual(row_b1["skill_action"], "定點投射三分的練習")

    def test_signature_skill_wins_over_representative_when_it_targets_the_axis(self):
        # A 軸有兩個候選技能，relevance 較高的是 high_post_playmaking(1.0)，
        # 但這位球員的招牌技能是 relevance 較低的 pick_and_roll_ball_handling
        # (0.9)——結果應該用招牌技能，不是單純取 relevance 最高的那個，
        # 跟 matching_skill_id() 既有的「招牌技能優先」規則一致。
        player = {
            "signature_skill_id": "pick_and_roll_ball_handling",
            "coordinates": {"A": 80, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50},
            "diff": {"A": 10, "B1": 0, "B2": 0, "C1": 0, "C2": 0, "D": 0},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS)

        row_a = next(row for row in result if row["axis"] == "A")
        self.assertEqual(row_a["skill_action"], "擋拆持球判斷的練習")

    def test_d_axis_positive_diff_uses_the_untrainable_message_not_a_skill(self):
        player = {
            "signature_skill_id": None,
            "coordinates": {"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 90},
            "diff": {"A": 0, "B1": 0, "B2": 0, "C1": 0, "C2": 0, "D": 20},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS)

        row_d = next(row for row in result if row["axis"] == "D")
        self.assertEqual(row_d["skill_action"], "身體天賦上有落差,不能單靠練習籃球技能")

    def test_lang_en_returns_english_text(self):
        player = {
            "signature_skill_id": None,
            "coordinates": {"A": 50, "B1": 80, "B2": 50, "C1": 50, "C2": 50, "D": 50},
            "diff": {"A": 0, "B1": 40, "B2": 0, "C1": 0, "C2": 0, "D": 0},
        }

        result = describe_training_breakdown(player, SKILLS_BY_ID_MULTI_AXIS, lang="en")

        row_b1 = next(row for row in result if row["axis"] == "B1")
        self.assertNotEqual(row_b1["skill_action"], "定點投射三分的練習")
        self.assertTrue(row_b1["skill_action"].strip())
```

- [ ] **Step 2: 跑測試，確認失敗**

Run: `PYTHONPATH=.:src python3 -m unittest tests.scripts.test_run_player_match.DescribeTrainingBreakdownTest -v`
Expected: `ImportError` 或 `AttributeError`，因為 `describe_training_breakdown` 還不存在。

- [ ] **Step 3: 寫最小實作**

在 `scripts/run_player_match.py` 裡，緊接在 `describe_growth_recommendation`
函數後面（第 109 行後面）加上：

```python
def describe_training_breakdown(player, skills_by_id, lang="zh"):
    """Full six-axis gap breakdown for "how do I train to become this
    player" -- unlike describe_growth_recommendation (which only reports
    the single dominant-diff axis), this reports all six so a user who
    clicks into one specific template player can see the whole picture,
    not just the biggest gap (2026-10 discussion).

    player: a ranked player dict from rank_similar_players_by_style_and_body
        (must have "coordinates" and "diff", both {axis: float} covering
        every axis in AXES).

    Returns a list of six dicts, one per axis in AXES order:
        {"axis": str, "your_value": float, "player_value": float,
         "diff": float, "skill_action": str | None}
    skill_action is None when diff <= 0 (the user already matches or
    exceeds the player on that axis -- nothing to train there). For D,
    a positive diff always uses D_AXIS_GROWTH_TEMPLATE instead of a skill
    action, same as describe_growth_recommendation -- athleticism isn't
    something a specific drill closes.
    """
    breakdown = []
    for axis in AXES:
        diff = player["diff"][axis]
        player_value = player["coordinates"][axis]
        your_value = player_value - diff

        if diff <= 0:
            skill_action = None
        elif axis == "D":
            skill_action = D_AXIS_GROWTH_TEMPLATE[lang]
        else:
            skill_id = matching_skill_id(axis, player.get("signature_skill_id"), skills_by_id)
            if not skill_id:
                skill_id = representative_skill_id_for_axis(axis, skills_by_id)
            action = skills_by_id[skill_id]["metric"]["action"]
            skill_action = GROWTH_ACTION_TEMPLATE[lang].format(action=action)

        breakdown.append({
            "axis": axis,
            "your_value": your_value,
            "player_value": player_value,
            "diff": diff,
            "skill_action": skill_action,
        })
    return breakdown
```

- [ ] **Step 4: 跑測試，確認通過**

Run: `PYTHONPATH=.:src python3 -m unittest tests.scripts.test_run_player_match -v`
Expected: 全部 PASS（包含原本就有的 `DescribeGrowthRecommendationTest`，
確認沒有改壞既有測試）。

- [ ] **Step 5: Commit**

```bash
git add scripts/run_player_match.py tests/scripts/test_run_player_match.py
git commit -m "feat: add describe_training_breakdown for full six-axis gap detail"
```

---

### Task 2: 接進 `/api/template-results` API 回應

**Files:**
- Modify: `server/app.py`
- Test: `server/test_app.py`

**Interfaces:**
- Consumes：Task 1 的 `describe_training_breakdown(player, skills_by_id, lang)`。
- Produces：`/api/template-results` 回應的 `top_10` 每一筆多一個
  `training_breakdown` 欄位（值是 Task 1 函數的回傳值）。Task 3 的前端會
  讀這個欄位。

- [ ] **Step 1: 寫會失敗的測試**

在 `server/test_app.py` 的 `test_top_10_entries_have_expected_fields`
（目前在 `TemplateResultsTest` 類別裡）把 `training_breakdown` 加進預期
欄位集合：

```python
    def test_top_10_entries_have_expected_fields(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)
        top_player = response.get_json()["top_10"][0]

        self.assertEqual(
            set(top_player.keys()),
            {
                "rank", "name", "team", "coordinates", "distance", "fit_stars",
                "notable_traits", "dominant_diff_axis", "growth_recommendation",
                "training_breakdown",
            },
        )
        self.assertEqual(top_player["rank"], 1)
        self.assertEqual(set(top_player["coordinates"].keys()), {"A", "B1", "B2", "C1", "C2", "D"})
```

緊接著在同一個類別裡新增一個測試方法：

```python
    def test_top_10_training_breakdown_covers_all_six_axes(self):
        payload = {
            "axis_answers": build_axis_answers(self.questions),
            "body_answers": build_required_body_answers(self.questions),
        }

        response = self.client.post("/api/template-results", json=payload)
        breakdown = response.get_json()["top_10"][0]["training_breakdown"]

        self.assertEqual(len(breakdown), 6)
        self.assertEqual(
            {row["axis"] for row in breakdown}, {"A", "B1", "B2", "C1", "C2", "D"}
        )
        for row in breakdown:
            self.assertIn("your_value", row)
            self.assertIn("player_value", row)
            self.assertIn("diff", row)
            self.assertIn("skill_action", row)
```

- [ ] **Step 2: 跑測試，確認失敗**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app.TemplateResultsTest.test_top_10_entries_have_expected_fields -v`
Expected: FAIL，因為回應裡還沒有 `training_breakdown` 這個 key
（`assertEqual` 的集合比對會印出差異）。

- [ ] **Step 3: 寫最小實作**

修改 `server/app.py` 第 105 行的 import，把 `describe_training_breakdown`
加進來：

```python
from scripts.run_player_match import (  # noqa: E402
    build_scouting_report,
    describe_growth_recommendation,
    describe_training_breakdown,
)
```

修改 `compute_template_results` 裡組 `top_10` 的迴圈（第 188-199 行），
在 `growth_recommendation` 那行後面加一行：

```python
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
            "training_breakdown": describe_training_breakdown(player, skills_by_id, lang),
        })
```

- [ ] **Step 4: 跑測試，確認通過**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app -v`
Expected: 全部 PASS。

再跑一次 Task 1 的測試加上整個 engine 套件，確認沒有連帶改壞別的東西：

Run: `PYTHONPATH=src python3 -m unittest discover -s tests/engine && PYTHONPATH=.:src python3 -m unittest discover -s tests/scripts`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add server/app.py server/test_app.py
git commit -m "feat: expose training_breakdown on /api/template-results top_10 entries"
```

---

### Task 3: 前端——卡片可點開看訓練明細

**Files:**
- Modify: `src/ui/index.html`

**Interfaces:**
- Consumes：Task 2 的 API 回應，每個 `top_10` 項目的
  `training_breakdown: {axis, your_value, player_value, diff, skill_action}[]`
  （六筆，順序固定 A/B1/B2/C1/C2/D）。
- Produces：無（這是最後一個 task，UI 端末端功能）。

這個 task 沒有自動化測試（專案目前沒有 JS 測試框架），改用「跑 balance-check
腳本驗證語法完整 + 啟動本機伺服器用 curl 核對 API 形狀」替代，跟這個專案
之前幾輪前端改動的驗證方式一致。

- [ ] **Step 1: 三個語言補上新的 UI_STRINGS key**

在 `src/ui/index.html` 裡找到 `youLabel: "你",`（zh 區塊，約第 1336 行），
改成：

```js
      youLabel: "你",
      trainingBreakdownAlreadyAhead: "已經領先",
      trainingBreakdownGapLabel: "差距",
      trainingBreakdownToggleAriaLabel: (name) => `查看${name}的訓練方式`,
```

找到 `youLabel: "你",`（zh-Hans 區塊，約第 1404 行），改成：

```js
      youLabel: "你",
      trainingBreakdownAlreadyAhead: "已经领先",
      trainingBreakdownGapLabel: "差距",
      trainingBreakdownToggleAriaLabel: (name) => `查看${name}的训练方式`,
```

找到 `youLabel: "You",`（en 區塊，約第 1472 行），改成：

```js
      youLabel: "You",
      trainingBreakdownAlreadyAhead: "Already ahead",
      trainingBreakdownGapLabel: "Gap",
      trainingBreakdownToggleAriaLabel: (name) => `View training plan for ${name}`,
```

- [ ] **Step 2: 新增 CSS**

找到這一行（約第 1062 行）：

```css
  .card .callout .growth, .top-match .callout .growth { color: var(--ink-soft); }
```

在它後面加上：

```css

  .card-trigger { cursor: pointer; display: flex; flex-direction: column; gap: 0.5rem; }
  .card-trigger:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
  .expand-caret {
    align-self: center;
    font-size: 0.7rem;
    color: var(--ink-soft);
    transition: transform 0.15s ease;
  }
  .card-trigger[aria-expanded="true"] .expand-caret { transform: rotate(180deg); }

  .training-breakdown {
    margin-top: 0.3rem;
    padding-top: 0.6rem;
    border-top: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }
  .breakdown-row {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.25rem 0.6rem;
    font-size: 0.78rem;
  }
  .breakdown-row .axis { font-weight: 700; color: var(--ink); flex: 0 0 4rem; }
  .breakdown-row .values { color: var(--ink-soft); }
  .breakdown-row .diff-gap { color: var(--accent-ink); font-weight: 700; }
  .breakdown-row .diff-lead { color: var(--ink-soft); }
  .breakdown-row .action { color: var(--ink-soft); flex-basis: 100%; }
```

（`.action` 用 `flex-basis: 100%` 讓建議練習文字永遠自己獨立一行，手機
窄螢幕也是同一套規則自然換行堆疊，不用另外寫 media query。）

- [ ] **Step 3: 新增 `renderTrainingBreakdown()`，改寫卡片組裝邏輯**

找到 `renderMatchCardInner` 函數結尾（約第 2254 行）：

```js
      <div class="callout">
        <span class="axis-tag">${t().dominantAxisGap(t().axisLabels[m.dominant_diff_axis])}</span>
        <span class="growth">${t().growthNotePrefix}${m.growth_recommendation}</span>
      </div>`;
  }
```

在這個函數後面（`renderPriorityRow` 之前）插入新函數：

```js

  function renderTrainingBreakdown(m) {
    const rows = m.training_breakdown.map((row) => {
      const diffText = (row.diff > 0 ? "+" : "") + row.diff.toFixed(1);
      const diffClass = row.diff > 0 ? "diff-gap" : "diff-lead";
      const actionHtml = row.skill_action
        ? `${t().growthNotePrefix}${row.skill_action}`
        : t().trainingBreakdownAlreadyAhead;
      return `
        <div class="breakdown-row">
          <span class="axis">${t().axisLabels[row.axis]}</span>
          <span class="values mono">${t().youLabel} ${row.your_value.toFixed(1)} → ${m.name} ${row.player_value.toFixed(1)}（${t().trainingBreakdownGapLabel} <span class="${diffClass}">${diffText}</span>）</span>
          <span class="action">${actionHtml}</span>
        </div>`;
    }).join("");
    return `<div class="training-breakdown" hidden>${rows}</div>`;
  }
```

找到 `renderTemplateReport` 裡組 `matchListHtml` 的地方（約第 2280-2284
行）：

```js
    const matchListHtml = data.top_10.map((m, i) => {
      const cardClass = i === 0 ? "top-match" : "card";
      const badge = i === 0 ? `<span class="top-match-badge">${t().mostSuitable}</span>` : "";
      return `<div class="${cardClass}">${badge}${renderMatchCardInner(i + 1, m)}</div>`;
    }).join("");
```

改成：

```js
    const matchListHtml = data.top_10.map((m, i) => {
      const cardClass = i === 0 ? "top-match" : "card";
      const badge = i === 0 ? `<span class="top-match-badge">${t().mostSuitable}</span>` : "";
      const ariaLabel = t().trainingBreakdownToggleAriaLabel(m.name);
      return `<div class="${cardClass}">${badge}<div class="card-trigger" role="button" tabindex="0" aria-expanded="false" aria-label="${ariaLabel}">${renderMatchCardInner(i + 1, m)}<span class="expand-caret" aria-hidden="true">▾</span></div>${renderTrainingBreakdown(m)}</div>`;
    }).join("");
```

- [ ] **Step 4: 綁定點擊/鍵盤事件**

找到 `renderTemplateReport` 函數結尾的 `shareBtn` 綁定（約第 2319-2322
行）：

```js
    const shareBtn = document.getElementById("share-btn");
    if (shareBtn) {
      shareBtn.addEventListener("click", () => downloadShareImage(data, topMatch));
    }
  }
```

改成：

```js
    const shareBtn = document.getElementById("share-btn");
    if (shareBtn) {
      shareBtn.addEventListener("click", () => downloadShareImage(data, topMatch));
    }

    document.querySelectorAll(".card-trigger").forEach((trigger) => {
      const toggle = () => {
        const expanded = trigger.getAttribute("aria-expanded") === "true";
        trigger.setAttribute("aria-expanded", String(!expanded));
        trigger.nextElementSibling.hidden = expanded;
      };
      trigger.addEventListener("click", toggle);
      trigger.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggle();
        }
      });
    });
  }
```

- [ ] **Step 5: 驗證語法完整性**

Run:
```bash
python3 -c "
content = open('src/ui/index.html', encoding='utf-8').read()
print('braces', content.count('{') - content.count('}'))
print('parens', content.count('(') - content.count(')'))
print('brackets', content.count('[') - content.count(']'))
"
```
Expected: 三個都印出 `0`。不是 0 就表示某處漏了括號，回頭檢查剛才貼的
程式碼片段有沒有貼完整。

- [ ] **Step 6: 跑完整 Python 測試套件，確認沒有連帶改壞**

Run:
```bash
PYTHONPATH=src python3 -m unittest discover -s tests/engine
PYTHONPATH=.:src python3 -m unittest discover -s tests/scripts
cd server && ../.venv/bin/python3 -m unittest test_app test_db
```
Expected: 三個指令都是 `OK`（這個 task 沒改 Python，這一步是保險，確認
前端改動沒有不小心動到別的檔案）。

- [ ] **Step 7: 啟動本機伺服器，手動核對 API 回應跟頁面**

```bash
cd server && ../.venv/bin/python3 app.py &
sleep 2
curl -s http://127.0.0.1:5001/ -o /dev/null -w "index.html: %{http_code}\n"
```

打開瀏覽器到 `http://127.0.0.1:5001/`，走一次完整流程到結果頁，確認：
1. 10 人對照表每一張卡片右下角有一個小箭頭圖示。
2. 點卡片（不是點按鈕，因為沒有獨立按鈕，整張卡片都可以點）會展開六列
   差距明細，箭頭會翻轉方向。
3. 同時點開兩張卡片，兩張都維持展開狀態（不是手風琴）。
4. 再點一次已展開的卡片，明細收合，箭頭轉回來。
5. 鍵盤 Tab 到卡片、按 Enter 或空白鍵，也能展開/收合。
6. 切換語言（右上角語言選單），展開面板裡的文字（差距/已經領先/建議
   練習）要跟著切換，不要停在舊語言。
7. 六軸裡只要有任一軸使用者已經領先，那一軸要顯示「已經領先」，不是
   顯示 `undefined` 或空白。

跑完後關掉伺服器：

```bash
pkill -f "server/app.py"
```

- [ ] **Step 8: Commit**

```bash
git add src/ui/index.html
git commit -m "feat: make 10-player cards clickable to reveal full training breakdown"
```
