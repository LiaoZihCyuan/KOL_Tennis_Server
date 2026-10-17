# Issue 13：教練開行事曆時，前端去抓只有小編能用的學生清單，被 403 拒絕後 console 噴錯

**嚴重程度：低**　**分類：權限範圍 / 前端錯誤處理**　**發現時機：Playwright smoke test（教練角色）**　**狀態：已修正 (2026-10-17)**

## 修正內容

- `static/assets/js/calendar.js`：初始化時只有小編（admin）才呼叫 `fetchStudentsForForm()`。教練不能新增或編輯課程，只需要看自己的課表，用不到學生清單。
- `fetchStudentsForForm()` 收到的資料不是陣列（例如 403 錯誤訊息）時直接跳過，不再丟出 `data.forEach is not a function`。
- 後端權限不變：`GET /api/users/students` 仍為 `@admin_required`。

## 問題敘述

`calendar.js` 在 `DOMContentLoaded` 時不分角色一律呼叫 `fetchStudentsForForm()` → `GET /api/users/students`。該 API 是 `@admin_required`（`routes/user_routes.py`），教練登入時會拿到 403 與 `{"error": ...}`，前端沒有檢查回應就直接 `data.forEach(...)`，在 console 噴出 `TypeError: data.forEach is not a function`。

頁面本身仍可正常顯示，對教練沒有實際功能影響，但會讓教練角色的 smoke test 永遠失敗，掩蓋真正的新錯誤。

## 重現步驟（修正前）

1. 以教練帳號登入，開啟 `/calendar`。
2. 開瀏覽器 console → 看到 `/api/users/students` 403 與 `data.forEach is not a function`。
