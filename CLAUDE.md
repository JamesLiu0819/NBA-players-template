# CLAUDE.md — 籃球球員模板分析系統

## 專案一句話
把一套原本靠 AI 對話執行的籃球球員分析流程，改寫成**不需要 AI 介入**的規則化網站：使用者填題目量表（目前已上線 18 題：六軸定位 12〔A/B1/B2/C1/C2/D 各 2〕+ 身材數值 6〔其中身高體重必填，其餘選填〕；技能行為題已移除，技能缺口改由六軸座標推算；SPEC.md §5.5 規劃的完整版是 41–47 題，還缺目標/限制兩塊）→ 系統計算六軸座標 → 輸出模板球員，並在結果頁底部依聯賽環境（三組暫定）與目標球員輸出訓練計劃。網站同時提供繁中（`data/zh/`）、簡中（`data/zh-Hans/`）、英文（`data/en/`）三語版本，由 API 的 `lang` 參數切換，三份資料檔結構完全對應（`tests/engine/test_i18n_parity.py` 把關）。四軸座標是 2026-10 以前的舊設計：原本的 B（空間位置）、C（防守對位）各自是「兩端二選一」的光譜軸，後來發現這其實問的是站位偏好/教練分配角色，不是真實的投籃或防守能力，系統性低估中鋒——改成各自拆成兩個獨立技能軸（B1 外線投射/B2 禁區得分、C1 外圍防守/C2 禁區防守），才有六軸。影片清單這塊還沒建（skills.json 的 `video_tags` 目前只是佔位標籤，沒有接真正的影片庫）。

## 最重要的三條規則

1. **AI 只用在文案潤飾，不用在分析。**
   所有分析（定位、匹配、排序）必須是確定性的純函數。同樣的輸入必須永遠得到同樣的輸出。任何「讓 LLM 判斷一下」的設計都是錯的。

2. **環境權重是輸入，不是後處理。**
   聯賽環境向量 `E` 在管線第一步就要注入，不能在最後才拿來修正結果。這是原始流程最大的設計缺陷，重寫的主要理由。

3. **不做即時外部 API 查詢。**
   球員資料庫離線批次建置，產出靜態 JSON，執行期零外部依賴。

## 目錄約定

```
/data
  zh/                  # 繁體中文，預設語言
    球員.json           # 現役球員庫（離線建置產物，勿手改，改 scripts/）
    歷史球員.json        # 歷史球員庫，同一套 schema，team 欄位改放代表年份
    原型.json           # 球場定位原型錨點（多數決分類用，見 engine/archetype.py）
    技能.json           # 技能庫 + 成本 C_i + 驗收指標
    題庫.json           # 問診題庫 + 分支規則（目前 18 題，見檔案內 _description）
    訓練菜單.json        # 技能 × 難度（entry/advanced/mastery）的訓練項目骨架，文案待填
  zh-Hans/             # 簡體中文，六個檔案跟 zh/ 結構完全一致，檔名用簡體字
  en/                  # 英文，同結構，檔名固定用原始英文（players.json/
                       # questions.json/archetypes.json/skills.json/
                       # players_alltime.json/drills.json）
  # 三個語言資料夾結構必須完全對應（id 集合、非文字欄位、座標、身體數據都要
  # 一致，只有文案不同），由 tests/engine/test_i18n_parity.py 把關。
  answers/              # tools/survey.html 匯出的本機測試作答，不對外公開、
                        # 不進 git（見 .gitignore），目錄本身用 .gitkeep 保留
  env_weights.json     # 三組聯賽環境倍率 E（暫定值，只放數字；顯示文字在前端 UI_STRINGS）
  # 尚未建立：videos.json（影片庫——skills.json 的 video_tags 目前只是佔位標籤，還沒接上）
/scripts                # 離線建庫腳本（Python）
/server                 # Flask 後端，唯一對外服務的伺服器（見 server/README.md）；
                        # lang 參數（"zh"/"zh-Hans"/"en"）決定讀哪個 data/{lang}/
/src
  /engine               # 純函數：向量計算、座標、匹配、排序。必須可單元測試
  /ui                   # 正式網站前端，由 server/app.py 服務
/tools
  survey.html           # 本機測試頁，不是正式網站的一部分（見 tools/README.md）
/tests
  engine/, scripts/     # 單元測試
  fixtures/             # 尚未建立，見下方開發紀律
```

## 開發紀律

- `/src/engine` 內不得有任何 I/O、隨機、時間依賴。全部純函數。
- 每個 engine 函數都要有單元測試。
- `tests/fixtures/james.json`（黃金測試案例，詳見 SPEC.md §11）還沒建立，`tests/fixtures/` 目錄目前不存在。補上之後，engine 對此輸入的輸出必須與已知的手工分析結論一致，這會是判斷公式權重是否校準對的標準；現在還沒有這個安全網。
- 資料檔用 JSON Schema 驗證，CI 要跑。

## 語言
程式碼與 commit 用英文；使用者介面文案用繁體中文。
使用清楚自然的文字，避免用抽象描述的語言，並讓句通暢，避免過度使用直接翻譯的專有名詞

