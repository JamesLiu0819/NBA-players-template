# 設計文件：選擇性 Google 登入 + 帳號功能

用途：這份文件記錄「使用者可以用 Google 帳號登入，取得跨裝置看回歷史結果、收藏球員、網站擁有者查看使用意見」這組功能的設計決策。
可手動調整的變數：無——這是設計文件，不是程式或資料。

- 日期：2026-10-21
- 狀態：已核准，進入實作計畫
- 對應討論：2026-10-21 brainstorming 討論；歷史結果「只留最新一筆還是存成清單」一題由 `/council --quick` 三人小組（Torvalds + Musashi + Feynman）裁決，結論見第 3.3 節

## 1. 背景與目標

網站目前完全無狀態：填問卷、送出、看結果，後端算完就直接回傳，沒有任何地方把使用者的作答或身份存起來。這次要加的是**選擇性**的帳號功能——網站本身維持完全不需要登入就能使用，登入是額外加值，給想要的使用者多三項能力：

1. 跨裝置、跨瀏覽器看回自己填過的問卷結果。
2. 收藏球員，之後直接找得到。
3. 網站擁有者（使用者本人）可以直接在網站上看使用意見，不用再手動開 Postico 下 SQL。

資料庫（Neon 免費版 Postgres）剛完成遷移（見 `server/db.py` 的 `init_db()` 註解），確認不會因為閒置被刪，這次功能可以放心建立在上面，不用再擔心資料庫過期的問題。

## 2. 範圍

**這次做：**
- Google OAuth 登入（唯一登入方式）
- 三張新資料表：`users`、`results`（歷史結果）、`favorites`（收藏球員）
- 送出問卷時，已登入的使用者自動存一筆結果（不用額外按鈕）
- 首頁偵測到已登入且存過結果，提供「查看我上次的結果」入口，不用重填問卷
- 球員卡片上的 ★ 收藏按鈕 + 獨立的「我的收藏」頁面
- `/api/admin/feedback`：只有信箱等於指定管理員信箱的使用者看得到

**這次不做（明確排除）：**
- email + 密碼登入、magic link，或任何 Google 以外的登入方式
- 完整歷史結果清單 UI——只顯示「最新一筆」，見第 3.3 節的 council 裁決
- 球員卡片以外的收藏入口（訓練計劃頁搜尋出來的球員、自選目標球員）——先不加，之後有需要再擴充
- 管理後台的任何寫入動作（刪除、回覆、標記已讀）——只能看
- 使用者自助刪除帳號、匯出個人資料的介面——真的有人要求再手動在資料庫處理
- 要求登入才能使用網站任何既有功能——問卷、球員模板、訓練計劃全部維持公開

## 3. 架構決策記錄

### 3.1 用 Authlib 接 Google OAuth，不是自己刻 OAuth 流程

**決策**：新增 `Authlib` 套件（`server/requirements.txt`），用它的 Flask 整合處理 Google OAuth 2.0 的授權碼交換、token 驗證。

**理由**：OAuth 的 state 參數防偽、token 交換、ID token 簽章驗證這些細節自己刻容易出錯，`Authlib` 是成熟、持續維護的套件，Flask 整合只需要幾行設定。這是這個專案第一次引入帳號系統，優先選「正確、別人已經踩過坑」的路線，不是「依賴最少」。

**已知限制**：多一個第三方套件依賴；Google Cloud Console 的 OAuth 用戶端設定是一次性的手動步驟，不在程式碼範圍內（見第 8 節）。

### 3.2 Session 用 Flask 內建的簽章 cookie，不是 token-based

**決策**：登入狀態存在 Flask 的 `session`（預設用 `SECRET_KEY` 簽章的 cookie，資料存在 cookie 本身，伺服器端不用另外存 session 資料）。

**理由**：這個專案沒有 app/行動裝置用戶端，只有瀏覽器前端，不需要 JWT 這類跨平台 token 機制。Flask 內建 session 是最簡單、文件最完整的做法，新增一個 `SECRET_KEY` 環境變數就能用，不用額外的 session 儲存（例如 Redis）。

**已知限制**：使用者清除瀏覽器 cookie 就會登出，沒有「記住我 30 天」以外的進階控制——這個專案的規模不需要更複雜的機制。

### 3.3 歷史結果：append-only 存原始作答，畫面只顯示最新一筆

**決策**：`results` 表只能 INSERT，不能 UPDATE 或 DELETE；存的是當次問卷的 18 題原始作答（`axis_answers`、`body_answers` 的 JSON），不是算好的結果快照；前端畫面目前只顯示「最新一筆」，重算時直接呼叫現有的 `compute_template_results()`，不用另外存一份算好的結果。

