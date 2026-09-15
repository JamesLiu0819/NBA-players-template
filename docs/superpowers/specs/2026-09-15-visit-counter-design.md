# 設計文件：首頁瀏覽人次計數器

用途：這份文件記錄「首頁右上角顯示瀏覽人次」這個小功能的設計決策,同時是「之後要做 email 登入系統」的第一塊基礎建設(先把持久化資料庫接起來)。
可手動調整的變數：無——這是設計文件,不是程式或資料。

- 日期：2026-09-15
- 狀態：已核准,進入實作計畫
- 對應討論：2026-09-15 email 登入系統規劃(過程中發現 Resend 沒有自己的驗證域名就沒辦法寄信給真實使用者,登入系統因此延後;瀏覽人次計數器不需要 email/域名,拆出來先做)

## 1. 背景與目標

使用者想在首頁右上角看到「這個網站被打開過幾次」。這是網站第一次需要「跨部署保留下來的狀態」——現有架構完全無狀態,每次作答送出後端算完結果就直接回傳,什麼都沒存,Render 免費方案的檔案系統重新部署也會清空,所以不能只是在後端記憶體裡存一個數字。

這也是原本「使用者 email 登入 + 查看歷史紀錄」規劃的一部分,但那個功能需要寄信服務(Resend),而 Resend 沒有自己驗證過的域名之前只能寄信給帳號本人,對其他使用者無效——使用者目前沒有域名,決定先不買,登入系統整個延後。瀏覽人次計數器不需要寄信、不需要域名,是可以獨立拆出來現在就做的部分,而且會用到的資料庫之後登入系統上線時可以直接沿用,不是重工。

## 2. 範圍

**這次做：**
- 一個持久化計數器,每次有人打開首頁就 +1
- 首頁右上角(topnav 的 `.topnav-actions` 區域,登入/選單按鈕旁邊)顯示目前總數
- 後端接一個 Render 免費方案的 Postgres 資料庫

**這次不做(明確排除)：**
- email 登入系統本身(見上方背景說明,延後到使用者有域名可以驗證 Resend 為止)
- 不重複訪客/不重複使用者的統計——使用者明確說「每個人點進網站就記錄一次」,是單純的頁面載入次數,不需要用 cookie/session 判斷是不是同一個人
- 歷史趨勢圖表、每日/每週細分數字——只要一個累計總數

## 3. 架構決策記錄

### 3.1 用 Render 免費 Postgres,不是檔案或記憶體

**決策**：新增一個 Render Postgres 資料庫服務(免費方案),後端透過 `DATABASE_URL` 環境變數連線。

**理由**：Render 免費 web service 沒有永久磁碟,重新部署會清空檔案系統跟程式記憶體,所以不能用 SQLite 檔案或是 Python 全域變數存這個數字。Postgres 是 Render 平台原生支援、免費方案就有的選項,不用另外註冊第三方服務帳號。

**已知限制**：Render 免費 Postgres 90 天後會過期,到期需要手動續約或升級成付費方案(約 $7/月起)——這個限制是使用者在規劃階段已經知情並接受的取捨,不是這次實作要解決的問題。

### 3.2 本機/測試環境:記憶體 fallback,不強制裝本機 Postgres

**決策**：`server/db.py` 在沒有讀到 `DATABASE_URL` 環境變數時(本機開發、跑測試套件),自動退化成一個進程內的記憶體計數器,不連真的資料庫。

**理由**：這個專案目前的開發流程完全不需要裝資料庫(`server/test_app.py` 用 Flask 的 `test_client()`,標準函式庫等級的輕量);硬性要求本機/CI 都要有一個真的 Postgres 才能跑測試,會提高每個人貢獻這個專案的門檻,不成比例。記憶體 fallback 同時也是測試會實際跑到的程式路徑(不是額外 mock 出來的假邏輯),遞增/回傳的邏輯本身有被測試覆蓋到。

**代價**：本機開發時看到的數字每次重啟伺服器就會歸零,跟正式站不同步——這是刻意接受的行為,不是 bug。

### 3.3 只存一個累計數字,不記錄逐筆造訪紀錄

