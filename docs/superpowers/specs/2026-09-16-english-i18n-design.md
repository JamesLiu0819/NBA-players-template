# 設計文件：英文版(多語言)

用途：這份文件記錄「讓網站同時支援繁體中文跟英文」這個多語言(i18n)子專案的設計決策。對應 `docs/superpowers/specs/2026-09-10-public-web-app-design.md` §2 明確排除的範圍——當時的結論是「現有資料檔的文案全部是寫死的繁體中文字串,不是文字 key + 翻譯檔的結構,要做多語言得先做這個資料層重構,是獨立子專案」,這份文件就是那個獨立子專案的設計。
可手動調整的變數：無——這是設計文件,不是程式或資料。

- 日期：2026-09-16
- 狀態：已核准,進入實作計畫
- 對應討論：2026-09-16「該讓英文版上線了」

## 1. 背景與目標

網站目前所有文案(題目、錨點、球員特質、原型文案、技能名稱、頁面上的按鈕/說明文字)都是寫死的繁體中文字串,散落在四個 JSON 資料檔跟前端 HTML/JS 裡,另外還有少量藏在後端 Python 程式碼裡的字串模板(例如成長建議句型、訓練優先序的一句話說明)。這次要讓同一套球探報告網站同時支援繁體中文跟英文兩種介面語言,使用者可以自己切換。

**核心原則**：`/src/engine` 的純函數完全不碰這次改動。engine 只讀座標、id、`axis`、`reverse_scored`、各種數值權重這些結構性欄位,從來不讀人看的文字內容,所以語言是什麼、文字放在哪個資料夾,對 engine 的計算結果完全沒有影響。這也是為什麼這個子專案可以獨立於分析邏輯進行——跟 CLAUDE.md 的核心原則「AI 只用在文案潤飾,不用在分析」完全一致,這次要做的就是文案本身的中翻英,不動任何分析規則。

## 2. 範圍

**這次做：**
- 現役 150 位 + 歷史 65 位球員(共 215 位)的 `notable_traits` 全部翻譯——球員 `name`/`team` 欄位本來就是英文/縮寫,不用翻
- 16 題球風定位 + 15 題技能行為(各 5 個錨點)、6 題身材數值題的 `prompt` 全部翻譯,`reverse_scored: true` 的兩題(`axis_b3`、`axis_c1`)英文版也要維持「1=最少,5=最多」的字面頻率排列,跟中文版修正過的方向一致
- 12 個原型的 `name_zh`(欄位名稱維持不變,只是內容改放英文)跟 `flavor` 文案
- 15 個技能的 `name_zh`、`metric.action`
- Stage 1(球員模板)跟 Stage 2(技能行為問卷 + 訓練優先序)**都要**做,不是只做 Stage 1
- 後端程式碼裡少量寫死的中文字串模板(見 §3.4)
- 前端所有靜態文案(按鈕、標題、規則說明、找不到符合條件時的預設文字等)
- topnav 語言選項(目前是中/EN 兩個),選擇記在 `localStorage`
- 語言相關的查找一律用 §3.6 訂的「以 `lang` 為 key 的字典」寫法,不寫死二選一的判斷式,確保之後加第三個語言不用回頭改邏輯(使用者 2026-09-16 提出的明確要求)

**這次不做(明確排除)：**
- 不做瀏覽器語言自動偵測——使用者自己手動切換,理由跟 2026-09-13 topnav 導覽的決策一致(明確的使用者動作優於自動猜測)
- 不實際新增中/英以外的第三種語言——這次只做中跟英,但架構要禁得起之後加語言,不需要回頭重寫(見 §3.6)
- 不改 `/src/engine` 任何一行(見上方核心原則)
- 不重新設計球員資料庫的內容本身(座標、身材數值、招牌技能等)——這些是語言無關的結構性資料,英文版直接沿用中文版算好的值,不重新跑一次 `mock_axis_answers`/`score_axis_coordinates` 推導(見 §3.2)

## 3. 架構決策記錄

### 3.1 資料夾拆成 `data/zh/` 跟 `data/en/`,中文版檔名也改成繁體中文

**決策**：五個資料檔(題庫、球員、歷史球員、原型、技能)各自在 `data/zh/` 跟 `data/en/` 底下都有一份,結構(id、`axis`、`coordinates`、`reverse_scored`、`cost_C`、`axis_relevance` 等所有非文字欄位)完全一致,只有人看的文字欄位內容不同。這個「同結構、不同資料夾」的做法直接沿用現有 `players.json` / `players_alltime.json`(現役/歷史球員池)已經驗證過的模式,後端只要幫 `load_data` 多加一個 `lang` 參數,跟現有的 `pool` 參數是同一套邏輯,不用發明新機制。

**中文版檔名額外改成繁體中文**(使用者要求,方便一眼區分兩個資料夾的檔案)：

