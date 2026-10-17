# KOL Tennis Server

網球課程排課系統。Flask + PostgreSQL（SQLAlchemy 2.0），以 Docker Compose 部署在 AWS EC2。

- 程式碼規範與架構約定見 `AI_RULES.md` 第 2、3 節（Tech Stack、Coding Standards）。
  該檔第 1 節「禁止執行 Shell 指令」是寫給其他不能執行指令的 AI 工具的，**不適用於 Claude Code**。
- 已知問題記錄在 `issues/`。

## 本機開發

- `docker-compose.yml`：開發環境，容器 `postgres_dev` 等
- 單獨執行套件內的腳本要用 `python3 -m package.module`

## Production（AWS EC2）

| 項目 | 值 |
|---|---|
| SSH | `ssh -i koltennis_key.pem ec2-user@ec2-3-239-229-97.compute-1.amazonaws.com` |
| 金鑰 | 專案根目錄 `koltennis_key.pem`（已 gitignore，絕不 commit） |
| 程式碼目錄 | `~/app`（git clone，追 `origin/main`） |
| Compose 檔 | `docker-compose.prod.yml` |
| 容器 | `flask_api_prod`（gunicorn，host :80 → 5000）、`postgres_prod`（postgres:16） |
| DB | user `appuser`、db `appdb` |
| 備份 | EC2 上 `~/backup_db.sh`，cron 每天 20:00 UTC（台灣 04:00），保留 14 份於 `~/backups`，log 在 `~/backup.log` |
| 時區 | 伺服器時鐘是 UTC；網站顯示固定台灣時間 |

一律在指令前加 `cd` 到專案根目錄，或使用金鑰的絕對路徑
`/home/liaozihcyuan/KOL_Tennis_Server/koltennis_key.pem`。

### 可以直接執行（唯讀，不必再問使用者）

使用者已授權 Claude 透過 SSH 在 EC2 上做唯讀檢查，例如：

- 狀態：`hostname; uptime; df -h; free -m; sudo docker ps`
- Log：`sudo docker logs --tail 200 flask_api_prod`（`postgres_prod` 同理）
- 版本：`cd ~/app && git log -1 --oneline && git status --short`，與本機 `origin/main` 比對是否已部署
- 健康檢查：`curl -sS -o /dev/null -w '%{http_code}' http://localhost/`
- 備份：`ls -lh ~/backups; tail ~/backup.log`
- DB 唯讀查詢：`sudo docker exec postgres_prod psql -U appuser -d appdb -c "SELECT ..."`（只限 SELECT）

### ⚠️ Production 資料庫鐵則

Production DB 的資料與本機**不一致**，而且是客戶的真實資料，一旦遺失無法交代。

1. **非必要不動 prod DB。** 能在本機重現、修正的事就在本機做。
2. **要動就一定先備份**，並確認備份檔存在、非空：
   `ssh ... "~/backup_db.sh && ls -lh ~/backups | tail -3"`
3. **Migration 必須對既有資料安全**：新欄位用 nullable 或給 default、不刪有資料的欄位/表、
   資料轉換要可逆。部署前先讀過新的 migration 檔，並比對 prod 的
   `flask db current` 與本機 `flask db heads`，告訴使用者會跑哪些 migration。
4. 不要假設 prod 的資料長得跟本機一樣（例如某些欄位可能是 NULL、有本機沒有的舊資料）。

這些規則有機制保護：
- `.claude/hooks/guard_prod_db.py`（PreToolUse hook）：針對 prod 的破壞性指令
  （`down -v`、刪 volume、DROP、TRUNCATE、刪備份）**一律拒絕**；
  其他寫入類指令（部署、migration、寫入 SQL、重啟、改檔）**強制詢問使用者**。
- `scripts/deploy.sh` 第一步會備份到 `~/backups/predeploy_*.sql.gz`（不會被每日輪替刪掉），
  備份失敗就中止部署。

### 必須先問使用者確認

Production 上是教練輸入的真實資料，以下動作執行前**必須先說明要做什麼並取得同意**：

- 部署：`scripts/deploy.sh`（pull → rebuild → `flask db upgrade` → health check）。部署前先確認變更已 push 到 `origin/main`
- 重啟／停止容器、`docker compose up/down`、rebuild
- 任何寫入 DB 的操作（INSERT/UPDATE/DELETE、migration、手動修資料）。修資料前先跑一次備份
- 修改 EC2 上的檔案、cron、系統套件
- `scripts/pull_prod_data.sh` 會**覆蓋本機 DB**（prod → local）。絕不做反方向（local → prod）

## 常用 workflow

- **部署**：確認 `git status` 乾淨且已 push → 經使用者同意 → `bash scripts/deploy.sh` → 看 log 確認無錯誤
- **查線上問題**：看 `flask_api_prod` log → 比對部署版本 → 必要時唯讀查 DB → 在本機重現與修正
- **用真實資料在本機測試**：經使用者同意 → `bash scripts/pull_prod_data.sh`
