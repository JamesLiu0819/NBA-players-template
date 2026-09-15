# 首頁瀏覽人次計數器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每次有人打開首頁就讓一個持久化計數器 +1,並在首頁右上角(topnav)顯示目前總數。

**Architecture:** 新增 `server/db.py` 包裝一個 Postgres 連線(讀 `DATABASE_URL` 環境變數),沒有這個環境變數時(本機開發、跑測試)自動退化成進程內的記憶體計數器,呼叫端(`server/app.py`)完全不需要知道現在是哪一種模式。後端新增一支 `POST /api/site-visit` 路由,前端在 `main()` 旁邊平行、不等待地打一次這支 API,成功才把回傳的數字顯示在 topnav 右上角。

**Tech Stack:** Flask(既有)、`psycopg[binary]`(新增,Postgres 驅動)、Render Postgres 免費方案、vanilla JS(既有前端,無框架)。

## Global Constraints

- 資料庫只存一個累計數字(單列單欄位 `site_stats.visit_count`),不記錄逐筆造訪——見 spec §3.3。
- 不做不重複訪客/session 判斷,單純每次頁面載入都 +1——見 spec §2。
- 本機開發與測試套件一律不連真的 Postgres,`DATABASE_URL` 未設定時走記憶體 fallback,且這個 fallback 路徑就是測試實際覆蓋到的路徑——見 spec §3.2、§8。
- 計數器是裝飾性功能,前端呼叫失敗時靜默不顯示,不彈錯誤訊息、不打斷作答流程——見 spec §5。
- 程式碼與 commit message 用英文;使用者看得到的文字(topnav 顯示的數字說明、任何 UI 字串)用繁體中文——CLAUDE.md 慣例。
- `server/`、`scripts/` 可以做 I/O;`/src/engine` 維持純函數,這個功能完全不碰 `/src/engine`。
- 對應規格文件：`docs/superpowers/specs/2026-09-15-visit-counter-design.md`。

---

### Task 1: `server/db.py` — 計數器持久化邏輯(記憶體 fallback + Postgres)

**Files:**
- Create: `server/db.py`
- Test: `server/test_db.py`

**Interfaces:**
- Consumes: 環境變數 `DATABASE_URL`(選填,字串或未設定)。
- Produces(給 Task 2 用):
  - `init_db() -> None` —— 冪等,確保 `site_stats` 表跟唯一那一列存在;沒有 `DATABASE_URL` 時是 no-op。
  - `increment_visit_count() -> int` —— 讓計數器 +1,回傳遞增後的新值。

- [ ] **Step 1: 寫失敗的測試**

建立 `server/test_db.py`:

```python
# 用途：測試 db.py 在沒有 DATABASE_URL 時的記憶體 fallback 遞增邏輯——這是
# 本機開發跟測試套件實際會跑到的路徑,不連真的 Postgres(見
# docs/superpowers/specs/2026-09-15-visit-counter-design.md)。Postgres 路徑
# 本身不寫自動化測試,跟專案既有慣例一致(測試不連外部服務)。
# 執行方式：cd server && ../.venv/bin/python3 -m unittest test_db -v

import importlib
import os
import unittest


class InMemoryVisitCounterTest(unittest.TestCase):
    def setUp(self):
        # 不管實際環境有沒有設定 DATABASE_URL,測試一律強制走記憶體路徑；
        # reload 讓每個測試方法從乾淨的計數器狀態開始。
        self._original_database_url = os.environ.pop("DATABASE_URL", None)
        import db
        importlib.reload(db)
        self.db = db

    def tearDown(self):
        if self._original_database_url is not None:
            os.environ["DATABASE_URL"] = self._original_database_url

    def test_first_increment_returns_one(self):
        self.assertEqual(self.db.increment_visit_count(), 1)

    def test_increments_accumulate_across_calls(self):
        self.db.increment_visit_count()
        self.db.increment_visit_count()
        self.assertEqual(self.db.increment_visit_count(), 3)

    def test_init_db_is_a_no_op_without_database_url(self):
        self.db.init_db()
        self.assertEqual(self.db.increment_visit_count(), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 執行測試,確認失敗原因正確**

Run: `cd server && ../.venv/bin/python3 -m unittest test_db -v`
Expected: `ModuleNotFoundError: No module named 'db'`(因為 `db.py` 還不存在)

- [ ] **Step 3: 寫最小實作(記憶體 fallback 部分)**

建立 `server/db.py`:

```python
# 用途：site_stats 表的 Postgres 連線跟遞增邏輯。沒有 DATABASE_URL 環境變數
# 時(本機開發、跑測試套件)自動退化成進程內的記憶體計數器，呼叫端不需要
# 知道現在是哪一種模式。見
# docs/superpowers/specs/2026-09-15-visit-counter-design.md。
# 可手動調整的變數：無。
"""Visit-counter persistence: Postgres when DATABASE_URL is set, an
in-memory counter otherwise (local dev / tests).
"""
import os

