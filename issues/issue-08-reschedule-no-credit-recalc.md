# Issue 08：調課只改時間，不會重算點數，時長改變後點數會跟課程實際時數脫鉤

**嚴重程度：低中**　**分類：點數邏輯**　**狀態：已修正 (2026-08-17)**

## 修正內容

- `services/course_service.py` 新增 `CourseService.reschedule_course()`：調課時若有帶 `start_time`/`end_time` 且沒有明確指定 `credit_cost`，會依新時長重新用 `hours_to_credit_cost()` 算出新的點數，取代原本「調課只改時間、完全不動 `credit_cost`」的行為。
- 新增 `_true_up_credit_cost_change()`：如果這堂課已經有學員簽到扣過點，調課導致點數變動時，會自動對該學員做校正交易（時長變長→補扣差額、變短→退還差額），並記錄交易說明「調課點數校正」，避免調課後帳務跟實際時數兜不起來。
- `routes/course_routes.py` 的調課 API 回應訊息會清楚告知小編「點數已由 X 點調整為 Y 點；若已有學員簽到扣點，已一併校正」，不會悄悄發生。
- **順便發現並修正一個相關的獨立 bug**：行事曆的 `editable: isAdmin` 設定其實預設同時開放「拖曳調課」跟「拖曳邊緣調整時長」，但程式碼只接了 `eventDrop`（搬移）沒有接 `eventResize`（調整時長）的 callback。也就是說小編如果用滑鼠拖曳課程方塊的邊緣調整時長，畫面上看起來調整成功，但其實完全沒有送到後端儲存，切換週次或重新整理頁面後會整個復原，小編不會有任何提示。已補上 `eventResize` callback，讓拖曳調整時長比照拖曳調課一樣呼叫 `/reschedule` API 並正確連動點數重算。

## 實測驗證（dev 環境真實 API）

1. 建課（1 小時，1 點）→ 簽到扣點（5→4）→ 調課延長為 2 小時 → 點數自動變成 2，且該學員已扣的點被補扣 1 點（4→3），回應訊息清楚說明。
2. 再把時間調回 1 小時 → 點數變回 1，該學員退還 1 點（3→4）。
3. 只搬移時段、不改變時長（模擬拖曳調課）→ 點數維持不變，回應只有「調課成功！」，不會誤跳出點數異動的提示。

測試完成後已清除所有測試資料。

## 問題敘述

調課 API 只更新 `start_time` / `end_time` / `location`，完全沒有重新計算 `credit_cost`：

```python
# routes/course_routes.py:216 reschedule_course
if "start_time" in data:
    course.start_time = datetime.fromisoformat(data["start_time"])
if "end_time" in data:
    course.end_time = datetime.fromisoformat(data["end_time"])
if "location" in data:
    course.location = data["location"]

Course.commit()
```

如果小編把一堂原本 1 小時（`credit_cost = 1`）的課，調課延長成 2 小時，`credit_cost` 仍然維持原本的 1，之後簽到只會扣 1 點，跟「點數＝時數」的原則（本應扣 2 點）不一致；反之把課縮短，也一樣不會少扣。

## 重現步驟

1. 建立一堂 18:00–19:00（1 小時）的課，`credit_cost` 自動算為 1。
2. 用調課功能把時間改成 18:00–20:00（2 小時）。
3. 檢查該課程的 `credit_cost` → 仍是 1，沒有跟著時長變成 2。
4. 對這堂課簽到 → 只扣 1 點，但實際上課是 2 小時。

## 影響

- 只要調課有改變時長，點數就會跟課程實際時數脫鉤，長期下來會有一批課程的 `credit_cost` 是「錯的」（沿用調課前的舊時長換算），影響帳務正確性，也讓 Issue 06 提到的「點數＝時數」認知更難對齊。

## 建議修復方向

- 調課時若 `start_time` / `end_time` 有變動，且小編沒有手動指定新的 `credit_cost`，就依照新的時長重新呼叫 `CourseService.hours_to_credit_cost` 計算並更新 `credit_cost`。
- 若課程已經簽到扣過點，調課應提示小編「時長已變更，點數是否需要一併調整」，避免事後帳務對不齊。
