# Issue 10：側邊選單在手機上完全沒有收合，會吃掉大半個畫面

**嚴重程度：高（教練實際使用情境）**　**分類：介面 / 響應式設計**　**發現時機：以教練角度評估系統時發現**　**狀態：已修正 (2026-08-17)**

## 修正內容

- `templates/base.html` 的 `<aside id="sidebar">` 改成 `fixed md:static ... -translate-x-full md:translate-x-0`：手機（`<768px`，跟 `calendar.css` 既有的響應式斷點一致）預設用 `fixed` 疊在畫面上、位移到螢幕外（收合狀態），md 以上維持原本 `static` 排版跟內容並排顯示，桌機使用體驗完全不變。
- 頂端導航列新增漢堡選單按鈕（僅手機顯示，`md:hidden`），點擊呼叫 `toggleSidebar(true)` 展開側邊選單；側邊選單頂部也加了一個關閉按鈕。
- 新增 `#sidebar-backdrop` 半透明遮罩（僅手機顯示），選單展開時點擊遮罩可直接關閉，是常見的 mobile drawer 互動模式。
- 因為導覽連結都是一般 `<a href>`（整頁重新載入），不需要額外處理「點擊連結後自動收合」——每次換頁時側邊選單本來就會回到預設收合狀態。

此修正是共用的 `base.html`，所有繼承它的頁面（行事曆、使用者列表、教練統計、續課審核、學員專區等）都一併套用，不用逐頁修改。

## 實測驗證

用真實頁面渲染確認新增的 `id="sidebar"`、`id="sidebar-backdrop"`、`toggleSidebar` 都正確出現在 `/calendar`、`/users`、`/add_user`、`/templates`、`/renewals/manage`、`/student/portal` 等所有頁面的 HTML 中（皆繼承 `base.html`）。手動邏輯確認：手機寬度下預設 `-translate-x-full`（收合），點擊漢堡按鈕才會滑出；md 以上 `md:translate-x-0 md:static` 蓋過手機版 class，桌機排版不受影響。

## 問題敘述

`templates/base.html` 的側邊選單是寫死 `w-72 shrink-0`（固定寬度 18rem／288px），全站找不到任何讓它在小螢幕收合成漢堡選單的邏輯：

```bash
$ grep -n "md:hidden\|sm:hidden\|hamburger\|toggle-sidebar\|@media" templates/base.html
# 完全沒有結果
```

`static/assets/css/calendar.css` 雖然有針對行事曆本身做過響應式調整（`@media (max-width: 1024px)` / `768px`），但那只處理行事曆內部的排版，**側邊選單本身完全沒有響應式行為**。

以一般手機螢幕寬度（iPhone SE 375px、多數 Android 約 360～414px）試算：288px 的側邊選單會佔掉 **69%～80%** 的畫面寬度，只留不到 100px 給實際的課表內容，等於行事曆在手機上幾乎無法閱讀。

## 為什麼這對教練特別重要

小編/管理員通常在電腦前操作，影響較小；但教練最自然的使用情境是**在球場邊、上課空檔用手機**確認下一堂課、學生姓名、體驗課資訊 —— 這正是這個系統目前最弱的一塊。如果教練打開網站要先橫向捲動或瞇眼看被壓縮到剩不到 100px 寬的課表，很可能直接放棄使用，改用 LINE 或口頭確認課表。

## 建議修復方向

- 在小螢幕（例如 `<768px`）將側邊選單預設收合，改用漢堡選單圖示點擊展開／覆蓋在內容上方（overlay），而不是把內容擠到旁邊。
- 行事曆頁面本身已經有日/週切換、快速跳轉等手機可用的控制項，只要側邊選單收合，其餘部分的可用性應該不會太差。
