# 設計文件：公開網頁版(Flask 後端 + 新前端)

用途：這份文件記錄「讓別人也能在網頁上填答並看到結果」這個產品化階段的設計決策,對應 SPEC.md §12 未決問題 #4(前端技術棧)。
可手動調整的變數：無——這是設計文件,不是程式或資料。

- 日期：2026-09-10
- 狀態：已核准,進入實作計畫
- 對應 SPEC.md：§10(P3 階段：HTML 渲染)、§12 issue #4(前端技術棧,本文件是該問題的解答)、§9(最終輸出規格,本次只實作其中已經算得出來的子集)

## 1. 背景與目標

目前使用者要看到分析結果,必須：開本機伺服器 → 填 `tools/survey.html` → 匯出 JSON → 手動搬到 `data/answers/` → 跑 Python CLI 腳本看終端機輸出。這條路只有開發者自己能走。這次要做的是「讓任何人開一個網址、填答、當場在頁面上看到結果」的公開版本。

使用者提出的三個長期目標(多語言、全球使用、可持續維護)裡,**多語言明確排除在這次範圍外**(見 §2);全球使用/可維護這兩點是選擇「後端重用 Python engine」而非「前端 JS 重寫」的直接理由——詳見下方架構決策的討論記錄。

## 2. 範圍

**這次做：**
- Flask 後端,一支 API 把作答轉成結果 JSON
- 新的公開前端頁面(`/src/ui`),取代「填答→匯出檔案→跑 CLI」這個流程,改成「填答→送出→頁面上看到結果」
- 部署到 Render,拿到一個任何人都能打開的網址

