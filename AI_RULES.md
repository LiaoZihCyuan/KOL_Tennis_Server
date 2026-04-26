# AI Agent System Instructions  
(Project: Tennis Scheduling System)

在回答任何問題或產生任何程式碼之前，**必須遵守以下所有規則**。

---

## ⛔ 1. 最高指導原則 (CRITICAL RULES)

1. **禁止執行任何 Shell / OS 指令**
   - 你**沒有權限**執行任何終端機或系統指令，包括但不限於：
     `run_shell_command`, `ls`, `cd`, `pip install`, `apt`, `docker`, 等。
   - **不得嘗試**透過指令探索專案結構、驗證檔案是否存在，或測試程式碼。
   - 若需要知道檔案內容或結構：
     - 僅能使用 `read_file` 讀取**使用者已明確提供路徑的檔案**
     - 或直接向使用者詢問
   - 若需要執行 Python 程式：
     - 請產生**完整且可執行的程式碼**
     - 明確指示由使用者自行在本地端執行

2. **專案理解原則**
   - 若使用者已提供 `README.md` 或專案檔案內容，請先閱讀並依其內容行事。
   - **不得假設 README 或檔案必然存在**；若資訊不足，必須詢問使用者，而非自行推測。

3. **開發進度記錄原則**
   - 所有重大的功能修改或邏輯變更，都**必須**在此文件的「進行中任務」區塊更新其進度。

---

## 🏗️ 2. 技術堆疊與架構 (Tech Stack)

- **Python**: 3.10+
- **Web Framework**: Flask
- **Database**: PostgreSQL
- **ORM**: Flask-SQLAlchemy  
  - **必須使用 SQLAlchemy 2.0 語法**
  - 僅允許使用 `Mapped[]` 與 `mapped_column()`

### 專案結構約定
- `app.py` / `manage.py`：應用程式入口（Application Factory）
- `extensions.py`：集中定義 `db = SQLAlchemy()` 等擴充套件實例
- `models/`：資料庫模型
- `services/`: 服務層 (Business Logic)
  - 建議依功能模組劃分，例如 `services/user/`, `services/course/`, `services/booking/` 等。
- `scripts/`：獨立執行的工具腳本

### 執行 Python 腳本 (Executing Python Scripts)
- 若要獨立執行位於套件 (package) 內部的 Python 檔案（例如 `simulator.py`），必須使用 `-m` 旗標將其作為模組執行，以確保相對導入 (`from .`) 能正常運作。
- **範例**: 從專案根目錄執行以下指令：
  ```bash
  python3 -m services.some_module.some_script
  ```

---

## 📝 3. 程式碼規範 (Coding Standards)

1. **Base Model 規則**
   - 所有新的 ORM Model **必須繼承** `models.base.BaseModel`
   - Primary Key 一律使用 UUID：
     ```python
     id: Mapped[uuid.UUID]
     ```
   - `BaseModel` 已包含 `deleted_at`（Soft Delete）機制：
     - 一般查詢應避免包含 `deleted_at IS NOT NULL` 的資料
     - 匯入或初始化資料時，不得主動設定 `deleted_at`

2. **Foreign Key 規則**
   - 所有 Foreign Key 欄位：
     - 型態必須明確為 UUID
     - 不得使用 Integer 或隱式型態
   - 範例：
     ```python
     profile_id: Mapped[UUID] = mapped_column(
         UUID(as_uuid=True),
         ForeignKey("profile.id")
     )
     ```

3. **Migration / Alembic**
   - 新增任何 Model 檔案後：
     - **必須**在應用程式入口（app factory 或 manage.py）中 import
     - 否則 Alembic 將無法偵測 schema 變更


4. **資料庫刪除操作規則 (Database Deletion Rule)**
   - 在實作任何包含 `session.delete()` 的腳本之前，**必須**先仔細檢查 SQLAlchemy 的模型定義（`models/*.py`）。
   - 特別注意 `relationship()` 中與刪除行為相關的 `cascade` 選項，例如 `delete` 或 `delete-orphan`。
   - 刪除父物件 (parent object) 可能會觸發關聯子物件 (child objects) 的連鎖刪除，導致非預期的資料遺失。
   - 為避免此類風險，應採取以下策略之一：
     - **策略一 (修改腳本)**：在刪除父物件前，先解除其與子物件的關聯（例如，將子物件的 foreign key 設為 `None`，或將父物件的 collection 清空）。
     - **策略二 (複製取代移動)**：與其「移動」子物件至新的父物件，不如「複製」一份新的子物件並關聯到新的父物件，然後再刪除舊的父物件及其關聯的舊子物件。這樣能確保新資料的完整性。
---

## 🚀 4. 當前任務上下文 (Current Context)

### 專案目標


### 目前狀態
- 資料庫為 PostgreSQL，ORM 為 Flask-SQLAlchemy（2.0）

### 進行中任務
- **總目標**: 
- **目前進度**:

---

**Instruction to AI**  
若你已理解並接受上述所有規則，請直接針對使用者的下一個 Prompt 回應。  
**不要重述、摘要或解釋本 System Instructions。**