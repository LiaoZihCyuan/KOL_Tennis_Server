# Issue 14：編輯使用者時 LINE ID 空白會存成空字串，第二位之後儲存就 500 錯誤

**嚴重程度：高（production 已觸發條件）**　**分類：使用者管理 / 資料正確性**　**發現時機：verifier 驗證教練顏色時（2026-10-17）**　**狀態：待處理**

## 問題敘述

使用者列表的編輯彈窗（`templates/user_list.html:299`）不論有沒有填，一律送出 `line_id: document.getElementById('editLineId').value`，空白時就是 `""`。
後端 `UserService.update_user()`（`services/user_service.py:161`）直接 `user.line_id = data["line_id"]`，把空字串原樣寫進 DB。

`users.line_id` 有唯一限制（`users_line_id_key`）。`NULL` 可以重複，但空字串 `''` 只能有一筆：
第一位被存成 `''` 之後，再儲存任何一位 LINE ID 空白的使用者都會違反唯一限制，API 回 HTTP 500。

## Production 現況（2026-10-17 唯讀查詢）

- 有效使用者 198 位，其中 `line_id = ''` 已有 **1 位**、`line_id IS NULL` 有 171 位。
- 代表目前在 production 編輯這 171 位裡任何一位並按儲存，都會失敗（500）。

## 重現步驟

1. 小編在使用者列表編輯 A（LINE ID 欄空白）→ 儲存成功，A 的 `line_id` 變成 `''`。
2. 編輯 B（LINE ID 也空白）→ 儲存 → HTTP 500（`users_line_id_key` 唯一限制違反）。

## 修正方向（待與使用者確認）

- 後端：`line_id`（以及其他有唯一限制的選填欄位，如 `email`、`username`）收到空字串一律轉成 `NULL`。
- 資料：把 production 現有的 `line_id = ''` 改回 `NULL`（寫入 prod DB，需先備份並取得使用者同意）。
- 相關：可能還有其他欄位/入口有同樣問題，修正時一併盤點。
