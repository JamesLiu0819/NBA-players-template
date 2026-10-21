# 後端(Flask)使用說明

**用途**：說明 `server/app.py`(唯一的後端)怎麼本機開發、怎麼部署到 Render。這份文件本身沒有可手動調整的變數。

## 本機開發

```bash
cd /Users/james/Desktop/NBA球員模板
python3 -m venv .venv          # 第一次才需要
source .venv/bin/activate
pip install -r server/requirements.txt   # 第一次才需要
python3 server/app.py
```

開 <http://localhost:5001>。

**注意：不要用 5000 port**——macOS 的 AirPlay Receiver 預設佔用 5000,連上去會拿到一個看起來像伺服器壞掉、實際上是 macOS 系統服務回應的 `403`。`server/app.py` 已經把預設 port 改成 5001。

## 跑後端測試

```bash
cd server
../.venv/bin/python3 -m unittest test_app -v
```

這組測試需要 Flask,所以跟主要的 `tests/` 套件分開跑,不會互相干擾。主要套件從專案根目錄跑(必須加 `-t .`,否則 `tests/scripts/` 會蓋掉標準庫裡的 `scripts` 套件名,導致 import 失敗):

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -t . -v
```

## 部署到 Render

`render.yaml`(repo 根目錄)是宣告式的部署設定,Render 的 Blueprint 功能可以直接讀它建立服務,不用在網頁介面上手動填欄位：

1. 把這個 repo push 到 GitHub(遠端是 `github.com/JamesLiu0819/NBA-players-template`)。
2. 到 [Render Dashboard](https://dashboard.render.com/) → New → Blueprint → 選這個 GitHub repo。
3. Render 會自動讀到 `render.yaml`,照裡面寫的 build/start command 建立一個 Web Service。
4. 部署完成後會拿到一個 `https://<service-name>.onrender.com` 的網址,任何人都能開。
5. 到該服務的 Environment 頁面,手動填入下面標「手動」的環境變數。

之後每次 push 到 `main`,Render 預設會自動重新部署。

**方案與費用**：網站服務是 Render 的 Starter 方案(每月 7 美元,`render.yaml` 的 `plan: starter`),不會因為閒置而休眠。不用手動續費——Render 按秒計費,每個月初自動從帳號綁定的信用卡扣上個月的費用;卡片過期或扣款失敗才會出問題,到 Render 後台的 Billing 確認。改方案時記得同步改 `render.yaml`,不然 Blueprint 同步可能把後台的設定改回去。

**資料庫**：用的是 Neon 的免費 Postgres,不是 Render 的資料庫(Render 舊的免費 Postgres 已經刪除,`render.yaml` 也不再宣告任何資料庫)。連線字串放在 Render 的環境變數 `DATABASE_URL`。

**環境變數**：

| 變數 | 用途 | 怎麼設定 |
|---|---|---|
| `DATABASE_URL` | Neon 資料庫連線字串 | 手動(`sync: false`) |
| `SECRET_KEY` | 登入 cookie 的簽章 | Render 自動產生 |
| `GOOGLE_CLIENT_ID` | Google 登入 | 手動(`sync: false`) |
| `GOOGLE_CLIENT_SECRET` | Google 登入 | 手動(`sync: false`) |
| `ADMIN_EMAIL` | 誰可以看使用意見 | 手動(`sync: false`) |

`sync: false` 代表 Render 只知道有這個變數,值由後台管理,push 新版本時不會被覆蓋。這些值不要寫進 `render.yaml`,那份檔案會上傳到 GitHub。

## 架構提醒

- `server/app.py` 不重寫任何計算邏輯,直接 import `src/engine` 跟 `scripts/run_player_match.py` 裡已經拆出來的函數。改 engine 的計算規則要去改 `src/engine`,不要在這裡加。
- `data/answers/` 目錄(真實使用者的個人作答存檔)刻意沒有被任何路由公開服務——`server/app.py` 只透過 `/api/form-data` 回傳題庫(渲染問卷用),不會把整個 `data/` 目錄當靜態檔案吐出去。