_memory_visit_count = 0


def _get_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return None
    import psycopg
    return psycopg.connect(database_url)


def init_db():
    """Idempotently ensure the site_stats table and its single row exist.
    No-op when DATABASE_URL isn't set. Call once at process startup.
    """
    conn = _get_connection()
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS site_stats (
                    id INTEGER PRIMARY KEY,
                    visit_count BIGINT NOT NULL DEFAULT 0
                )
                """
            )
            cur.execute(
                "INSERT INTO site_stats (id, visit_count) VALUES (1, 0) ON CONFLICT (id) DO NOTHING"
            )
        conn.commit()
    finally:
        conn.close()


def increment_visit_count():
    """Increment the visit counter by 1 and return the new value.

    Uses Postgres (DATABASE_URL) when available; otherwise increments an
    in-memory counter local to this process -- the path local dev and the
    test suite actually exercise (2026-09-15 design doc).
    """
    global _memory_visit_count
    conn = _get_connection()
    if conn is None:
        _memory_visit_count += 1
        return _memory_visit_count

    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE site_stats SET visit_count = visit_count + 1 WHERE id = 1 RETURNING visit_count"
            )
            new_count = cur.fetchone()[0]
        conn.commit()
        return new_count
    finally:
        conn.close()
```

注意：`import psycopg` 刻意寫在 `_get_connection()` 函數內部(不是檔案最上面)——這樣本機開發/測試(不設定 `DATABASE_URL`,永遠不會執行到這一行)就算還沒安裝 `psycopg` 也不會噴 `ImportError`。`psycopg` 依賴的安裝在 Task 3 處理。

Postgres 分支(`_get_connection()` 回傳真連線之後的邏輯)在這個階段沒有自動化測試覆蓋——這是刻意的,對應規格文件 §8「不寫連到真的 Render Postgres 的整合測試」。Task 3 部署後會有一次手動的線上驗證(見 Task 3 Step 4)。

- [ ] **Step 4: 執行測試,確認全部通過**

Run: `cd server && ../.venv/bin/python3 -m unittest test_db -v`
Expected: `OK`(3 個測試全過)

- [ ] **Step 5: Commit**

```bash
git add server/db.py server/test_db.py
git commit -m "feat: add visit-counter persistence with in-memory fallback"
```

---

### Task 2: `POST /api/site-visit` Flask 路由

**Files:**
- Modify: `server/app.py`
- Test: `server/test_app.py`

**Interfaces:**
- Consumes: Task 1 的 `init_db()`、`increment_visit_count()`(從 `db` 模組匯入)。
- Produces: `POST /api/site-visit` 回傳 `{"visit_count": <int>}`,狀態碼 200。

- [ ] **Step 1: 寫失敗的測試**

在 `server/test_app.py` 裡,`FormDataAndStaticTest` 類別後面(檔案最後,`if __name__ == "__main__":` 之前)新增：

```python
class SiteVisitTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_returns_200_with_visit_count_field(self):
        response = self.client.post("/api/site-visit")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data["visit_count"], int)

    def test_visit_count_increments_across_calls(self):
        first = self.client.post("/api/site-visit").get_json()["visit_count"]
        second = self.client.post("/api/site-visit").get_json()["visit_count"]

        self.assertEqual(second, first + 1)
```

- [ ] **Step 2: 執行測試,確認失敗原因正確**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app.SiteVisitTest -v`
Expected: FAIL,404(路由還不存在,`/api/site-visit` 目前沒有對應的 view function)

- [ ] **Step 3: 實作路由**

在 `server/app.py` 第 67 行(`from flask import ...`)之後、第 69 行(`from engine.archetype import ...`)之前,新增一行 import：

```python
from db import increment_visit_count, init_db  # noqa: E402
```

在第 90 行 `app = Flask(__name__, static_folder=None)` 之後新增一行,呼叫一次初始化(gunicorn 用 `--chdir server app:app` 匯入這個模組時、或本機用 `python3 server/app.py` 執行時都會跑到這一行,只會執行一次)：

```python
init_db()
```

在第 242 行 `return jsonify(results)`(`api_priority_results` 函式的結尾)之後、第 245 行 `@app.route("/", defaults={"path": "index.html"})` 之前,新增路由：

```python
@app.route("/api/site-visit", methods=["POST"])
def api_site_visit():
    return jsonify({"visit_count": increment_visit_count()})
```

同時更新檔案最上方(第 1-44 行)的用途註解,在既有三支 API 的說明之後加一段：

```
#   POST /api/site-visit         每次呼叫讓瀏覽人次計數器 +1,回傳遞增後的
#                             總數,給首頁右上角顯示用(2026-09-15 新增,見
#                             docs/superpowers/specs/2026-09-15-visit-counter-design.md)。
#                             計數邏輯在 db.py,沒有 DATABASE_URL 環境變數
#                             時退化成記憶體計數器(本機開發/測試)。
```

- [ ] **Step 4: 執行測試,確認全部通過**

Run: `cd server && ../.venv/bin/python3 -m unittest test_app -v`
Expected: `OK`(既有 17 個測試 + 新增 2 個,共 19 個全過)

- [ ] **Step 5: Commit**

```bash
git add server/app.py server/test_app.py
git commit -m "feat: add POST /api/site-visit endpoint"
```

---

### Task 3: 部署設定 — Render Postgres + `psycopg` 依賴

**Files:**
- Modify: `render.yaml`
- Modify: `server/requirements.txt`

**Interfaces:**
- Consumes: Task 1 的 `db.py`(執行期讀取 `DATABASE_URL` 環境變數)。
- Produces: 部署到 Render 後,web service 會拿到一個指向真的 Postgres 的 `DATABASE_URL`;`requirements.txt` 讓 build 階段裝好 `psycopg`。

- [ ] **Step 1: 更新 `render.yaml`**

把整份檔案內容改成：

```yaml
# 用途：Render 的 Blueprint 部署設定,讓 Render 自動讀這份檔案建立後端 Web
# Service,不用在網頁介面手動填 build/start command。細節見 server/README.md。
# databases 區塊是瀏覽人次計數器用的 Postgres(2026-09-15 新增,見
# docs/superpowers/specs/2026-09-15-visit-counter-design.md)——免費方案 90
# 天後會過期,到期需要手動續約或升級成付費方案,這是已知、接受的限制。
# 可手動調整的變數：plan(目前是免費方案 free,流量大了要付費升級就改這裡)、
# PYTHON_VERSION(要跟本機開發用的 Python 版本一致,避免行為不一致)。
services:
  - type: web
    name: nba-player-template
    runtime: python
    plan: free
    buildCommand: pip install -r server/requirements.txt
    startCommand: gunicorn --chdir server app:app --bind 0.0.0.0:$PORT
    envVars:
      - key: PYTHON_VERSION
        value: "3.13.0"
      - key: DATABASE_URL
        fromDatabase:
          name: nba-player-template-db
          property: connectionString

databases:
  - name: nba-player-template-db
    plan: free
```

- [ ] **Step 2: 更新 `server/requirements.txt`**

把整份檔案內容改成：

```
Flask==3.1.3
gunicorn==26.2.0
psycopg[binary]==3.2.3
```

- [ ] **Step 3: 本機也裝上這個依賴(方便之後想手動測 Postgres 分支的話可以用)**

Run: `.venv/bin/python3 -m pip install "psycopg[binary]==3.2.3"`
Expected: 安裝成功,無錯誤

- [ ] **Step 4: Commit**

```bash
git add render.yaml server/requirements.txt
git commit -m "chore: provision Render Postgres for the visit counter"
```

- [ ] **Step 5: 推上線後的手動驗證(部署完成才能做,不是這次 commit 前置動作)**

這一步驟只是記錄下來,不是 commit 的一部分——推上 `main` 讓 Render 部署完成、Postgres 服務建立好之後,用瀏覽器打開正式站,確認：(a) 首頁右上角出現瀏覽人次數字,(b) 重新整理頁面數字有往上跳一格,(c) 到 Render 後台確認 `nba-player-template-db` 這個 Postgres 服務狀態是 available。這是唯一驗證 Postgres 分支真的能動的方式,因為本機/CI 都刻意不連真的 Postgres(見 Task 1 說明)。

---

### Task 4: 前端整合 — 顯示在 topnav 右上角

**Files:**
- Modify: `src/ui/index.html`

**Interfaces:**
- Consumes: Task 2 的 `POST /api/site-visit`,回應格式 `{"visit_count": <int>}`。
- Produces: 無(這是最後一個任務,UI 端點)。

- [ ] **Step 1: 新增 CSS**

在 `src/ui/index.html` 裡找到 `.topnav-login` 的 CSS 規則(約在 `.topnav-actions { ... }` 區塊附近),在它前面新增：

```css
  .visit-counter {
    font-size: 0.78rem;
    color: var(--ink-soft);
    font-family: var(--mono);
    white-space: nowrap;
  }
```

- [ ] **Step 2: 新增 HTML**

找到：

```html
    <div class="topnav-actions">
      <button type="button" class="topnav-login">登入</button>
      <button type="button" class="topnav-menu" aria-label="選單">☰</button>
    </div>
```

改成(在 `topnav-login` 按鈕前面插入一個預設隱藏的 span)：

```html
    <div class="topnav-actions">
      <span class="visit-counter" id="visit-counter" style="display:none"></span>
      <button type="button" class="topnav-login">登入</button>
      <button type="button" class="topnav-menu" aria-label="選單">☰</button>
    </div>
```

- [ ] **Step 3: 新增 JS**

在 `<script>` 區塊裡,找到 IIFE 最後面的 `main();` 呼叫(在 `})();` 之前)：

```js
  main();
})();
```

改成(新增一個獨立函式,跟 `main()` 平行呼叫,互不等待)：

```js
  function recordSiteVisit() {
    fetch("/api/site-visit", { method: "POST" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && typeof data.visit_count === "number") {
          const el = document.getElementById("visit-counter");
          el.textContent = `👁 ${data.visit_count.toLocaleString()}`;
          el.style.display = "inline";
        }
      })
      .catch(() => {}); // 裝飾性數字,失敗就不顯示,不打斷任何流程
  }

  main();
  recordSiteVisit();
})();
```

- [ ] **Step 4: 手動驗證(這個專案的前端沒有自動化測試框架,既有慣例是本機啟動 Flask 手動檢查)**

Run:
```bash
cd "/Users/james/Desktop/NBA球員模板"
PYTHONPATH=src:. .venv/bin/python3 server/app.py
```
然後用瀏覽器打開 `http://localhost:5001`,確認：(a) topnav 右上角、登入按鈕左邊出現「👁 1」,(b) 重新整理頁面,數字變成「👁 2」、「👁 3」⋯⋯依序遞增(本機沒有 `DATABASE_URL`,走的是 Task 1 的記憶體 fallback,重啟伺服器後會歸零,這是預期行為)。

驗證完按 Ctrl+C 關掉伺服器。

- [ ] **Step 5: Commit**

```bash
git add src/ui/index.html
git commit -m "feat: show the visit counter in the topnav"
```