**理由**（`/council --quick` 三人小組一致結論，見同日對話紀錄）：
- append-only 比「先查有沒有舊紀錄、決定要 UPDATE 還是 INSERT」的 upsert 邏輯簡單，不會有兩個裝置同時送出造成的 race condition，也不會有「使用者資料不見了」這種不可逆的錯誤。
- 存原始作答、讀取時用現有引擎重算，比存算好的結果更不會「悄悄過期」——之後如果調整 `env_weights.json` 或技能的 `axis_relevance`，使用者看到的永遠是最新邏輯算出來的結果，不會卡在舊版本的數字。這個做法跟現有架構完全相容：`compute_template_results()` 本來就是每次請求即時呼叫，沒有任何預先算好、快取住的結果，不衝突。
- 只顯示最新一筆，不做完整歷史清單 UI，是因為目前沒有任何證據顯示使用者需要「比較我三個月前跟現在的差異」——這是單人業餘維護的側專案，不該為了想像中的需求先把 UI（分頁、空狀態、測試）都做出來。**但儲存本身一開始就是 append-only**，之後如果真的有人想看歷史清單，直接在現有的表上做 UI 就好，不用改資料庫 schema、不用搬資料。

**已知限制**：目前使用者沒辦法自己看到「我填過幾次」，只會看到最新一次。這是刻意的取捨，不是遺漏。

### 3.4 管理員身份：比對登入信箱跟環境變數，不是資料庫裡的角色欄位

**決策**：`/api/admin/feedback` 檢查目前登入者的 email 是否等於 `ADMIN_EMAIL` 這個環境變數,相等才回傳資料,否則一律 404(不是 403——不透露這支路由存在,避免被嘗試探測)。

**理由**：目前只有網站擁有者一人需要這個權限,不需要在 `users` 表裡加一個角色欄位、也不需要管理介面去指派角色——環境變數是最小複雜度的做法。之後如果真的需要多個管理員,改成逗號分隔的信箱清單一樣簡單,不用改資料庫 schema。

**已知限制**：换人或加人要改 Render 的環境變數、重新部署——這個頻率預期極低,換取現在不用做角色管理介面是合理的。

### 3.5 ★ 收藏先只加在 10 人對照表，其他球員卡片之後再說

**決策**：收藏按鈕這次只出現在「我的模板」頁 SECTION 2 的 10 人對照表卡片上。訓練計劃頁搜尋出來的自選球員、3 位深度模板卡片，這次都不加。

**理由**：10 人對照表是「使用者明確看到一位具體球員、產生『我喜歡這個人』念頭」最自然的時機。其他地方（搜尋結果、深度模板）之後觀察使用狀況，真的有需要再加，一次把所有球員卡片都加上收藏按鈕會把這次的改動範圍拉大，不符合 YAGNI。

## 4. 資料庫 Schema

```sql
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    google_sub TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS results (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    pool TEXT NOT NULL,
    lang TEXT NOT NULL,
    axis_answers JSONB NOT NULL,
    body_answers JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS favorites (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    player_id TEXT NOT NULL,
    pool TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, player_id, pool)
);
```

`google_sub` 是 Google 回傳的使用者唯一識別碼（ID token 裡的 `sub` 欄位），不是 email——同一個 Google 帳號的 `sub` 永遠不變，email 理論上可能變更，用 `sub` 當唯一鍵比較穩定。`favorites` 的 `UNIQUE (user_id, player_id, pool)` 讓「收藏同一位球員兩次」在資料庫層就不可能發生，不用在應用層額外檢查。

建表邏輯比照 `site_stats`、`feedback` 的既有模式，放進 `server/db.py` 的 `init_db()`，冪等、伺服器啟動時檢查並視需要建立。

## 5. 登入流程

```
使用者點「登入」
  → GET /auth/login：Authlib 導去 Google 的同意畫面
  → 使用者在 Google 同意
  → Google 導回 GET /auth/callback?code=...&state=...
  → 後端用 code 跟 Google 換 token，拿到 email / sub / name
  → 查 users 表：google_sub 存在就直接登入；不存在就先 INSERT 一筆再登入
  → session['user_id'] = ...、session['email'] = ...
  → 導回首頁
```

```
使用者點「登出」
  → POST /auth/logout：清空 session，導回首頁
```

本機開發跟正式站各需要在 Google Cloud Console 的 OAuth 用戶端設定裡登記一組「已授權的重新導向 URI」：
- 本機：`http://localhost:5001/auth/callback`
- 正式站：`https://nba-player-template.onrender.com/auth/callback`

## 6. 後端 API 設計

```
GET /api/me
Response 200（已登入）：{ "email": "...", "name": "..." }
Response 200（未登入）：{ "email": null, "name": null }
```