**這次不做(明確排除)：**
- **多語言/i18n**——現有資料檔的文案(題目、錨點、球員介紹)全部是寫死的繁體中文字串,不是「文字 key + 翻譯檔」的結構。要做多語言得先做這個資料層重構,是獨立子專案。
- SPEC §9 裡 engine 還沒算出來的輸出項：訓練菜單、比賽日執行清單、影片資料庫、環境校準說明表(現有的 G/E/R/C 展開跟主導因子說明可以算部分涵蓋,但不是 §9 第 7 項要求的完整格式)。UI 不假裝顯示不存在的東西。
- `tools/survey.html`(本機測試工具)不受影響,繼續存在,兩者並存。
- 使用者帳號、歷史紀錄(SPEC §12 issue #5,P4 前不需要)。
- 環境權重問卷、目標/限制/困擾題組(SPEC §5.5 剩下的兩塊,跟這次的產品化是兩件事)——這次的 API 一樣沿用「使用者手動選環境預設值」的作法,跟 `tools/survey.html` 現在的行為一致。

## 3. 架構決策記錄

### 3.1 計算邏輯放後端,不放前端 JS

**決策**：新增一個 Flask 後端,直接 import 現有、已測試過的 `src/engine`,不把邏輯重寫成 JavaScript。

**理由**：
1. `tools/survey.html` 已經示範過純前端 JS 重寫的代價——目前只重寫了優先序那一段,就已經需要 `tools/README.md` 那套手動比對步驟來防止兩套邏輯漂移。這次要涵蓋的計算(四軸座標、技能缺口、相關性、優先序、最近鄰配對、深度模板、反面對照——六個 engine 模組)如果全部重寫成 JS,維護稅會是現在的好幾倍,直接違背「可持續修改精進」這個目標。
2. 全球使用的流量規模,一個免費/最低階後端方案完全撐得住,不構成選擇純前端的理由。
3. 代價：這是專案第一次引入外部相依套件(Flask)。之前所有東西都刻意只用標準函式庫,這次是有意識的例外。

**SPEC.md 的落差**：SPEC §6.4 原本寫「網站直接載入,最近鄰查詢在前端算」,隱含的是純前端架構。這次的決策推翻了這個假設,是使用者在充分了解取捨後的決定,不是疏忽——但代表 SPEC.md 這段之後應該更新,避免跟實作對不上。

### 3.2 新前端不取代 `tools/survey.html`

**決策**：`/src/ui` 是新的公開產品前端,`tools/survey.html` 維持原樣,兩者並存。

**理由**：`tools/survey.html` 的價值是「不需要後端、離線也能測試 engine 邏輯」,這個用途在後端存在之後依然成立(例如本機開發時不想啟動 Flask)。拿掉它沒有任何好處,保留的維護成本也低(它本來就是刻意做成獨立、自我描述的單一 HTML 檔)。

## 4. API 設計

```
POST /api/results
Content-Type: application/json

Request body（跟 answers.json 匯出格式相同）：
{
  "axis_answers": [{"question_id": str, "score": 1-5}, ...],   // 16 筆,必須齊全
  "skill_answers": [{"question_id": str, "score": 1-5}, ...],  // 15 筆,必須齊全
  "body_answers": [{"question_id": str, "value": number}, ...], // 0 或 6 筆(可省略——身體最貼合會顯示無法計算)
  "env": {skill_id: number, ...}                                 // 15 個技能都要有值
}

Response 200：
{
  "coordinates": {"A": number, "B": number, "C": number, "D": number},
  "priorities": [
    {"skill_id": str, "name_zh": str, "P": number, "G": number, "E": number, "R": number, "C": number},
    ... 15 筆,已排序
  ],
  "dominant_factor_sentence": str | null,   // 第一名 vs 第二名的說明句,平手時是打平訊息
  "deep_templates": {
    "skill_fit": {"name": str, "team": str} | null,
    "body_fit": {"name": str, "team": str} | null,        // body_answers 沒給就是 null
    "ceiling": {"name": str, "team": str} | null
  },
  "top_10": [
    {"rank": int, "name": str, "team": str, "distance": number, "fit_stars": int,
     "notable_traits": [str, ...], "dominant_diff_axis": str, "growth_recommendation": str},
    ... 10 筆
  ],
  "anti_template": {"name": str, "team": str} | null
}

Response 400：作答不齊全或格式錯誤時,回傳 {"error": "說明文字"}，前端顯示成表單驗證訊息，不是把 500 錯誤丟給使用者。
```

輸入驗證(哪些欄位一定要有、範圍檢查)沿用 `src/engine` 各函數已經有的 `ValueError`——後端把這些例外攔截下來轉成 400 回應,不新增一套重複的驗證邏輯。

## 5. 前端內容規劃

單頁應用,兩個畫面狀態：**填答畫面**(沿用 `tools/survey.html` 已經驗證過的模式：BARS 選項旁邊顯示行為錨點文字、進度條、環境權重預設按鈕)跟**結果畫面**(送出後切換,顯示 API 回傳的內容)。視覺設計(排版、配色、字體)這次會認真做,不是延用 `tools/survey.html` 的陽春風格——實作時用 `frontend-design` 技能引導。

結果畫面要涵蓋 API 回傳的五塊：四軸座標、優先序(含展開 G/E/R/C 的能力)、3 位深度模板、10 人對照表、反面對照——內容跟現有 CLI 輸出的資訊量一致,只是用網頁呈現。

## 6. 部署

Render,Python Web Service,免費方案。`server/requirements.txt` 只放 `Flask` 跟 `gunicorn`。靜態前端檔案由同一個 Flask app 用 `send_from_directory` 服務(不另外開靜態網站服務,降低部署複雜度)。

## 7. 待確認事項

無阻塞性未決問題——範圍、架構、API、部署平台都已經跟使用者確認過。實作時如果 Flask 側需要對 `scripts/run_priority.py`、`scripts/run_player_match.py` 做小幅重構(把可重用的計算函數跟 CLI 專用的 `main()`/`print` 邏輯切乾淨)才能被後端 import,屬於實作細節,會在計畫文件裡列成具體任務,不是設計層級的未決問題。
