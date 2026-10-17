# KOL Tennis Server

網球課程排課系統。Flask + PostgreSQL（SQLAlchemy 2.0），以 Docker Compose 部署在 AWS EC2。

- 程式碼規範與架構約定見 `AI_RULES.md` 第 2、3 節（Tech Stack、Coding Standards）。
  該檔第 1 節「禁止執行 Shell 指令」是寫給其他不能執行指令的 AI 工具的，**不適用於 Claude Code**。
- 已知問題記錄在 `issues/`。

## 修改前先確認（drill me）

改任何**程式碼或設定**之前，必須先照 `/drill-me` skill（`.claude/skills/drill-me/SKILL.md`）
跟使用者確認清楚：一次問一題、附建議答案、能查的自己查，最後總結計畫並取得「可以」才動手。
- 不要憑空想像需求：使用者沒要求的功能、重構、「順便」的修改都不做，想到了就提出來問。
- 實作中要偏離已確認的計畫時，停下來重新確認。
- `CLAUDE.md`、`.claude/lessons-learned.md`、`e2e_artifacts/` 測試腳本可以直接更新，不必先問。

## 交付前驗證（每次改動都必須做）

沒有通過獨立驗證的改動，**不可以**說「完成」或交付給使用者。

1. **功能測試**：自己先測（API 用 `curl` 打 `localhost:5000`、跑相關 Python），修到過為止。
2. **獨立驗證**：用 Agent tool 開 `verifier` agent（`.claude/agents/verifier.md`）。
   給它：使用者的原始需求、驗收條件、改了哪些地方。**不要**給「我覺得已經好了」之類的結論，
   也不要替它決定測什麼。它會自己讀 diff、用 Playwright 在本機實際操作網站、看截圖、記錄結果。
3. **結果**：
   - PASS → 交付，回報時附上 verifier 跑了哪些檢查與截圖路徑。
   - FAIL → 修正後開一個**新的** verifier 重驗，不可沿用舊結論。
   - BLOCKED（環境問題，例如瀏覽器無法啟動）→ 照實告訴使用者沒驗證到，不可宣稱完成。
4. **不准自己騙自己**：Claude（實作者）絕不執行 `verdict.py record`，那只屬於 verifier。
   PASS 之前不要 commit app 程式碼。

機制：
- `scripts/e2e/harness.py`：Playwright 工具（登入、截圖、自動抓 console error / 5xx），只連 localhost。
- `scripts/e2e/smoke.py`：所有頁面 × 所有角色 × 桌機/手機的基本檢查。
- 測試帳號 `e2e_admin` / `e2e_coach` / `e2e_student`（密碼 `e2e-pass-123`），只存在本機 DB，
  由 `harness.ensure_users()` 建立；guard hook 禁止對 prod 執行任何 e2e 工具。
- `.claude/hooks/require_verification.py`（Stop hook）：有未驗證的 app 改動時，阻止結束回合一次並提醒。
  改動指紋由 `scripts/e2e/verdict.py` 計算，PASS 之後只要再改任何 app 檔案就會失效。

## Lessons Learned

對話中只要踩到坑，就要記錄到 `.claude/lessons-learned.md`（最上面新增一條），
包括：指令失敗後才找到正確做法、被權限擋下、對環境或資料的錯誤假設、使用者糾正的做法。
不用等使用者要求，修正問題後當下就寫，並在回覆中用一句話告知。
同類的坑已有條目就更新它，不要重複新增；環境改變後已不成立的條目要刪除。

@.claude/lessons-learned.md

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

### AI 工具不進 production

Production 只跑網站本身，AI workflow（`CLAUDE.md`、`.claude/`、`scripts/e2e/`、`e2e_artifacts/`、
文件、Playwright）都不屬於 production，不要安裝或執行在 EC2 上。
- `.dockerignore` 把這些排除在 image 之外。新增任何 AI／開發用的檔案或目錄時，同步加進 `.dockerignore`。
- 不在 EC2 上安裝 Playwright、Node、測試套件，也不在 production 上跑驗證；驗證只在本機做。

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
