# Issue 11：「教練時數統計」頁面讓每個教練都能看到所有教練的時數與體驗課收入

**嚴重程度：中（隱私 / 職場敏感度）**　**分類：權限範圍**　**發現時機：以教練角度評估系統時發現**　**狀態：已修正 (2026-08-17)**

## 修正內容

- `services/course_service.py` 的 `get_coach_monthly_stats()` 新增可選參數 `coach_id`：有帶就只計算該教練一人的統計，不帶（管理員情境）維持原本回傳所有教練。
- `routes/course_routes.py` 的 `get_coaches_stats`：依據 `g.current_user.role`，教練呼叫時自動帶入自己的 `id` 作為過濾條件，管理員呼叫時不過濾（維持看全部教練）。權限判斷完全在後端做，不是只藏前端。
- `templates/coach_stats.html`：教練登入看到這頁時，畫面文字同步調整——隱藏「教練總人數」卡片、標題從「各教練授課明細」改成「我的授課明細」，避免教練看到只有自己一行、卻還寫著「總人數」的違和畫面。

## 實測驗證（dev 環境真實 API）

1. 用「王教練」帳號打 `/api/coaches/stats` → 只回傳王教練自己一筆資料。
2. 用「小編」（admin）帳號打同一支 API → 仍回傳全部 6 位教練的資料，管理員視角不受影響。
3. 確認 `/coaches/stats` 頁面的文字調整 hook（`cardTotalCoaches`／`statsTableTitle`）有正確渲染在頁面上。

## 問題敘述

`templates/base.html` 的導覽選單中，「教練時數統計」(`/coaches/stats`) 這個連結**沒有**標記 `admin-only`（跟同一區塊的「審核中心」「學生堂數與出席」不同），也就是教練登入後也看得到、點得進去這個頁面。

對應的後端 API：

```python
# routes/course_routes.py
@course_bp.route("/api/coaches/stats", methods=["GET"])
@roles_required("admin", "coach")   # <- 教練本來就有權限呼叫
def get_coaches_stats():
    ...
    stats = CourseService.get_coach_monthly_stats(year, month)
    return jsonify(stats), 200
```

而 `CourseService.get_coach_monthly_stats()` 內部固定 `User.get_users_by_role(UserRole.COACH)` 撈出**全部教練**、逐一計算時數與體驗課收入，完全沒有依照呼叫者的身分過濾成「只看自己」。

實測（用「王教練」帳號登入後打 `/api/coaches/stats`）：回傳內容包含全部 6 位教練的姓名、當月課程堂數、總時數、體驗課收費金額——王教練可以直接看到宋教練、蔡教練等人的堂數與體驗課收入。

## 影響

如果這個頁面是教練用來對帳「自己這個月上了多少課、賺了多少體驗課費」的地方，目前的設計會讓每位教練同時看到**所有同事**的數字。這類時數／收入資訊通常帶有職場敏感性（可能牽涉待遇比較、業績壓力），除非場館明確希望教練之間互相透明，否則多數教練應該不會樂見這件事，也可能造成教練對系統的不信任感（「我的時數大家都看得到」）。

## 建議修復方向

- 教練登入時，`/api/coaches/stats` 應該只回傳該教練自己的統計（依 `g.current_user.id` 過濾），管理員才看得到全部教練的總覽。
- 或者至少跟場館確認這是不是刻意設計的「公開透明」機制——如果是，維持現狀即可，但建議把這個決策記錄下來，避免日後被誤認為是漏洞。