| 現有檔名(即將搬到 `data/en/`,英文版繼續用這組名字) | `data/zh/` 底下的新檔名 |
|---|---|
| `questions.json` | `題庫.json` |
| `players.json` | `球員.json` |
| `players_alltime.json` | `歷史球員.json` |
| `archetypes.json` | `原型.json` |
| `skills.json` | `技能.json` |

英文版檔名沿用現有的英文命名,不另外改——使用者的要求只針對中文版檔名,英文名字本來就是整個程式碼庫預設的慣例(變數、函式命名都是英文),不需要額外區分。

**代價**：這是目前唯一會touching 到「檔名」本身的改動,牽涉到的檔案比想像中多——所有直接用字串寫死檔名的地方都要跟著改(`scripts/build_players_seed.py`、`build_players_alltime_seed.py`、`run_player_match.py`、`run_priority.py`、`server/app.py`、以及好幾支測試檔)。`/src/engine` 裡雖然有幾處註解提到這些檔名,但都只是文件性質的註解(不是真的檔案 I/O),語意上要跟著更新,但不影響任何測試或行為。

### 3.2 英文版球員資料是從中文版「結構複製 + 只翻文字欄位」,不是重新建庫

**決策**：`data/en/球員.json`(即 `players.json`)不透過 `scripts/build_players_seed.py` 的 `mock_axis_answers`/`score_axis_coordinates` 推導管線重新產生,而是讀取已經建好的 `data/zh/球員.json`,把每個球員的 `notable_traits` 換成對應的英文翻譯,其餘欄位(`coordinates`、`body`、`mock_axis_answers`、`mock_skill_answers`、`signature_skill_id`、`learnability_flag`、`id`、`name`、`team`)逐位元複製,不重新計算。

**理由**：這些欄位本來就跟語言無關,球員的座標、身材數值、招牌技能是「這個球員長什麼樣子」的事實資料,不是文案。如果英文版另外重新跑一次建庫管線,兩個語言版本的座標理論上應該要算出一樣的值,但沒有任何機制保證這件事,未來只要中文版建庫腳本改了什麼細節,兩邊就可能悄悄產生分歧,又要花時間debug「為什麼英文版跟中文版的模板配對結果不一樣」。直接結構複製從根本上排除這個風險類別,而且這正是 §4 要寫的資料完整性測試想要驗證的事情。

`data/en/歷史球員.json`(即 `players_alltime.json`)適用同一個原則。

### 3.3 後端 `lang` 參數,跟現有 `pool` 參數同一套模式

**決策**：`load_data(pool="current", lang="zh")`、`load_archetypes(lang="zh")`——合法值來自單一常數 `SUPPORTED_LANGUAGES = ("zh", "en")`(位置見 §3.6),不合法回傳 400(跟現有 `pool` 驗證邏輯一樣)。`POST /api/template-results`、`POST /api/priority-results`、`GET /api/form-data` 都多接受一個選填的 `"lang"` 欄位,預設 `"zh"`(維持向後相容,舊的前端呼叫不用改就能繼續動)。

### 3.4 後端程式碼裡的字串模板也要 lang-aware

**決策**：目前有兩處真的會出現在 API 回應裡、卻是寫死在 Python 程式碼裡(不在 JSON 資料檔裡)的中文字串,要各自加上英文版本：

1. `scripts/run_player_match.py` 的 `describe_growth_recommendation()`——`D_AXIS_GROWTH_TEMPLATE`(D 軸差距時的固定句子)跟 `f"{action}的練習"` 這個組句方式,都要有對應的英文版本。
2. `scripts/run_priority.py` 的 `format_dominant_factor_sentence()`——`FACTOR_LABELS`(G/E/R/C 的顯示名稱)跟组句模板,也要有英文版本。

兩個函式都新增一個 `lang="zh"` 參數,依語言選對應的字典/模板(實作方式見 §3.6 的擴充原則,不能寫成 `if lang == "zh"` 這種二選一判斷式)。`build_scouting_report()` 不用改——它現在已經只是直接回傳 `archetype['flavor']`,只要 `archetype` 是從正確語言的資料夾讀出來的,這裡自動就是對的語言,不需要額外的模板。

`main()` 函式(CLI 專用的終端機輸出,不是網站 API 會呼叫的路徑)裡其餘的中文 `print()` 字串(例如「你的四軸座標:」)維持原樣不用翻——這些只有開發者本機下指令測試時會看到,不是使用者會接觸到的介面。

### 3.5 前端：topnav 語言選項 + `UI_STRINGS` 字典 + `localStorage`

