# 點擊球員模板看訓練方式 — 設計文件

> 2026-10-06，分支 `feature/template-player-training-guide`

## 一句話

10 人對照表裡每一位球員卡片都可以點開，看到使用者跟這位球員在「六軸」上
完整的差距，以及每一軸該練什麼技能才補得起來——不只是現在卡片上已經有的
「差距最大那一軸 + 一個技能建議」。

## 為什麼

現有的 `growth_recommendation` 只講差距最大的那一軸，資訊量故意收斂成一句
話，適合列表瀏覽。但使用者點進一位具體球員、想認真研究「我要怎麼練成這個
人」的時候，一句話不夠——六軸裡搞不好有兩三軸差距都很大，使用者會想知道
全貌,不是只被告知「最大的那一軸」。

## 範圍

**可以點開的卡片**：10 人對照表的每一列（不含 3 位深度模板卡片——那三張
卡片的設計目的本來就不是同一回事：技術模板刻意排除身材、身體最貼合刻意
只看身材、天花板是另一套邏輯，混進來會讓「訓練方式」這件事失焦）。

**點開後顯示的內容**：六軸完整差距表，每一軸顯示：
- 使用者的座標值、這位球員的座標值、差距（球員 − 使用者，正值代表球員
  較強）
- 如果差距 > 0：對應的技能練習建議（沿用現有的技能選擇邏輯：優先用這位
  球員自己的招牌技能，如果招牌技能不是對應這一軸，退回該軸相關性最高的
  技能，跟現在 `growth_recommendation` 用的是同一套規則，只是套用到全部
  六軸而不是只套在差距最大那一軸）
- 如果差距 ≤ 0（使用者已經比這位球員強，或打平）：不給技能建議，前端顯示
  「已經領先」類的文字

**展開行為**：多張卡片可以同時展開（不是手風琴），方便並排比較。

## 資料流

`rank_similar_players_by_style_and_body`（`src/engine/player_matching.py`）
內部早就算好每位球員的完整六軸 `diff`，只是目前 API 回應只挑出
`dominant_diff_axis` 跟一句 `growth_recommendation`，沒有把完整的六軸差距
送到前端。

新增 `scripts/run_player_match.py` 裡的函數
`describe_training_breakdown(player, skills_by_id, lang="zh")`：複用
`describe_growth_recommendation` 已經在用的 `matching_skill_id` /
`representative_skill_id_for_axis`，差別只是對 `AXES` 六軸各跑一次，不是
只對 `dominant_diff_axis` 跑一次。回傳：

```python
[
    {"axis": "A", "your_value": 55.0, "player_value": 80.0, "diff": 25.0,
     "skill_action": "高位傳導視野的練習"},
    {"axis": "B1", "your_value": 40.0, "player_value": 85.0, "diff": 45.0,
     "skill_action": "定點投射三分的練習"},
    ...  # 六筆,順序固定照 AXES
    {"axis": "C1", "your_value": 60.0, "player_value": 50.0, "diff": -10.0,
     "skill_action": None},  # 使用者已領先,沒有建議
]
```

不回傳軸的中文/英文標籤——前端已經有 `t().axisLabels[axis]`，不用兩邊各
維護一份。`skill_action` 本身的文字要照 `lang` 走（沿用
`GROWTH_ACTION_TEMPLATE` 那套 zh/zh-Hans/en 字典，不能用 if/elif）。

`server/app.py` 的 `compute_template_results` 在組 `top_10` 每一筆的時候，
多加一個 `training_breakdown` 欄位放這個新函數的回傳值——十位球員都在同一
次 `/api/template-results` 回應裡算好，不開新的 API endpoint（運算量很小：
6 軸 × 10 位球員 × ~15 個技能，比對目前算距離的運算量還小很多）。

## 前端

`renderMatchCardInner` 的卡片本身不變，整張卡片（`.card`/`.top-match`）
當作可點擊的展開/收合觸發點——不額外加「查看訓練方式」按鈕，卡片本身的
`cursor: pointer` 跟一個小箭頭圖示（展開/收合方向）就足夠提示可以點。
展開的面板是一個六列小表格,比照網站既有的
表格/卡片視覺風格（`--paper-sunken` 底色、`--line` 分隔線），手機版用堆疊
排版，不用表格橫向捲動。

每張卡片有自己的展開狀態（布林值,存在渲染時組出來的 DOM/state 裡，不用
存到 `state` 全域物件——跟現有「哪個語言」「哪個主題」這種需要跨渲染保留
的狀態不同，這個只在這次結果畫面存在期間有意義，使用者重新整理或換語言
after 不需要記得哪些卡片是展開的）。

## 邊界情況

- 使用者六軸都領先某位球員（六筆差距全部 ≤ 0）：六列都顯示「已經領先」，
  不用額外的空狀態文案，表格本身就說明了情況。
- 歷史球員池（all-time）：邏輯完全一樣，`describe_training_breakdown` 不
  分現役/歷史，兩個 pool 共用。
- 球員沒有 `signature_skill_id`（目前資料裡應該都有，但函數簽名要保留
  這個可能性）：沿用 `matching_skill_id` 現有的 None 處理，直接退回
  `representative_skill_id_for_axis`。

## 測試

- `scripts/run_player_match.py` 新增 `describe_training_breakdown` 的
  單元測試（跟 `tests/scripts/test_run_player_match.py` 裡現有的
  `DescribeGrowthRecommendationTest` 同一個檔案、類似結構）：六軸都要
  覆蓋、正負差距都要覆蓋、三語都要覆蓋。
- `server/test_app.py` 的 `TemplateResultsTest` 加一個 assertion：
  `top_10` 每一筆都有 `training_breakdown`，且剛好六筆、`axis` 涵蓋
  `AXES` 全部六個。
- 前端沒有自動化測試（這個專案目前沒有 JS 測試框架，跟現有其他前端功能
  一致，靠手動瀏覽器測試）。

## 不做的事

- 不做「技能影片」連結（`skills.json` 的 `video_tags` 目前只是佔位標籤，
  跟這個功能無關，CLAUDE.md 已經記錄這塊還沒做）。
- 不做 3 位深度模板卡片的點擊展開（見上面「範圍」一節的理由）。
- 不做跨球員的訓練計畫合併/去重（例如使用者點開兩位球員，兩邊都建議練
  「定點投射三分」，不特別合併成一個待辦清單——每張卡片的訓練內容就是
  針對「變成這一位球員」,卡片之間刻意保持獨立）。