```
POST /api/template-results   （既有路由，行為新增一項）
```
邏輯不變；唯一新增的是：如果 `session` 裡有 `user_id`，在回傳結果之前額外把這次的 `axis_answers`／`body_answers`／`pool`／`lang` INSERT 進 `results` 表。這個寫入失敗（例如資料庫短暫斷線）不應該讓使用者拿不到問卷結果——比照 `increment_visit_count()` 的既有模式，包一層 try/except，寫入失敗只記錄到 log，不影響這次請求的回應。

```
GET /api/my-results/latest
Response 200（有存過結果）：跟 /api/template-results 回應格式完全相同
Response 204（未登入，或登入了但沒存過任何結果）：無內容
```
實作上是查 `results` 表裡該使用者 `created_at` 最新的一筆，把存的原始作答餵進既有的 `compute_template_results()`，回傳格式因此跟 `/api/template-results` 一致，前端可以直接重用 `renderTemplateReport()`。

```
GET /api/favorites
Response 200：{ "favorites": [ { "player_id": "...", "pool": "current", "name": "...", "team": "..." }, ... ] }
```
```
POST /api/favorites
Request: { "player_id": "...", "pool": "current" }
Response 200：{ "ok": true }
```
```
DELETE /api/favorites
Request: { "player_id": "...", "pool": "current" }
Response 200：{ "ok": true }
```
以上三支都要求已登入，未登入回傳 401。`player_id`／`pool` 的合法性比照現有 `/api/player-training-plan` 的檢查方式驗證。

```
GET /api/admin/feedback?lang=zh
Response 200（email 符合 ADMIN_EMAIL）：{ "feedback": [ { "created_at", "rating", "message", "lang" }, ... ] }
Response 404（不符合，或未登入）
```

## 7. 前端整合

- 導覽列：未登入顯示「登入」連結（連去 `/auth/login`）；已登入顯示使用者名字 + 「登出」，並新增「我的收藏」分頁。
- 首頁：`main()` 初始化時順便打一次 `GET /api/me`；已登入且 `GET /api/my-results/latest` 有資料，首頁顯示「查看我上次的結果」按鈕，點下去直接走現有的 `renderTemplateReport()` 流程，不經過問卷。
- 10 人對照表卡片：`renderMatchCardInner()` 加一顆 ★ 按鈕。已登入：點擊呼叫 `POST/DELETE /api/favorites` 並切換樣式。未登入：顯示提示文字「登入才能收藏」+ 登入連結，不直接把使用者導去 Google（避免問卷填到一半被打斷）。
- 新頁面「我的收藏」：比照現有四頁（首頁/問題/我的模板/訓練計劃）的頁面切換機制新增第五頁，列出 `GET /api/favorites` 回傳的球員，每筆可以移除、可以點進去直接跳到訓練計劃頁並選定那位球員（重用現有的自選目標球員機制）。
- 所有新文字（登入、登出、我的收藏、查看我上次的結果、登入才能收藏等）補齊三語（zh / zh-Hans / en）。

## 8. 部署設定變更

新增環境變數（Render 後台手動設定，不寫進程式碼或 git）：
- `SECRET_KEY`：Flask session 簽章用，隨機字串。
- `GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET`：Google Cloud Console 申請。
- `ADMIN_EMAIL`：網站擁有者的 Google 信箱。

`server/requirements.txt` 新增 `Authlib`。

Google Cloud Console 設定（一次性手動步驟，不在這次程式變更範圍內，但實作前需要先完成）：
1. 建立一個 Google Cloud 專案（免費）。
2. 設定 OAuth 同意畫面（External，只需要基本資訊）。
3. 建立 OAuth 用戶端 ID（類型：Web application），登記第 5 節列出的兩個重新導向 URI。
4. 拿到 Client ID / Client Secret，設成上面的環境變數。

## 9. 測試

- `server/db.py` 新增三張表的建表邏輯跟存取函數：比照 `site_stats`／`feedback` 的既有模式，記憶體 fallback（沒有 `DATABASE_URL` 時）要能直接單元測試。
- `server/test_app.py` 新增：
  - `/api/me` 登入／未登入兩種狀態的回應格式。
  - `/api/template-results` 在已登入 session 下會多寫一筆 `results`；未登入不會寫。
  - `/api/my-results/latest` 的 200／204 兩種情境，回傳格式跟 `/api/template-results` 一致。
  - `/api/favorites` 的 GET／POST／DELETE，含未登入 401、重複收藏不報錯（UNIQUE 約束）。
  - `/api/admin/feedback` 的 email 比對：符合、不符合、未登入三種情境都回傳預期的狀態碼。
- 不寫真的呼叫 Google OAuth 的整合測試——`/auth/callback` 的測試會 mock 掉 Authlib 跟 Google 的互動，只測「拿到使用者資訊之後，users 表跟 session 的狀態是否正確」這一段屬於這個專案自己的邏輯。
- 前端：沿用既有的 headless Chrome 手動驗證流程（而非新增自動化前端測試框架，跟現有慣例一致）。
