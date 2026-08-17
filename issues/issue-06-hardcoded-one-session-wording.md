# Issue 06：介面文字寫死「1 堂」，跟後端「點數＝時數」的實際換算會兜不起來

**嚴重程度：中**　**分類：點數 / 文案一致性**　**狀態：已修正 (2026-08-17)**

## 修正內容（背景：新增了「堂數」這個獨立欄位）

小編確認系統應該同時記錄「點數」（真正的餘額，依課程時數扣款）跟「堂數」（好記的上課次數顯示，簽到固定 -1、退點固定 +1）兩個數字，見 `models/user.py` 新增的 `lesson_count` 欄位。有了這個區分之後，原本寫死的「1 堂」文字其實是**對的**（堂數本來就固定 ±1），問題只出在文字把「堂」跟「點數」黏在一起講、讓人以為兩者是同一件事。已把以下位置的文字都改成明確區分兩者：

- `templates/calendar.html`：「自動扣抵 1 堂（依課程時數扣除對應點數）」
- `static/assets/js/calendar.js` 簽到確認彈窗：同上
- `templates/renewals_manage.html`：請假同意的說明與確認彈窗，改為「退還 1 堂（若已扣點會一併退還對應點數）」
- `templates/student_portal.html`：請假流程說明，改為「退還 1 堂（若該堂課已扣點，會一併退還對應點數）」；交易紀錄清單的金額單位原本誤標「堂」（其實顯示的是 `CreditTransaction.amount`，也就是點數），已改標「點」；頂部「剩餘上課堂數」卡片改讀 `lesson_count`，並新增一行小字顯示實際點數餘額

詳見 Issue 05 的實測記錄（涵蓋約課擋單、簽到/請假扣退點數與堂數同步異動）。

## 問題敘述

後端建立課程時，點數其實已經是照「時數」換算的：

```python
# services/course_service.py:16
@staticmethod
def hours_to_credit_cost(duration_minutes: float) -> int:
    """1 credit == 1 hour of lesson, rounded to the nearest whole credit
    (credit_cost is stored as an Integer column, so e.g. a 1.5hr class rounds to 2)."""
    return max(1, round(duration_minutes / 60))
```

新增課程的前端也確實是照時長算的：

```js
// static/assets/js/calendar.js:560
credit_cost: Math.max(1, Math.round(durationMins / 60)),
```

代表只要課程排到 1.5 小時以上，`credit_cost` 就會是 2（甚至更多），**不是每堂課都固定扣 1 點**。

但介面上有多處文字是**寫死「1 堂」**，沒有跟著實際的 `credit_cost` 顯示，會讓小編或學員誤以為每堂課無論多長一律只扣 / 退 1 點：

- `templates/calendar.html:216`：「完成上課後簽到，**自動扣抵 1 堂點數**」
- `static/assets/js/calendar.js:623`：簽到確認彈窗「…並自動為學員扣抵 **1 堂課**點數。」
- `templates/renewals_manage.html:36,180`：同意請假的說明與確認彈窗都寫「退回 **1 堂課**」
- `templates/student_portal.html:172`：請假流程說明「小編審核同意後，系統將自動退還 **1 堂課**點數」

實際上如果那堂課是 2 小時（`credit_cost = 2`），簽到會扣 2 點、請假核准會退 2 點，跟文字上寫的「1 堂」對不起來。

## 重現步驟

1. 建立一堂 2 小時的課（`credit_cost` 會自動算成 2）。
2. 打開該課程編輯彈窗，會看到「自動扣抵 1 堂點數」的固定文字。
3. 按下簽到，實際扣點是 2 點，但事前的確認彈窗文字仍寫「自動為學員扣抵 1 堂課點數」。

## 影響

- 小編、教練、學員三方看到的文案跟系統實際行為不一致，容易誤解「點數」單位（把「堂」跟「點/小時」混為一談），也是使用者反映「點數使用有點混亂」的直接原因之一。

## 建議修復方向

- 把這些寫死的「1 堂」文字改成動態帶入實際 `credit_cost`（例如「自動扣抵 {{credit_cost}} 點（約 {{duration}} 小時）」）。
- 統一介面用語：明確區分「堂」（一次上課的預約單位）與「點」（依時數換算、可能 >1 的扣款單位），避免兩者混用造成認知落差。
