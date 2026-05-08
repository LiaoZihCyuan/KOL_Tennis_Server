import uuid
from datetime import datetime
from typing import List, Optional

from models.course import Course, CourseStatus
from models.booking import Booking, BookingStatus
from models.credit_transaction import CreditTransaction, TransactionType

class CourseService:
    @staticmethod
    def create_course(
        coach_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        capacity: int,
        location: str,
        credit_cost: int,
        description: Optional[str] = None
    ) -> Course:
        course = Course(
            coach_id=coach_id,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            location=location,
            credit_cost=credit_cost,
            description=description,
            status=CourseStatus.SCHEDULED
        )
        course.save()
        Course.commit()
        return course

    @staticmethod
    def get_courses(start_date: datetime, end_date: datetime) -> List[Course]:
        return Course.get_courses_in_range(start_date, end_date)

    @staticmethod
    def update_course(
        course_id: uuid.UUID,
        **kwargs
    ) -> Optional[Course]:
        course = Course.get(course_id)
        if not course or course.deleted_at is not None:
            return None

        for key, value in kwargs.items():
            if hasattr(course, key):
                setattr(course, key, value)
                
        Course.commit()
        return course

    @staticmethod
    def cancel_course(course_id: uuid.UUID, admin_id: uuid.UUID) -> Optional[Course]:
        course = Course.get(course_id)
        if not course or course.deleted_at is not None:
            return None

        if course.status == CourseStatus.CANCELLED:
            return course # already cancelled

        course.status = CourseStatus.CANCELLED
        
        # Handle bookings and refunds
        bookings = Booking.get_confirmed_for_course(course_id)
        
        for booking in bookings:
            booking.status = BookingStatus.CANCELLED
            
            # Refund transaction
            refund = CreditTransaction(
                user_id=booking.user_id,
                type=TransactionType.REFUND_LEAVE,
                amount=course.credit_cost,
                related_booking_id=booking.id,
                admin_user_id=admin_id,
                description=f"Refund due to course {course_id} cancellation"
            )
            refund.save()
            
            # Add credits back to student
            booking.student.credits += course.credit_cost

        Course.commit()
        return course
