# KOL 網球管理系統 — 任務清單

## 第一階段：資料基礎 + 行事曆增強
- [x] 1. User Model 擴充 (phone/nickname/gender/color/line_display_name/notes) + Migration
- [x] 2. CSV 學生匯入腳本 (26 位學生，密碼=手機)
- [x] 3. 教練帳號建立 (王/宋/張/柯/湯/蔡 + 顏色)
- [x] 4. 教練顏色前端 — calendar.js 根據 color 欄位著色
- [x] 5. 一天/一週視圖切換
- [x] 6. 週次下拉選單

## 第二階段：業務邏輯
- [x] 7. Course Model 擴充 (is_trial/trial_count/trial_fee) + CourseTemplate Model
- [x] 8. 請假流程 (標記請假→灰色置頂+釋出時段)
- [x] 9. 每週課表模板 (CourseTemplate + 一鍵套用至指定週)
- [x] 10. 出席紀錄 (預設 attended / 可改 absent / 請假自動記錄)
- [x] 11. 學生剩餘堂數統計 + 出席日期記錄頁面
- [x] 12. 教練月統計 (每月上課時數與體驗課費用統計)
- [x] 13. 使用者編輯功能 (學生/教練資料彈窗修改)

## 第三階段：登入 + 權限
- [x] 14. 登入系統 (帳密 + JWT Session + 快速身份登入切換)
- [x] 15. 教練個人視圖 (教練登入後自動過濾只看個人課程)
- [x] 16. 權限控管 (教練唯讀不可新增修改，Admin/小編完整管理)