**決策**：`src/ui/index.html` 新增一個 `UI_STRINGS = { zh: {...}, en: {...} }` 物件,涵蓋所有寫死在 HTML/JS 裡的靜態文案(標題、按鈕文字、規則說明、「目前沒有符合條件的球員」這類預設訊息,包含目前寫死中文的 `AXIS_LABELS`)。topnav 依 `SUPPORTED_LANGUAGES`(定義見 §3.6)動態渲染對應數量的語言選項按鈕,目前陣列長度是 2,畫面上就是「中/EN 兩個按鈕」的效果。點擊其中一個後：(1) 把 `state.lang` 設成被點的那個值、寫進 `localStorage`,(2) 把畫面上目前看得到的 `UI_STRINGS` 文字換成新語言,(3) 如果使用者已經在作答中,重新渲染當前這一題(沿用 2026-09-13 做的單題精靈架構,只重繪目前這張卡片,不用整頁重整),(4) 之後每一次呼叫後端 API 都帶上目前的 `lang`。

作答中途切換語言不會清空已經填的答案——答案是用題目 `id` 存的,`id` 在兩個語言版本裡完全一樣,只有畫面上顯示的文字語言不同。

### 3.6 多語言擴充原則(2026-09-16 使用者提出：網站之後會加更多語言)

使用者明確提出這次不是只做中英兩語,之後還會加其他語言,所以這次翻譯過程中發現的「輸出裡有寫死、不會自動依語言調整」的地方,要在這次一併修正,不要只是暫時繞過中英兩語就算了。具體要求：

**決策**：所有語言相關的查找,一律用「以 `lang` 字串為 key 的字典查找」,禁止用 `if lang == "zh": ... else: ...` 或 `elif` 這種只考慮兩種語言的判斷式——不管是 §3.4 的 Python 字串模板,還是 §3.5 前端的 `UI_STRINGS`,都要是 `TEMPLATE[lang]` 這種形狀。這樣以後加第三個語言,永遠只需要「新增資料」(新的 `data/<lang>/` 資料夾、字典裡多一組 key),不需要「修改邏輯」——不會有任何一段程式碼的 if/else 分支數量要跟著語言數量調整。§3.5 的 topnav 語言選項已經是照這個原則設計(迴圈產生按鈕,不是寫死的二選一切換)。

新增一個單一的合法語言清單常數(後端 `server/app.py` 一份、前端 `index.html` 一份,兩邊值要一致),所有驗證(`lang` 參數合不合法)、UI 產生語言選項的地方都讀這個清單,不要在多個檔案各自寫死 `("zh", "en")`：

```python
# server/app.py
SUPPORTED_LANGUAGES = ("zh", "en")
```

```js
// src/ui/index.html
const SUPPORTED_LANGUAGES = ["zh", "en"];
```

## 4. 資料完整性測試(新增)

新增一支測試(例如 `tests/engine/test_i18n_parity.py`),對 `data/zh/` 跟 `data/en/` 的五組檔案逐一比對：
- id 集合完全一致(不多不少)
- 所有非文字欄位(`axis`、`coordinates`、`reverse_scored`、`cost_C`、`axis_relevance`、`video_tags`、`metric.denominator`/`direction`/`thresholds`、`body`、`mock_axis_answers`、`mock_skill_answers`、`signature_skill_id`、`learnability_flag`、球員的 `name`/`team`)逐位元相等
- 每個應該要有文字的欄位(`prompt`、`anchors` 的 5 個值、`notable_traits`、`flavor`、`name_zh`、`metric.action`)兩個語言版本都不是空字串,而且**不相等**(避免漏翻——如果中英文完全一樣,大機率是忘了翻,直接讓測試失敗提醒)

這支測試是這次子專案最重要的安全網:未來不管是新增球員、修改某一題的用詞,只要忘記同步更新另一個語言版本,CI 就會抓到,不會等到使用者真的切換語言才發現某個地方还是中文或英文缺了一塊。

## 5. 檔案異動範圍

有實際檔案 I/O(不只是註解)依賴這些資料檔路徑的檔案,這次都要跟著更新路徑常數：`scripts/build_players_seed.py`、`scripts/build_players_alltime_seed.py`、`scripts/run_player_match.py`、`scripts/run_priority.py`、`server/app.py`、`server/test_app.py`,以及 `tests/engine/test_archetypes_data.py`、`tests/engine/test_players_data.py`、`tests/engine/test_data_integrity.py`、`tests/engine/test_env_calibration.py`、`tests/scripts/test_mock_answers.py`。`/src/engine/*.py` 裡提到檔名的地方都只是註解,語意上更新即可,不影響任何測試或行為。

## 6. 測試

- §4 的資料完整性測試是這次新增的核心測試。
- `server/test_app.py` 新增 `lang="en"` 版本的請求測試,確認回應內容(archetype、scouting_report、growth_recommendation、dominant_factor_sentence)是英文而非中文,以及缺少 `lang` 欄位時預設行為維持中文(向後相容)。
- 前端沒有自動化測試框架,維持現有慣例(本機啟動 Flask 手動用 curl/瀏覽器驗證)。
