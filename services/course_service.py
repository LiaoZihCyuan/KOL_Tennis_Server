import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, extract

from extensions import db
from models.course import Course, CourseStatus
from models.course_template import CourseTemplate
from models.booking import Booking, BookingStatus
from models.credit_transaction import CreditTransaction, TransactionType
from models.user import User, UserRole


class CourseService:
    @staticmethod
    def hours_to_credit_cost(duration_minutes: float) -> int:
        """1 credit == 1 hour of lesson, rounded to the nearest whole credit
        (credit_cost is stored as an Integer column, so e.g. a 1.5hr class rounds to 2)."""
        return max(1, round(duration_minutes / 60))

    @staticmethod
    def create_course(
        coach_id: Optional[uuid.UUID],
        start_time: datetime,
        end_time: datetime,
        capacity: int,
        location: str,
        credit_cost: int,
        description: Optional[str] = None,
        title: Optional[str] = None,
        is_trial: bool = False,
        trial_count: Optional[int] = None,
        trial_fee: Optional[int] = None,
        student_id: Optional[uuid.UUID] = None
    ) -> Course:
        # Credits must be checked at booking time, not left to be discovered
        # (or silently skipped) at checkin — a student should never be able
        # to end up booked into a class they can't actually pay for.
        student = None
        if student_id and not is_trial:
            student = User.get(student_id)
            if not student or student.deleted_at is not None:
                raise ValueError("找不到指定的學生資料")
            if student.credits < credit_cost:
                raise ValueError(
                    f"{student.display_name} 點數不足（剩餘 {student.credits} 點，本堂課需要 {credit_cost} 點），"
                    f"請先為學員儲值後再排課"
                )

        course = Course(
            coach_id=coach_id,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            location=location,
            credit_cost=credit_cost,
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

    # ------------------------------------------------------------------
    # Credit helpers
    #
    # Credits are only ever taken from a student at checkin time (see
    # _deduct_for_checkin). Leave / cancel / delete must therefore only
    # refund a booking's credit_cost when that specific booking actually
    # has a matching DEDUCTION transaction on record — otherwise "refunding"
    # a class that was never paid for just hands the student free points.
    # ------------------------------------------------------------------
    @staticmethod
    def _was_credit_deducted(booking_id: uuid.UUID) -> bool:
        return db.session.query(CreditTransaction).filter(
            CreditTransaction.related_booking_id == booking_id,
            CreditTransaction.type == TransactionType.DEDUCTION,
            CreditTransaction.deleted_at.is_(None)
        ).first() is not None

    @staticmethod
    def _deduct_student(student: User, course: Course, admin_id: Optional[uuid.UUID], booking_id: Optional[uuid.UUID]) -> None:
        # Booking is gated on sufficient credits (create_course /
        # generate_courses_from_templates), so this should never run short —
        # but if it somehow does (credits adjusted after booking, etc.), we
        # still deduct honestly and let the balance go negative rather than
        # silently skipping the deduction, which used to hide the shortfall
        # from admins entirely.
        if student.credits < course.credit_cost:
            logging.warning(
                f"學生 {student.display_name} ({student.id}) 簽到扣點後點數將為負數："
                f"目前 {student.credits} 點，本堂課需要 {course.credit_cost} 點"
            )
        student.credits -= course.credit_cost
        student.lesson_count = max(0, student.lesson_count - 1)
        tx = CreditTransaction(
            user_id=student.id,
            type=TransactionType.DEDUCTION,
            amount=-course.credit_cost,
            related_booking_id=booking_id,
            admin_user_id=admin_id,
            description=f"上課簽到扣點：{course.title or ''}"
        )
        tx.save()

    @staticmethod
    def _deduct_for_checkin(course: Course, admin_id: Optional[uuid.UUID] = None) -> None:
        bookings = Booking.get_confirmed_for_course(course.id)
        for b in bookings:
            b.status = BookingStatus.ATTENDED
            if b.student:
                CourseService._deduct_student(b.student, course, admin_id, b.id)

        if not bookings and course.title:
            student = db.session.query(User).filter(
                User.display_name == course.title.strip(),
                User.role == UserRole.STUDENT,
                User.deleted_at.is_(None)
            ).first()
            if student:
                CourseService._deduct_student(student, course, admin_id, None)

    @staticmethod
    def _refund_and_release(
        course: Course,
        new_booking_status: BookingStatus,
        admin_id: Optional[uuid.UUID] = None,
        description: str = ""
    ) -> None:
        bookings = db.session.query(Booking).filter(
            Booking.course_id == course.id,
            Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.LEAVE_REQUESTED, BookingStatus.ATTENDED]),
            Booking.deleted_at.is_(None)
        ).all()
        for booking in bookings:
            was_deducted = CourseService._was_credit_deducted(booking.id)
            booking.status = new_booking_status
            if was_deducted and course.credit_cost > 0:
                refund = CreditTransaction(
                    user_id=booking.user_id,
                    type=TransactionType.REFUND_LEAVE,
                    amount=course.credit_cost,
                    related_booking_id=booking.id,
                    admin_user_id=admin_id,
                    description=description or f"退點：課程 {course.title or ''}"
                )
                refund.save()
                booking.student.credits += course.credit_cost
                booking.student.lesson_count += 1

    @staticmethod
    def _true_up_credit_cost_change(course: Course, old_credit_cost: int, admin_id: Optional[uuid.UUID] = None) -> None:
        """
        A reschedule that changes a course's duration changes its credit_cost too
        (see reschedule_course). If a booking on this course was already deducted
        at checkin under the *old* credit_cost, that student's balance needs a
        correcting transaction — otherwise the points=hours invariant breaks the
        moment a course is rescheduled after checkin.
        """
        diff = course.credit_cost - old_credit_cost
        if diff == 0:
            return

        bookings = db.session.query(Booking).filter(
            Booking.course_id == course.id,
            Booking.status == BookingStatus.ATTENDED,
            Booking.deleted_at.is_(None)
        ).all()
        for booking in bookings:
            if not booking.student or not CourseService._was_credit_deducted(booking.id):
                continue
            booking.student.credits -= diff
            tx = CreditTransaction(
                user_id=booking.user_id,
                type=TransactionType.DEDUCTION if diff > 0 else TransactionType.REFUND_LEAVE,
                amount=-diff,
                related_booking_id=booking.id,
                admin_user_id=admin_id,
                description=f"調課點數校正：課程時長變更，{'補扣' if diff > 0 else '退還'} {abs(diff)} 點"
            )
            tx.save()

    @staticmethod
    def reschedule_course(
        course_id: uuid.UUID,
        admin_id: Optional[uuid.UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        location: Optional[str] = None,
        credit_cost: Optional[int] = None
    ) -> Optional[Course]:
        course = Course.get(course_id)
        if not course or course.deleted_at is not None:
            return None

        old_credit_cost = course.credit_cost
        duration_changed = start_time is not None or end_time is not None

        if start_time is not None:
            course.start_time = start_time
        if end_time is not None:
            course.end_time = end_time
        if location is not None:
            course.location = location

        if credit_cost is not None:
            course.credit_cost = credit_cost
        elif duration_changed:
            # Time changed and the caller didn't explicitly override credit_cost:
            # keep it honest to the (possibly new) duration rather than silently
            # carrying over a cost computed for the old time slot.
            duration_minutes = (course.end_time - course.start_time).total_seconds() / 60
            course.credit_cost = CourseService.hours_to_credit_cost(duration_minutes)

        CourseService._true_up_credit_cost_change(course, old_credit_cost, admin_id)

        Course.commit()
        return course

    @staticmethod
    def checkin_course(course_id: uuid.UUID, admin_id: Optional[uuid.UUID] = None) -> Optional[Course]:
        course = Course.get(course_id)
        if not course or course.deleted_at is not None:
            return None

        course.status = CourseStatus.COMPLETED
        CourseService._deduct_for_checkin(course, admin_id)

        Course.commit()
        return course

    @staticmethod
    def update_course(
        course_id: uuid.UUID,
        admin_id: Optional[uuid.UUID] = None,
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
        # trigger the same credit deduction / refund side effects as the
        # dedicated 簽到出席 / 標記請假 buttons — otherwise this dropdown is a
        # silent way to change a course's outcome without touching points.
        became_completed = new_status == CourseStatus.COMPLETED and course.status != CourseStatus.COMPLETED
        became_cancelled = new_status == CourseStatus.CANCELLED and course.status != CourseStatus.CANCELLED

        for key, value in kwargs.items():
            if hasattr(course, key):
                setattr(course, key, value)

        if became_completed:
            CourseService._deduct_for_checkin(course, admin_id)
        elif became_cancelled:
            CourseService._refund_and_release(
                course, BookingStatus.LEAVE_APPROVED, admin_id,
                description=f"請假退點：課程 {course.title or ''}"
            )

        Course.commit()
        return course

    @staticmethod
    def mark_leave(course_id: uuid.UUID, admin_id: Optional[uuid.UUID] = None) -> Optional[Course]:
        """
        Mark a course as student leave (status=cancelled), update bookings to LEAVE_APPROVED.
        Only refunds credits for bookings that had actually been deducted (i.e. already
        checked in) — a booking that never reached checkin was never charged.
        """
        course = Course.get(course_id)
        if not course or course.deleted_at is not None:
            return None

        course.status = CourseStatus.CANCELLED
        CourseService._refund_and_release(
            course, BookingStatus.LEAVE_APPROVED, admin_id,
            description=f"請假退點：課程 {course.title or ''}"
        )

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
        CourseService._refund_and_release(
            course, BookingStatus.CANCELLED, admin_id,
            description=f"課程取消退點：{course.title or ''}"
        )

        Course.commit()
        return course

    @staticmethod
    def cleanup_bookings_before_delete(course_id: uuid.UUID, admin_id: Optional[uuid.UUID] = None) -> int:
        """
        Course.soft_delete() only stamps the course itself — it does not cascade
        to its bookings, which otherwise stay "active" forever and keep showing
        up in attendance stats / student profiles for a course that no longer
        exists (see Issue 09). This does two things before a course is deleted:
          1. Refund any booking that actually has a DEDUCTION transaction on
             record (previously deleting a checked-in course silently kept the
             deducted credits, see Issue 03).
          2. Soft-delete every booking on the course so it stops appearing in
             attendance/history queries.
        Returns the number of bookings refunded.
        """
        course = Course.get(course_id)
        if not course or course.deleted_at is not None:
            return 0

        bookings = db.session.query(Booking).filter(
            Booking.course_id == course_id,
            Booking.deleted_at.is_(None)
        ).all()

        refunded_count = 0
        for booking in bookings:
            if course.credit_cost > 0 and CourseService._was_credit_deducted(booking.id):
                refund = CreditTransaction(
                    user_id=booking.user_id,
                    type=TransactionType.REFUND_LEAVE,
                    amount=course.credit_cost,
                    related_booking_id=booking.id,
                    admin_user_id=admin_id,
                    description=f"課程刪除退點：{course.title or ''}"
                )
                refund.save()
                if booking.student:
                    booking.student.credits += course.credit_cost
                    booking.student.lesson_count += 1
                refunded_count += 1
            booking.soft_delete()

        return refunded_count

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
                    credit_cost=tmpl.credit_cost,
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
                        # A student's credits must cover the lesson before the
                        # template can auto-book them — same rule as manual
                        # booking (create_course), just non-fatal here since
                        # this runs unattended: skip only that student's slot
                        # instead of failing the whole week's generation.
                        if not student or student.deleted_at is not None:
                            skipped.append({
                                "student_name": sid,
                                "course_title": course.title or "",
                                "reason": "找不到學生資料"
                            })
                            continue
                        if student.credits < tmpl.credit_cost:
                            logging.warning(
                                f"跳過固定課表自動生課的預約：學生 {student.display_name} ({sid}) 點數不足 "
                                f"(模板 {tmpl.id}, 課程 {course.title})"
                            )
                            skipped.append({
                                "student_name": student.display_name,
                                "course_title": course.title or "",
                                "reason": f"點數不足（剩餘 {student.credits} 點，需要 {tmpl.credit_cost} 點）"
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
