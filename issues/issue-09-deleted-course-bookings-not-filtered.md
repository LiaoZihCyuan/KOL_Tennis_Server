# Issue 09：課程被刪除後，關聯的預約沒有跟著軟刪除，統計頁查詢也沒有過濾已刪除課程

**嚴重程度：低中**　**分類：資料一致性**　**發現時機：修正 Issue 03 時順帶發現**　**狀態：已修正 (2026-08-17)**

## 修正內容

- `services/user_service.py` 的 `get_student_attendance_stats()` 與 `routes/user_routes.py` 的 `get_user_full_profile()`，兩處查詢學員出席紀錄的地方都補上 `Course.deleted_at.is_(None)` 過濾條件，已刪除的課程不會再被算進「已出席/請假/缺席」清單。
- 更徹底的作法：`services/course_service.py` 原本的 `refund_deducted_bookings_before_delete()` 改名為 `cleanup_bookings_before_delete()`，除了原本的退點邏輯，現在**刪除課程時也會把該課程底下所有預約一併軟刪除**，從根本避免「課程已刪除、但預約還留著」這種資料狀態再度造成類似的查詢遺漏問題（防禦性修法，即使將來有其他地方忘記加 `Course.deleted_at` 過濾條件也不會受影響）。

## 實測驗證（dev 環境真實 API）

1. 幫學員排課並簽到（出席統計 `attended_count` 從 1 變 2）。
2. 刪除該課程 → 出席統計 `attended_count` 正確變回 1，該學員的「完整檔案」出席紀錄筆數也同步減少 1 筆，確認已刪除課程不再出現在任何統計或紀錄畫面。

測試完成後已清除所有測試資料。

## 問題敘述

`Course.soft_delete()`（`models/base.py:95`）只會把 `Course.deleted_at` 設為現在時間，**不會連動把該課程底下的 `Booking` 一併軟刪除**。

但 `UserService.get_student_attendance_stats()`（`services/user_service.py:136`）與 `user_bp` 的 `get_user_full_profile`（`routes/user_routes.py:66`）在查詢學員出席紀錄時，都只過濾 `Booking.deleted_at.is_(None)`，**沒有一併過濾 `Course.deleted_at.is_(None)`**：

```python
# services/user_service.py:145
bookings = db.session.query(Booking).join(Course).filter(
    Booking.user_id == student.id,
    Booking.deleted_at.is_(None)
).order_by(Course.start_time.desc()).all()
```

代表小編如果刪除一堂課（例如排錯課要刪掉重排），這堂課底下的預約紀錄依然會出現在「學員剩餘堂數統計」「學員完整檔案」的出席/請假/缺席清單裡，因為查詢完全沒有意識到這堂課其實已經被刪除了。

## 重現步驟

1. 幫學員排一堂課並簽到（出席紀錄會有一筆 `ATTENDED`）。
2. 用「刪除課程」把這堂課刪掉。
3. 到「學員統計」或該學員的「完整檔案」頁查看出席紀錄 → 這堂已刪除的課仍然列在「已出席」清單中。

## 影響

- 小編透過統計頁核對「這個月學員實際上了幾堂課」時，數字會把已刪除（例如排錯又刪掉重建）的課程也算進去，造成統計失真。

## 建議修復方向

- 兩處查詢都加上 `Course.deleted_at.is_(None)` 的過濾條件；或者讓 `Course.soft_delete()` 連動軟刪除底下所有 `Booking`（更徹底，但要留意目前 `Course.bookings` relationship 設定的是 `cascade="all, delete-orphan"`，這是給 SQLAlchemy 物件刪除用的 cascade，跟軟刪除是兩回事，不會自動處理）。
