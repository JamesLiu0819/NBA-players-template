# 本機測試頁使用說明

**用途**：說明 `tools/survey.html`（本機用的 BARS 問診測試頁，收集作答、即時預覽
六軸座標、匯出 `answers.json`）怎麼啟動跟使用。它不做任何決策 —— 唯一權威的計算結果
來自 `scripts/run_player_match.py`（呼叫 `src/engine` 既有的純函數）。

**這份文件本身沒有可手動調整的變數**（它是說明文件，不是程式或資料）；真正的可調變數在
`data/zh/題庫.json` 等資料檔，各自的檔案開頭已經寫明。

## 啟動方式

`fetch()` 在 `file://` 底下會被瀏覽器的 CORS 政策擋掉，所以不能直接雙擊 HTML
檔打開，要跑一個本機靜態伺服器：

```bash
cd /Users/james/Desktop/NBA球員模板
python3 -m http.server 8000
```

然後瀏覽器打開 <http://localhost:8000/tools/survey.html>。

## 填寫流程

1. 依序填完六軸定位 12 題（A、B1、B2、C1、C2、D 各 2 題）+ 身材數值 6 題，共 18 題。
   六軸定位每題都要選「哪句描述最像我」，不是憑感覺打分數；身材數值題直接填實際數字。
   技能行為題已經從題庫移除（2026-10），技能不再由問卷直接評分，而是由六軸座標推算。
2. 「即時預覽」區塊會隨填答即時重算六軸座標。這只是預覽，不是正式結果；它不含身材
   數值、球員配對與訓練計劃，那些只有 `run_player_match.py` 會算。
3. 18 題全部填完後，「匯出 answers.json」按鈕才會開啟。
   - 如果瀏覽器支援 File System Access API（Chrome / Edge），會跳出存檔對
     話框，**請手動導覽到 `data/answers/` 目錄**再存檔（瀏覽器不會自己選路
     徑）。
   - 如果瀏覽器不支援（例如 Safari），檔案會下載到瀏覽器預設的下載資料夾，
     **請手動把檔案搬到 `data/answers/`**。
4. 下次要重測時，用「載入 data/answers/ 最新一份」或「載入指定檔案」把之前的
   作答讀回來，不用重填。舊版匯出的檔案裡如果還有 `skill_answers` 或 `env` 欄位，
   載入時會直接忽略，不會報錯。

## 取得正式結果

```bash
python3 scripts/run_player_match.py                    # 3 位深度模板 + 10 人對照表 + 訓練計劃
python3 scripts/run_player_match.py data/answers/answers_20260908T153000.json
```

`run_player_match.py` 印出六軸座標、3 位深度模板（技能最貼合／身體最貼合／天花板方向）、
10 人對照表。如果作答檔沒有身材數值題的作答，身體最貼合那一項會顯示「無法計算」而不是報錯。

## 為什麼頁面上有兩套算法，會不會算出不一樣的結果？

`tools/survey.html` 的即時預覽是用 JavaScript 重寫的一份 `src/engine` 邏輯（目前只有
`scoreAxisCoordinates`，逐行對照 `src/engine/axis_position.py`），純粹是為了讓你邊填
邊看趨勢，不用每次都跑 Python。但這代表兩套實作有可能因為手改其中一邊而悄悄長歪。
這裡沒有自動化的跨語言比對（這台機器沒裝 Node，也不打算為此新增任何相依套件），所以
改動任一邊的公式後，請手動照下面步驟比對：

1. 用 `tools/survey.html` 填一份完整作答，匯出到 `data/answers/`。
2. 記下瀏覽器「即時預覽」區塊顯示的六軸座標。
3. 跑 `python3 scripts/run_player_match.py <剛剛匯出的檔案>`，看它印出的六軸座標。
4. 逐項比對六軸座標（到小數點後一位應該完全一致，兩邊都是同樣的四則運算，沒有隨機性
   或時間依賴）。
5. 若不一致：先看是不是 JS 版的 `scoreAxisCoordinates` 跟 `src/engine/axis_position.py`
   的邏輯分岔了（例如反向計分的 `6 - score`、平均的分母、或 0–100 的換算）。

## 範圍限制

這個測試頁只收集六軸定位與身材數值題的作答，不做任何評分決策，也不建立或修改
`data/env_weights.json` 之類的資料檔。
