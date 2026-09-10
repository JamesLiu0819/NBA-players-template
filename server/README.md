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

這組測試需要 Flask,所以跟主要的 `tests/` 套件(純標準函式庫,`PYTHONPATH=src python3 -m unittest discover ...`)分開跑,不會互相干擾。

## 部署到 Render

`render.yaml`(repo 根目錄)是宣告式的部署設定,Render 的 Blueprint 功能可以直接讀它建立服務,不用在網頁介面上手動填欄位：

1. 把這個 repo push 到 GitHub(目前本機 repo 還沒設定 remote)。
2. 到 [Render Dashboard](https://dashboard.render.com/) → New → Blueprint → 選這個 GitHub repo。
3. Render 會自動讀到 `render.yaml`,照裡面寫的 build/start command 建立一個 Web Service。
4. 部署完成後會拿到一個 `https://<service-name>.onrender.com` 的網址,任何人都能開。

**免費方案的限制**：閒置一段時間後服務會被暫停(sleep),下一個訪客的第一個請求要等服務醒過來,大概 30-60 秒才會有回應,之後就正常。這是 Render 免費方案的已知行為,不是我們的程式碼有問題。

## 架構提醒

- `server/app.py` 不重寫任何計算邏輯,直接 import `src/engine` 跟 `scripts/run_priority.py`、`scripts/run_player_match.py` 裡已經拆出來的函數。改 engine 的計算規則要去改 `src/engine`,不要在這裡加。
- `data/answers/` 目錄(真實使用者的個人作答存檔)刻意沒有被任何路由公開服務——`server/app.py` 只透過 `/api/form-data` 回傳題庫跟技能名稱(渲染問卷用),不會把整個 `data/` 目錄當靜態檔案吐出去。
