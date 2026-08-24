import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, extract

from extensions import db
from models.course import Course, CourseStatus
from models.course_template import CourseTemplate
from models.booking import Booking, BookingStatus
from models.user import User, UserRole

# 全系統的營業時區。課程時間從前端送來時是 UTC（JS 的 toISOString()），存進
# timestamptz 後讀回來也不保證是 +08，所以任何要「取出時鐘上的幾點／星期幾」
# 的地方都必須先轉成這個時區再取，不能直接對原始 datetime 呼叫 .hour /
# .weekday() / .strftime()。台灣沒有日光節約時間，固定 +08 即可。
TAIPEI_TZ = timezone(timedelta(hours=8))


def to_taipei(dt: datetime) -> datetime:
    """把任意 datetime 轉成台北時間。naive（沒有時區）的一律當成 UTC 解讀，
    因為前端一律送 JS toISOString() 的 UTC 字串——直接呼叫 astimezone() 會讓
    Python 拿「容器的系統時區」來補，容器是 UTC 時剛好對、之後改設定就會默默算錯。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TAIPEI_TZ)


class CourseService:
    @staticmethod
    def _upsert_template_from_course(course: Course, student_ids: List[uuid.UUID]) -> Optional[CourseTemplate]:
        """
        Turn a single calendar course into a recurring weekly template so it keeps
        showing up every future week regardless of payment status. Trial lessons are
        one-offs by nature and are never turned into a standing template. Matches on
        day-of-week + start time + location so re-marking the same course "固定" twice
        (or marking a course that a template already auto-generated) doesn't create
        a duplicate template.
        """
        if course.is_trial or not student_ids:
            return None

        # 一定要先轉成台北時間再取星期幾/時分：course.start_time 是前端送來的
        # UTC 時間（例如台北 10:00 會是 02:00Z）。直接取的話模板會存成「02:00」，
        # 而 generate_courses_from_templates 又把模板時間當成台北時間來生課，
        # 於是同一堂課除了原本的 10:00 之外，還會多生出一堂 02:00 的幽靈課
        # ——使用者回報的「建立一堂課卻跑出兩堂、時間還很奇妙」就是這個原因。
        # 晚上 8 點之後 / 早上 8 點之前的課還會連星期幾都算錯一天。
        local_start = to_taipei(course.start_time)
        local_end = to_taipei(course.end_time)
        day_of_week = local_start.weekday()
        start_time_str = local_start.strftime("%H:%M")
        end_time_str = local_end.strftime("%H:%M")

        existing = db.session.query(CourseTemplate).filter(
            CourseTemplate.day_of_week == day_of_week,
            CourseTemplate.start_time == start_time_str,
            CourseTemplate.location == course.location,
            CourseTemplate.deleted_at.is_(None)
        ).first()
        if existing:
            return existing

        tmpl = CourseTemplate(
            coach_id=course.coach_id,
            title=course.title,
            student_ids=[str(sid) for sid in student_ids],
            day_of_week=day_of_week,
            start_time=start_time_str,
            end_time=end_time_str,
            capacity=course.capacity,
            location=course.location,
            description=course.description,
            is_trial=False,
            is_active=True
        )
        tmpl.save()
        return tmpl

    @staticmethod
    def create_course(
        coach_id: Optional[uuid.UUID],
        start_time: datetime,
        end_time: datetime,
        capacity: int,
        location: str,
        description: Optional[str] = None,
        title: Optional[str] = None,
        is_trial: bool = False,
        trial_count: Optional[int] = None,
        trial_fee: Optional[int] = None,
        student_id: Optional[uuid.UUID] = None,
        is_recurring: bool = False
    ) -> Course:
        student = None
        if student_id and not is_trial:
            student = User.get(student_id)
            if not student or student.deleted_at is not None:
                raise ValueError("找不到指定的學生資料")

        course = Course(
            coach_id=coach_id,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            location=location,
            description=description,
            title=title,
            is_trial=is_trial,
            trial_count=trial_count,
            trial_fee=trial_fee,
            status=CourseStatus.SCHEDULED
        )
        course.save()

        if student:
            db.session.flush()  # populate course.id (default is applied at flush, not construction)
            booking = Booking(
                course_id=course.id,
                user_id=student.id,
                status=BookingStatus.CONFIRMED
            )
            db.session.add(booking)

        if is_recurring and student:
            CourseService._upsert_template_from_course(course, [student.id])

        Course.commit()
        return course

    @staticmethod
    def get_courses(start_date: datetime, end_date: datetime, coach_id: Optional[uuid.UUID] = None) -> List[Course]:
        # Automatically generate courses from active templates for every week in range
        try:
            tz = start_date.tzinfo or timezone(timedelta(hours=8))
            cur = start_date.date()
            # If start_date is not Monday, find the Monday before/on start_date
            monday_diff = cur.weekday()
            first_monday = cur - timedelta(days=monday_diff)
            
            check_monday = first_monday
            while check_monday <= end_date.date():
                monday_dt = datetime(check_monday.year, check_monday.month, check_monday.day, 0, 0, 0, tzinfo=tz)
                CourseService.generate_courses_from_templates(monday_dt)
                check_monday += timedelta(days=7)
        except Exception as e:
            logging.error(f"Failed to auto-generate courses from templates: {e}")

        stmt = select(Course).where(
            Course.start_time >= start_date,
            Course.start_time <= end_date,
            Course.deleted_at.is_(None)
        )
        if coach_id:
            stmt = stmt.where(Course.coach_id == coach_id)

        stmt = stmt.order_by(Course.start_time)
        return list(db.session.scalars(stmt))

    @staticmethod
    def reschedule_course(
        course_id: uuid.UUID,
        admin_id: Optional[uuid.UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        location: Optional[str] = None
    ) -> Optional[Course]:
        course = Course.get(course_id)
        if not course or course.deleted_at is not None:
            return None

        if start_time is not None:
            course.start_time = start_time
        if end_time is not None:
            course.end_time = end_time
        if location is not None:
            course.location = location

        Course.commit()
        return course

    @staticmethod
    def checkin_course(course_id: uuid.UUID, admin_id: Optional[uuid.UUID] = None) -> Optional[Course]:
        course = Course.get(course_id)
        if not course or course.deleted_at is not None:
            return None

        course.status = CourseStatus.COMPLETED
        for b in Booking.get_confirmed_for_course(course.id):
            b.status = BookingStatus.ATTENDED

        Course.commit()
        return course

    @staticmethod
    def update_course(
        course_id: uuid.UUID,
        admin_id: Optional[uuid.UUID] = None,
        is_recurring: bool = False,
        **kwargs
    ) -> Optional[Course]:
        course = Course.get(course_id)
        if not course or course.deleted_at is not None:
            return None

        # Convert status string to enum if provided
        new_status = kwargs.get("status")
        if isinstance(new_status, str):
            try:
                new_status = CourseStatus(new_status.lower())
                kwargs["status"] = new_status
            except ValueError:
                new_status = None

        # "已完成" / "學員請假" chosen from the edit form's status dropdown must
        # trigger the same booking-status side effects as the dedicated
        # 簽到出席 / 標記請假 buttons.
        became_completed = new_status == CourseStatus.COMPLETED and course.status != CourseStatus.COMPLETED
        became_cancelled = new_status == CourseStatus.CANCELLED and course.status != CourseStatus.CANCELLED

        for key, value in kwargs.items():
            if hasattr(course, key):
                setattr(course, key, value)

        if became_completed:
            for b in Booking.get_confirmed_for_course(course.id):
                b.status = BookingStatus.ATTENDED
        elif became_cancelled:
            CourseService._release_bookings(course, BookingStatus.LEAVE_APPROVED)

        if is_recurring:
            student_ids = [b.user_id for b in course.bookings if b.deleted_at is None]
            CourseService._upsert_template_from_course(course, student_ids)

        Course.commit()
        return course

    @staticmethod
    def _release_bookings(course: Course, new_booking_status: BookingStatus) -> None:
        bookings = db.session.query(Booking).filter(
            Booking.course_id == course.id,
            Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.LEAVE_REQUESTED, BookingStatus.ATTENDED]),
            Booking.deleted_at.is_(None)
        ).all()
        for booking in bookings:
            booking.status = new_booking_status

    @staticmethod
    def mark_leave(course_id: uuid.UUID, admin_id: Optional[uuid.UUID] = None) -> Optional[Course]:
        """Mark a course as student leave (status=cancelled), update bookings to LEAVE_APPROVED."""
        course = Course.get(course_id)
        if not course or course.deleted_at is not None:
            return None

        course.status = CourseStatus.CANCELLED
        CourseService._release_bookings(course, BookingStatus.LEAVE_APPROVED)

        Course.commit()
        return course

    @staticmethod
    def cancel_course(course_id: uuid.UUID, admin_id: uuid.UUID) -> Optional[Course]:
        course = Course.get(course_id)
        if not course or course.deleted_at is not None:
            return None

        if course.status == CourseStatus.CANCELLED:
            return course

        course.status = CourseStatus.CANCELLED
        CourseService._release_bookings(course, BookingStatus.CANCELLED)

        Course.commit()
        return course

    @staticmethod
    def cleanup_bookings_before_delete(course_id: uuid.UUID, admin_id: Optional[uuid.UUID] = None) -> int:
        """
        Course.soft_delete() only stamps the course itself — it does not cascade
        to its bookings, which otherwise stay "active" forever and keep showing
        up in attendance stats / student profiles for a course that no longer
        exists (see Issue 09). Soft-deletes every booking on the course so it
        stops appearing in attendance/history queries. Returns the number of
        bookings removed.
        """
        course = Course.get(course_id)
        if not course or course.deleted_at is not None:
            return 0

        bookings = db.session.query(Booking).filter(
            Booking.course_id == course_id,
            Booking.deleted_at.is_(None)
        ).all()

        for booking in bookings:
            booking.soft_delete()

        return len(bookings)

    @staticmethod
    def generate_courses_from_templates(monday_date: datetime) -> int:
        """
        Generate courses for the whole week starting from monday_date (Monday 00:00).
        Skips slot if a non-deleted course already exists at that coach/time.
        Returns {"created_count": int, "skipped": [{"student_name": str, "course_title": str, "reason": str}]}
        so callers (see apply_templates_to_week) can tell the admin which students
        didn't get booked instead of it happening invisibly.
        """
        templates = CourseTemplate.get_active_templates()
        created_count = 0
        skipped: List[Dict[str, Any]] = []

        # monday_date should be a Monday
        for tmpl in templates:
            # Calculate actual date
            target_date = monday_date.date() + timedelta(days=tmpl.day_of_week)
            
            # Parse start_time and end_time
            start_parts = [int(p) for p in tmpl.start_time.split(":")]
            end_parts = [int(p) for p in tmpl.end_time.split(":")]
            
            tz = timezone(timedelta(hours=8)) # Asia/Taipei
            start_dt = datetime(target_date.year, target_date.month, target_date.day, start_parts[0], start_parts[1], tzinfo=tz)
            end_dt = datetime(target_date.year, target_date.month, target_date.day, end_parts[0], end_parts[1], tzinfo=tz)

            # Check if course already exists at this location & time
            existing = db.session.query(Course).filter(
                Course.location == tmpl.location,
                Course.start_time == start_dt,
                Course.deleted_at.is_(None)
            ).first()

            if not existing:
                course = Course(
                    coach_id=tmpl.coach_id,
                    title=tmpl.title,
                    start_time=start_dt,
                    end_time=end_dt,
                    capacity=tmpl.capacity,
                    location=tmpl.location,
                    description=tmpl.description,
                    is_trial=tmpl.is_trial,
                    trial_count=tmpl.trial_count,
                    trial_fee=tmpl.trial_fee,
                    status=CourseStatus.SCHEDULED
                )
                db.session.add(course)

                if tmpl.student_ids and not tmpl.is_trial:
                    db.session.flush()  # populate course.id
                    for sid in tmpl.student_ids:
                        student = User.get(uuid.UUID(sid))
                        # Fixed-course templates auto-book every listed student
                        # regardless of payment status — only a missing/deleted
                        # student record is skipped, non-fatal so it doesn't
                        # fail the whole week's generation.
                        if not student or student.deleted_at is not None:
                            skipped.append({
                                "student_name": sid,
                                "course_title": course.title or "",
                                "reason": "找不到學生資料"
                            })
                            continue
                        db.session.add(Booking(
                            course_id=course.id,
                            user_id=student.id,
                            status=BookingStatus.CONFIRMED
                        ))

                created_count += 1

        db.session.commit()
        return {"created_count": created_count, "skipped": skipped}

    @staticmethod
    def get_coach_monthly_stats(year: int, month: int, coach_id: Optional[uuid.UUID] = None) -> List[Dict[str, Any]]:
        """
        Calculate total teaching hours and course counts per coach in the specified month.
        Pass coach_id to restrict this to a single coach (see Issue 11 — a coach calling
        this should only ever see their own hours/trial revenue, not every coach's).
        """
        coaches = [c for c in User.get_users_by_role(UserRole.COACH) if c.id == coach_id] if coach_id else User.get_users_by_role(UserRole.COACH)
        stats = []

        # Define month range in UTC+8
        start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        if month == 12:
            end_dt = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        else:
            end_dt = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=8)))

        for coach in coaches:
            courses = db.session.query(Course).filter(
                Course.coach_id == coach.id,
                Course.start_time >= start_dt,
                Course.start_time < end_dt,
                Course.status != CourseStatus.CANCELLED,
                Course.deleted_at.is_(None)
            ).all()

            total_minutes = 0
            trial_count = 0
            trial_revenue = 0

            for c in courses:
                diff = (c.end_time - c.start_time).total_seconds() / 60
                total_minutes += max(0, diff)
                if c.is_trial:
                    trial_count += (c.trial_count or 1)
                    trial_revenue += (c.trial_fee or 0)

            stats.append({
                "coach_id": str(coach.id),
                "coach_name": coach.display_name,
                "color": coach.color or "#3b82f6",
                "course_count": len(courses),
                "total_hours": round(total_minutes / 60, 1),
                "trial_count": trial_count,
                "trial_revenue": trial_revenue
            })

        return stats
