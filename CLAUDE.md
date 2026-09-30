# CLAUDE.md — 籃球球員模板分析系統

## 專案一句話
把一套原本靠 AI 對話執行的籃球球員分析流程，改寫成**不需要 AI 介入**的規則化網站：使用者填題目量表（目前已上線 37 題：四軸定位 16 + 技能行為 15 + 身材數值 6〔選填〕；SPEC.md §5.5 規劃的完整版是 45–51 題，還缺聯賽環境、目標/限制兩塊）→ 系統計算四軸座標與優先序 → 輸出模板球員、訓練菜單。影片清單這塊還沒建（skills.json 的 `video_tags` 目前只是佔位標籤，沒有接真正的影片庫）。

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
  players.json          # 現役球員庫（離線建置產物，勿手改，改 scripts/）
  players_alltime.json  # 歷史球員庫，同一套 schema，team 欄位改放代表年份
  archetypes.json       # 球場定位原型錨點（多數決分類用，見 engine/archetype.py）
  skills.json           # 技能庫 + 成本 C_i + 驗收指標
  questions.json        # 問診題庫 + 分支規則（目前 37 題，見檔案內 _description）
  answers/              # tools/survey.html 匯出的本機測試作答，不對外公開
  # 尚未建立：env_weights.json（環境倍率表——現在是 src/ui/index.html 裡
  # 3 組暫定的 ENV_PRESETS，不是 SPEC.md §3.2 講的完整表）、videos.json
  # （影片庫——skills.json 的 video_tags 目前只是佔位標籤，還沒接上）
/scripts                # 離線建庫腳本（Python）
/server                 # Flask 後端，唯一對外服務的伺服器（見 server/README.md）
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

