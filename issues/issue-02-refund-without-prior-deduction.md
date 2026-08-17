# Issue 02：請假 / 取消課程一律退點，但點數其實是「簽到時才扣」→ 會無中生有多退點數

**嚴重程度：高（帳務正確性）**　**分類：點數邏輯**　**狀態：已修正 (2026-08-17)**

## 修正內容

- `services/course_service.py` 新增 `_was_credit_deducted()`：以該預約是否存在對應的 `DEDUCTION` 交易紀錄，判斷這堂課的點數是否真的被扣過。
- `mark_leave()` 與 `cancel_course()` 改用共用的 `_refund_and_release()`：只有在 `_was_credit_deducted()` 為真時才建立 `REFUND_LEAVE` 交易並加回點數；尚未扣點的預約（`CONFIRMED` / `LEAVE_REQUESTED`）只會釋出時段、更新狀態，不會再無中生有多送點數。
- 一併把 `_refund_and_release()` 的查詢範圍擴大到含 `ATTENDED` 狀態的預約，讓「已簽到扣點後才請假/取消」的情境也能被正確處理（之前這個情境完全沒有路徑會退點）。

## 實測驗證

在 dev 環境用真實 API 呼叫驗證：
1. 建立學員（5 點）→ 建立一堂未來的課（未簽到）→ 直接標記請假 → 點數維持 5（修正前會變成 6）。
2. 建立另一堂課 → 簽到扣點（5→4）→ 刪除該課程（見 Issue 03）→ 自動退還 1 點回到 5，確認退點邏輯在「已扣點」情境下仍正常運作。

測試完成後已清除所有測試資料。

## 問題敘述

系統的點數扣款時機，只有在**課後點名簽到**時才會真的執行：

```python
# routes/course_routes.py:242 checkin_course
bookings = Booking.get_confirmed_for_course(c_id)
for b in bookings:
    b.status = BookingStatus.ATTENDED
    if b.student and b.student.credits >= course.credit_cost:
        b.student.credits -= course.credit_cost
        ...
```

也就是說，一堂課只要還沒「簽到」，學員的點數就完全沒有被扣過（`CourseService.create_course` 建立預約時 `models/course.py` / `services/course_service.py:37-63` 都沒有扣點）。

但「同意請假」與「取消課程」這兩個動作，卻**不論這堂課是否已經扣過點**，一律無條件把 `course.credit_cost` 加回學員帳戶：

```python
# services/course_service.py:117 mark_leave（對應「標記請假」按鈕 / 學員請假審核同意）
for booking in bookings:
    booking.status = BookingStatus.LEAVE_APPROVED
    if course.credit_cost > 0:
        refund = CreditTransaction(type=REFUND_LEAVE, amount=course.credit_cost, ...)
        refund.save()
        booking.student.credits += course.credit_cost   # <- 直接加點，沒有檢查是否曾經扣過
```

```python
# services/course_service.py:150 cancel_course
for booking in bookings:
    booking.status = BookingStatus.CANCELLED
    refund = CreditTransaction(type=REFUND_LEAVE, amount=course.credit_cost, ...)
    refund.save()
    booking.student.credits += course.credit_cost       # <- 同樣直接加點
```

由於絕大多數「請假」與「取消課程」都是發生在**課程還沒上（未來的課、還沒簽到）**的情況，這代表：

> 小編每同意一次請假、或取消一堂還沒上的課，系統就會**憑空多送學員 `credit_cost` 點數**（因為這堂課根本還沒扣過點）。

這正是「點數使用起來很亂」最主要的根源之一：點數餘額會隨著請假/取消次數持續「灌水」，長期下來帳上點數會跟「小編認知中學員實際還能上幾堂課」對不起來。

## 重現步驟（可用資料庫或手動操作驗證）

1. 建立一位學員，初始點數設為 5。
2. 幫他排一堂尚未發生的課（credit_cost 依時長算，例如 1 小時 = 1 點），此時點數仍是 5（未扣點）。
3. 對這堂課按下「標記請假」或「同意請假」。
4. 檢查學員點數 → 變成 6（無中生有多 1 點），而不是維持 5。
5. 重複步驟 2–4 幾次，點數會一直往上累加，永遠不會減少，等於「請假 = 免費送點數」。

## 影響

- 帳務無法對帳：小編如果想用「點數餘額」推算學員還能上幾堂課，數字會失準。
- 學員可能被無意間多送點數（非惡意，但屬系統性 bug，累積久了金額可能不小）。
- 目前無法從點數紀錄輕易分辨「這筆退款是真的退了已扣的點」還是「其實從沒扣過、被多送的點」。

## 建議修復方向

退點邏輯應該只在「這堂課的點數真的已經被扣過」時才退還，例如：

- 用 `Booking.status` 或是否存在對應的 `DEDUCTION` 類型 `CreditTransaction`（`related_booking_id` 對應）來判斷該堂課是否已扣點。
- 若尚未扣點（booking 還是 `CONFIRMED` / `LEAVE_REQUESTED`，且找不到對應的 `DEDUCTION` 交易紀錄），「取消」或「同意請假」時就**不應該加點**，只需要把時段釋出、booking 標記取消即可。
- 若已扣點（`ATTENDED` 之後才被取消／請假回溯），才執行 `REFUND_LEAVE` 退點。

也可以考慮改變設計為「約課當下就扣點、簽到只是確認出席」，這樣點數異動的因果關係會更直覺，但需要同步調整 #03、#04、#05 的相關邏輯。
