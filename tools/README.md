# 本機測試頁使用說明

**用途**：說明 `tools/survey.html`（本機用的 BARS 問診測試頁，收集作答、即時預覽排序、
匯出 `answers.json`）怎麼啟動跟使用。它不做任何決策 —— 唯一權威的計算結果來自
`scripts/run_priority.py`（呼叫 `src/engine` 既有的純函數）。

**這份文件本身沒有可手動調整的變數**（它是說明文件，不是程式或資料）；真正的可調變數在
`tools/survey.html`（`ENV_PRESETS` 等）跟 `data/questions.json` / `data/skills.json`
裡，各自的檔案開頭已經寫明。

## 啟動方式

`fetch()` 在 `file://` 底下會被瀏覽器的 CORS 政策擋掉，所以不能直接雙擊 HTML
檔打開，要跑一個本機靜態伺服器：

```bash
cd /Users/james/Desktop/NBA球員模板
python3 -m http.server 8000
```

然後瀏覽器打開 <http://localhost:8000/tools/survey.html>。

## 填寫流程

1. 依序填完四軸定位 16 題 + 技能行為 5 題 + 身材數值 6 題（共 27 題）。四軸定位跟
   技能行為每題都要選「哪句描述最像我」，不是憑感覺打分數；身材數值題直接填
   實際數字。
2. 在「環境權重」區塊，用三個預設按鈕之一（或手動拉滑桿）設定 5 個技能的 E
   值。**這些是暫定值**，`data/env_weights.json`（SPEC.md §12 issue #2）還沒
   建立。
3. 「即時預覽」區塊會隨填答即時重算座標與優先序——這只是預覽，不是正式結
   果。這個預覽不含身材數值/球員配對/深度模板,那些只有 `run_player_match.py`
   會算。
4. 27 題全部填完後，「匯出 answers.json」按鈕才會開啟。
   - 如果瀏覽器支援 File System Access API（Chrome / Edge），會跳出存檔對
     話框，**請手動導覽到 `data/answers/` 目錄**再存檔（瀏覽器不會自己選路
     徑）。
   - 如果瀏覽器不支援（例如 Safari），檔案會下載到瀏覽器預設的下載資料夾，
     **請手動把檔案搬到 `data/answers/`**。
5. 下次要重測時，用「載入 data/answers/ 最新一份」或「載入指定檔案」把之前的
   作答讀回來，不用重填 27 題。舊版(沒有身材數值題)匯出的作答檔也能正常載入,
   只是身材數值那 6 格會是空的。

## 取得正式結果

```bash
python3 scripts/run_priority.py                       # 優先序:讀 data/answers/ 最新一份
python3 scripts/run_priority.py data/answers/answers_20260908T153000.json  # 指定檔案

python3 scripts/run_player_match.py                    # 3位深度模板 + 10人對照表 + 反面對照
python3 scripts/run_player_match.py data/answers/answers_20260908T153000.json
```

`run_priority.py` 印出四軸座標、優先序表格（含 G/E/R/C 分項）、以及第一名為什麼
排在第二名前面的中文說明句。`run_player_match.py` 印出四軸座標、3 位深度模板(技
能最貼合/身體最貼合/天花板方向)、10 人對照表、反面對照——如果作答檔沒有身材數值
題的作答(例如舊版匯出的檔案),身體最貼合那一項會顯示「無法計算」而不是報錯。

## 為什麼頁面上有兩套算法，會不會算出不一樣的結果？

`tools/survey.html` 的即時預覽是用 JavaScript 重寫的一份 `src/engine` 邏輯
（逐行對照 `axis_position.py` / `skill_level.py` / `relevance.py` /
`priority.py`），純粹是為了讓你邊填邊看趨勢，不用每次都跑 Python。但這代表
兩套實作有可能因為手改其中一邊而悄悄長歪。這裡沒有自動化的跨語言比對（這台
機器沒裝 Node，也不打算為此新增任何相依套件），所以改動任一邊的公式後，請手
動照下面步驟比對：

1. 用 `tools/survey.html` 填一份完整作答，匯出到 `data/answers/`。
2. 記下瀏覽器「即時預覽」區塊顯示的四軸座標與優先序（含展開後的 G/E/R/C）。
3. 跑 `python3 scripts/run_priority.py <剛剛匯出的檔案>`。
4. 逐項比對兩邊的四軸座標、每個技能的 P 值與 G/E/R/C 分項數值（到小數點後兩
   位應該完全一致，因為兩邊都是同樣的四則運算，沒有隨機性或時間依賴）。
5. 若不一致：先看是不是 `tools/survey.html` 裡 `ENV_PRESETS` 常數跟
   `tests/engine/test_env_calibration.py` 裡的 `ENV_COLLAPSED_NO_SHOOTERS` /
   `ENV_TIGHT_PERIMETER_OPP_SHOOTERS` 手動同步的兩份數字不小心改到只改了一
   邊；再看是不是 JS 版的 `scoreAxisCoordinates` / `scoreSkillCurrentLevel` /
   `computeGap` / `computeRelevance` / `computePriority` / `rankPriorities`
   其中一個函式跟對應的 Python 實作邏輯分岔了（例如四捨五入、clamp 範圍、
   排序 tie-break 規則）。

## 範圍限制

這個測試頁不建立 `data/env_weights.json`（那是 issue #2，需要領域專家填寫完
整的 5 維 × 3 檔倍率表），三個預設按鈕只是測試用的暫定數字。它也不修改
`src/engine` 既有的計算邏輯，只在 JS 裡重寫一份供預覽用。