**決策**：`site_stats` 資料表只有一列一個欄位(`visit_count`),用 `UPDATE ... SET visit_count = visit_count + 1 RETURNING visit_count` 原子遞增並取得最新值,不是每次造訪都新增一筆紀錄。

**理由**：需求就是「總共被打開幾次」這一個數字,不需要查詢過去某個時間點造訪了誰/幾次——逐筆記錄除了增加資料庫負擔外沒有對應到任何需求。單列原子遞增也天然避免了併發請求同時讀寫造成的計數錯誤(不需要額外加鎖)。

## 4. 資料庫 Schema

```sql
CREATE TABLE IF NOT EXISTS site_stats (
  id INTEGER PRIMARY KEY,
  visit_count BIGINT NOT NULL DEFAULT 0
);
INSERT INTO site_stats (id, visit_count)
  VALUES (1, 0)
  ON CONFLICT (id) DO NOTHING;
```

`id` 固定是 1,整張表永遠只有這一列。建表跟初始化這列的邏輯放在 `server/db.py` 裡,伺服器啟動時檢查並視需要建立(冪等,重複執行不會出錯或重置數字)。

## 5. 後端 API 設計

```
POST /api/site-visit
Content-Type: application/json (無 request body)

Response 200:
{ "visit_count": 1234 }
```

- 每次呼叫都會讓 `visit_count` +1 並回傳遞增後的值——不是冪等的查詢端點,是「記錄一次造訪」的動作,所以用 POST。
- 沒有錯誤情境需要回傳給前端特殊處理:資料庫連線失敗的話回傳 500,前端收到非 200 就直接不顯示數字(見下方第 6 節),不彈錯誤訊息給使用者——這只是個裝飾性的小數字,不值得為它打斷使用者的作答流程。

`server/db.py` 提供：
- `get_db_connection()`——用 `DATABASE_URL` 建立連線;環境變數不存在時回傳 `None`。
- `increment_visit_count()`——如果有資料庫連線就執行上面的 SQL 並回傳新值;沒有連線(本機/測試)就對一個模組層級的整數變數 +1 並回傳,行為對呼叫端完全透明,呼叫端不需要知道現在是哪一種模式。

## 6. 前端整合

`main()` 一開始(跟 `fetch("/api/form-data")` 平行,不互相等待,任何一邊失敗都不影響另一邊)呼叫一次 `POST /api/site-visit`：

```js
fetch("/api/site-visit", { method: "POST" })
  .then((res) => (res.ok ? res.json() : null))
  .then((data) => {
    if (data && typeof data.visit_count === "number") {
      document.getElementById("visit-counter").textContent = `👁 ${data.visit_count.toLocaleString()}`;
      document.getElementById("visit-counter").style.display = "inline";
    }
  })
  .catch(() => {}); // 靜默失敗,不顯示計數器就好
```

HTML 上在 `.topnav-actions`(登入按鈕左邊)新增一個預設隱藏的 `<span id="visit-counter" class="visit-counter" style="display:none"></span>`,成功拿到數字才顯示,避免載入過程中或失敗時出現「0」這種誤導畫面。

## 7. 部署設定變更

`render.yaml` 新增一個 `databases:` 區塊定義 Postgres 服務,並在既有 web service 的 `envVars` 用 `fromDatabase` 參照,讓 Render 自動把連線字串注入成 `DATABASE_URL`,不用手動複製貼上。`server/requirements.txt` 新增 `psycopg[binary]`(連 Postgres 用的驅動)。

## 8. 測試

- `server/db.py` 的記憶體 fallback 邏輯:直接單元測試(不需要 `DATABASE_URL`,天然就是測試環境會走到的路徑)——遞增行為、初始值、連續呼叫累加正確。
- `server/test_app.py` 新增 `POST /api/site-visit` 的路由測試:回傳 200、回應內有 `visit_count` 整數欄位、連續呼叫兩次數字會遞增。
- 不寫連到真的 Render Postgres 的整合測試——跟專案目前「後端測試用 Flask test_client,不連外部服務」的既有慣例一致。
