import uuid
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, g
from services.course_service import CourseService
from models.course import Course, CourseStatus
from models.course_template import CourseTemplate
from models.booking import Booking, BookingStatus
from models.user import User
from extensions import db
from utils.auth import admin_required, login_required, roles_required

course_bp = Blueprint("course_bp", __name__)


@course_bp.route("/api/courses", methods=["GET"])
@login_required
def get_courses():
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    if not start_date_str or not end_date_str:
        return jsonify({"error": "start_date and end_date are required"}), 400

    try:
        start_date = datetime.fromisoformat(start_date_str)
        end_date = datetime.fromisoformat(end_date_str)
    except ValueError:
        return jsonify({"error": "Invalid date format."}), 400

    # Identity/role comes from the verified JWT, never from client-supplied query params
    # (previously user_role/student_id were trusted from the querystring, letting any
    # caller claim admin or read another student's private course data).
    current_user = g.current_user
    user_role = current_user.role.value
    coach_id = None
    student_id = None
    student_name = None

    if user_role == "coach":
        coach_id = current_user.id
    elif user_role == "student":
        student_id = current_user.id
        student_name = current_user.display_name
    elif user_role == "admin":
        coach_id_str = request.args.get("coach_id")
        try:
            coach_id = uuid.UUID(coach_id_str) if coach_id_str else None
        except ValueError:
            return jsonify({"error": "Invalid coach_id format."}), 400

    courses = CourseService.get_courses(start_date, end_date, coach_id=coach_id)
    result = []

    for c in courses:
        # Check bookings for this course
        has_leave_requested = any(b.status == BookingStatus.LEAVE_REQUESTED for b in c.bookings)
        has_leave_approved = (c.status == CourseStatus.CANCELLED) or any(b.status == BookingStatus.LEAVE_APPROVED for b in c.bookings)
        
        leave_status = "none"
        if has_leave_approved:
            leave_status = "approved"
        elif has_leave_requested:
            leave_status = "requested"

        # Check if this course belongs to the requesting student
        is_my_course = False
        my_booking = None
        if student_id:
            for b in c.bookings:
                if b.user_id == student_id:
                    is_my_course = True
                    my_booking = b
                    break
            if not is_my_course and student_name and c.title and student_name in c.title:
                is_my_course = True

        # Privacy protection for students: mask other students' information!
        if user_role == "student" and not is_my_course:
            result.append({
                "course_id": str(c.id),
                "coach_id": str(c.coach_id) if c.coach_id else None,
                "coach_name": c.coach.display_name if c.coach else "教練",
                "coach_color": c.coach.color if c.coach else "#3b82f6",
                "title": f"教練授課中 ({c.coach.display_name if c.coach else ''})",
                "start_time": c.start_time.isoformat(),
                "end_time": c.end_time.isoformat(),
                "capacity": c.capacity,
                "location": c.location,
                "description": "",
                "status": "busy",
                "leave_status": leave_status,
                "is_trial": False,
                "trial_count": None,
                "trial_fee": None,
                "is_other_student": True,
                "students": []
            })
        else:
            result.append({
                "course_id": str(c.id),
                "coach_id": str(c.coach_id) if c.coach_id else None,
                "coach_name": c.coach.display_name if c.coach else "未知",
                "coach_color": c.coach.color if c.coach else None,
                "title": c.title,
                "start_time": c.start_time.isoformat(),
                "end_time": c.end_time.isoformat(),
                "capacity": c.capacity,
                "location": c.location,
                "description": c.description,
                "status": c.status.value,
                "leave_status": leave_status,
                "leave_reason": my_booking.reason if my_booking else None,
                "is_trial": c.is_trial,
                "trial_count": c.trial_count,
                "trial_fee": c.trial_fee,
                "is_other_student": False,
                # 前端要靠這個判斷刪除時是否需要問「只刪這一堂／刪整個固定課程」
                "is_recurring": c.template_id is not None,
                "students": [{"id": str(b.student.id), "name": b.student.display_name, "status": b.status.value} for b in c.bookings if b.student]
            })

    return jsonify(result), 200


@course_bp.route("/api/courses", methods=["POST"])
@admin_required
def create_course_public():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
        
    required_fields = ["start_time", "end_time", "capacity", "location"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    is_trial = bool(data.get("is_trial", False))
    student_id_str = data.get("student_id")

    if not is_trial and not student_id_str:
        return jsonify({"error": "非體驗課必須從既有學生名單中選擇學生"}), 400

    try:
        coach_id_str = data.get("coach_id")
        coach_id = uuid.UUID(coach_id_str) if coach_id_str else None
        student_id = uuid.UUID(student_id_str) if student_id_str else None
        start_time = datetime.fromisoformat(data["start_time"])
        end_time = datetime.fromisoformat(data["end_time"])
        capacity = int(data["capacity"])
        is_recurring = bool(data.get("is_recurring", False))

        course = CourseService.create_course(
            coach_id=coach_id,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            location=data["location"],
            description=data.get("description"),
            title=data.get("title"),
            is_trial=is_trial,
            trial_count=int(data["trial_count"]) if data.get("trial_count") else None,
            trial_fee=int(data["trial_fee"]) if data.get("trial_fee") else None,
            student_id=student_id,
            is_recurring=is_recurring
        )
        message = "Course created successfully"
        if is_recurring and not is_trial:
            message += "，已同步建立固定課表，之後每週會自動排入這位學生"
        return jsonify({
            "message": message,
            "course_id": str(course.id)
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


@course_bp.route("/api/courses/<course_id>", methods=["PUT"])
@admin_required
def update_course_public(course_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
        
    try:
        c_id = uuid.UUID(course_id)
        
        if "start_time" in data and isinstance(data["start_time"], str):
            data["start_time"] = datetime.fromisoformat(data["start_time"])
        if "end_time" in data and isinstance(data["end_time"], str):
            data["end_time"] = datetime.fromisoformat(data["end_time"])
        if "coach_id" in data:
            data["coach_id"] = uuid.UUID(data["coach_id"]) if data["coach_id"] else None
        if "is_trial" in data:
            data["is_trial"] = bool(data["is_trial"])
        if "trial_count" in data and data["trial_count"]:
            data["trial_count"] = int(data["trial_count"])
        if "trial_fee" in data and data["trial_fee"]:
            data["trial_fee"] = int(data["trial_fee"])
        if "is_recurring" in data:
            data["is_recurring"] = bool(data["is_recurring"])

        is_recurring = bool(data.get("is_recurring", False))
        course = CourseService.update_course(c_id, admin_id=g.current_user.id, **data)
        if not course:
            return jsonify({"error": "Course not found"}), 404

        message = "Course updated successfully"
        if is_recurring and not course.is_trial:
            message += "，已同步建立/連動固定課表"
        return jsonify({"message": message}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


@course_bp.route("/api/courses/<course_id>/reschedule", methods=["POST"])
@admin_required
def reschedule_course(course_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    try:
        c_id = uuid.UUID(course_id)

        course = CourseService.reschedule_course(
            c_id,
            admin_id=g.current_user.id,
            start_time=datetime.fromisoformat(data["start_time"]) if "start_time" in data else None,
            end_time=datetime.fromisoformat(data["end_time"]) if "end_time" in data else None,
            location=data.get("location")
        )
        if not course:
            return jsonify({"error": "Course not found"}), 404

        return jsonify({"message": "調課成功！"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@course_bp.route("/api/courses/<course_id>/checkin", methods=["POST"])
@admin_required
def checkin_course(course_id):
    try:
        c_id = uuid.UUID(course_id)
        course = CourseService.checkin_course(c_id, admin_id=g.current_user.id)
        if not course:
            return jsonify({"error": "Course not found"}), 404

        return jsonify({"message": "簽到點名成功！課程已標記為已完成。"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ============================================================
# 請假完整工作流：申請、撤回、審核同意、拒絕
# ============================================================

@course_bp.route("/api/courses/<course_id>/request-leave", methods=["POST"])
@login_required
def request_course_leave(course_id):
    """Student submits a leave request."""
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "臨時有事請假")
    current_user = g.current_user

    try:
        c_id = uuid.UUID(course_id)
        course = Course.get(c_id)
        if not course or course.deleted_at is not None:
            return jsonify({"error": "課程不存在"}), 404

        if current_user.role.value == "student":
            # students may only request leave for themselves, never on behalf of others
            user_id = current_user.id
        else:
            user_id_str = data.get("user_id")
            user_id = uuid.UUID(user_id_str) if user_id_str else None
            # If user_id not provided, try matching course.title with student
            if not user_id and course.title:
                student = db.session.query(User).filter(User.display_name == course.title.strip()).first()
                if student:
                    user_id = student.id

        if not user_id:
            return jsonify({"error": "請提供學員 ID"}), 400

        # Find existing booking or create one
        booking = db.session.query(Booking).filter(
            Booking.course_id == c_id,
            Booking.user_id == user_id,
            Booking.deleted_at.is_(None)
        ).first()

        if not booking:
            booking = Booking(
                course_id=c_id,
                user_id=user_id,
                status=BookingStatus.LEAVE_REQUESTED,
                reason=reason
            )
            db.session.add(booking)
        else:
            booking.status = BookingStatus.LEAVE_REQUESTED
            booking.reason = reason

        db.session.commit()
        return jsonify({"message": "請假申請已送出！待小編或蔡教練確認同意後將釋出時段並退還堂數點數。"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@course_bp.route("/api/courses/<course_id>/withdraw-leave", methods=["POST"])
@login_required
def withdraw_course_leave(course_id):
    """Student withdraws their pending leave request before approval."""
    data = request.get_json(silent=True) or {}
    current_user = g.current_user

    try:
        if current_user.role.value == "student":
            # students may only withdraw their own leave request
            user_id = current_user.id
        else:
            user_id_str = data.get("user_id")
            if not user_id_str:
                return jsonify({"error": "請提供學員 ID"}), 400
            user_id = uuid.UUID(user_id_str)

        c_id = uuid.UUID(course_id)

        stmt = db.select(Booking).where(
            Booking.course_id == c_id,
            Booking.status == BookingStatus.LEAVE_REQUESTED,
            Booking.deleted_at.is_(None),
            Booking.user_id == user_id
        )

        booking = db.session.scalar(stmt)
        if not booking:
            return jsonify({"error": "找不到待審核的請假申請"}), 404

        booking.status = BookingStatus.CONFIRMED
        booking.reason = None
        db.session.commit()

        return jsonify({"message": "已成功撤回請假申請，課程維持正常上課！"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@course_bp.route("/api/courses/<course_id>/approve-leave", methods=["POST"])
@admin_required
def approve_course_leave(course_id):
    """Admin approves leave: marks course cancelled (grey), refunds credit."""
    try:
        c_id = uuid.UUID(course_id)
        course = CourseService.mark_leave(c_id, admin_id=g.current_user.id)
        if not course:
            return jsonify({"error": "課程不存在"}), 404

        return jsonify({"message": "已同意學員請假！時段已釋出轉為灰色置頂，並已將堂數退還至學員帳戶。"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@course_bp.route("/api/courses/<course_id>/reject-leave", methods=["POST"])
@admin_required
def reject_course_leave(course_id):
    """Admin rejects leave request."""
    try:
        c_id = uuid.UUID(course_id)
        bookings = db.session.query(Booking).filter(
            Booking.course_id == c_id,
            Booking.status == BookingStatus.LEAVE_REQUESTED,
            Booking.deleted_at.is_(None)
        ).all()

        for b in bookings:
            b.status = BookingStatus.CONFIRMED

        db.session.commit()
        return jsonify({"message": "已拒絕請假申請，課程維持正常排課。"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@course_bp.route("/api/courses/leave-requests", methods=["GET"])
@admin_required
def get_pending_leave_requests():
    """Admin queries all pending leave requests."""
    bookings = db.session.query(Booking).join(Course).filter(
        Booking.status == BookingStatus.LEAVE_REQUESTED,
        Booking.deleted_at.is_(None)
    ).order_by(Course.start_time.asc()).all()

    result = []
    for b in bookings:
        c = b.course
        result.append({
            "booking_id": str(b.id),
            "course_id": str(c.id),
            "student_id": str(b.user_id),
            "student_name": b.student.display_name if b.student else (c.title or "學員"),
            "student_phone": b.student.phone if b.student else "",
            "coach_name": c.coach.display_name if c and c.coach else "未知",
            "start_time": c.start_time.isoformat() if c else "",
            "location": c.location if c else "",
            "reason": b.reason or "無填寫原因",
            "created_at": b.created_at.isoformat() if b.created_at else ""
        })

    return jsonify(result), 200


@course_bp.route("/api/courses/<course_id>/leave", methods=["POST"])
@admin_required
def mark_course_leave(course_id):
    try:
        c_id = uuid.UUID(course_id)
        course = CourseService.mark_leave(c_id, admin_id=g.current_user.id)
        if not course:
            return jsonify({"error": "Course not found"}), 404
        return jsonify({"message": "課程已標記請假，時段已釋出"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


@course_bp.route("/api/courses/<course_id>", methods=["DELETE"])
@admin_required
def delete_course_public(course_id):
    try:
        c_id = uuid.UUID(course_id)
        # scope=occurrence(預設) 只刪這一堂；scope=series 連固定課表一起停掉
        scope = (request.args.get("scope") or "occurrence").lower()
        if scope not in ("occurrence", "series"):
            return jsonify({"error": "scope 只接受 occurrence 或 series"}), 400

        result = CourseService.delete_course(c_id, scope=scope, admin_id=g.current_user.id)
        if result is None:
            return jsonify({"error": "Course not found"}), 404

        if result["template_removed"]:
            message = "已刪除整個固定課程，往後每週都不會再自動帶入"
            if result["removed_future"]:
                message += f"（同時移除了 {result['removed_future']} 堂尚未上課的同系列課程）"
        else:
            message = "已刪除這一堂課"
        return jsonify({"message": message}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


# ============================================================
# 教練月統計 API
# ============================================================
@course_bp.route("/api/coaches/stats", methods=["GET"])
@roles_required("admin", "coach")
def get_coaches_stats():
    now = datetime.now()
    year = int(request.args.get("year", now.year))
    month = int(request.args.get("month", now.month))

    # A coach may only ever see their own hours/trial revenue — admins see everyone.
    # (Previously this ignored the caller's role entirely and always returned every
    # coach's numbers, letting any coach see every colleague's stats. See Issue 11.)
    coach_id = g.current_user.id if g.current_user.role.value == "coach" else None

    try:
        stats = CourseService.get_coach_monthly_stats(year, month, coach_id=coach_id)
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 每週固定課表模板 API
# ============================================================
@course_bp.route("/api/templates", methods=["GET"])
@admin_required
def get_templates():
    templates = CourseTemplate.get_active_templates()
    result = []
    for t in templates:
        student_ids = t.student_ids or []
        students = []
        if student_ids:
            uuids = [uuid.UUID(sid) for sid in student_ids]
            found = {str(u.id): u.display_name for u in db.session.query(User).filter(User.id.in_(uuids)).all()}
            students = [{"id": sid, "display_name": found.get(sid, "未知")} for sid in student_ids]
        result.append({
            "id": str(t.id),
            "coach_id": str(t.coach_id) if t.coach_id else None,
            "coach_name": t.coach.display_name if t.coach else "未知",
            "coach_color": t.coach.color if t.coach else None,
            "title": t.title,
            "student_ids": student_ids,
            "students": students,
            "day_of_week": t.day_of_week,
            "start_time": t.start_time,
            "end_time": t.end_time,
            "capacity": t.capacity,
            "location": t.location,
            "description": t.description,
            "is_trial": t.is_trial,
            "trial_count": t.trial_count,
            "trial_fee": t.trial_fee
        })
    return jsonify(result), 200


@course_bp.route("/api/templates", methods=["POST"])
@admin_required
def create_template():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    is_trial = bool(data.get("is_trial", False))
    student_ids_raw = data.get("student_ids") or []

    if not is_trial and not student_ids_raw:
        return jsonify({"error": "非體驗課必須從既有學生名單中選擇至少一位學生"}), 400

    try:
        coach_id_str = data.get("coach_id")
        coach_id = uuid.UUID(coach_id_str) if coach_id_str else None

        student_uuids = [uuid.UUID(sid) for sid in student_ids_raw]
        if student_uuids:
            found_count = db.session.query(User).filter(
                User.id.in_(student_uuids), User.deleted_at.is_(None)
            ).count()
            if found_count != len(student_uuids):
                return jsonify({"error": "選擇的學生資料中有無法辨識的項目，請重新選擇"}), 400

        tmpl = CourseTemplate(
            coach_id=coach_id,
            title=data.get("title"),
            student_ids=[str(sid) for sid in student_uuids] or None,
            day_of_week=int(data["day_of_week"]),
            start_time=data["start_time"],
            end_time=data["end_time"],
            capacity=int(data.get("capacity", 4)),
            location=data.get("location", "court_out_1"),
            description=data.get("description"),
            is_trial=is_trial,
            trial_count=int(data["trial_count"]) if data.get("trial_count") else None,
            trial_fee=int(data["trial_fee"]) if data.get("trial_fee") else None,
            is_active=True
        )
        tmpl.save()
        CourseTemplate.commit()
        return jsonify({"message": "Template created successfully", "id": str(tmpl.id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@course_bp.route("/api/templates/<template_id>", methods=["DELETE"])
@admin_required
def delete_template(template_id):
    try:
        t_id = uuid.UUID(template_id)
        tmpl = CourseTemplate.get(t_id)
        if not tmpl:
            return jsonify({"error": "Template not found"}), 404
        tmpl.soft_delete()
        CourseTemplate.commit()
        return jsonify({"message": "Template deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@course_bp.route("/api/templates/apply-to-week", methods=["POST"])
@admin_required
def apply_templates_to_week():
    data = request.get_json(silent=True) or {}
    week_start_str = data.get("week_start")
    
    if not week_start_str:
        return jsonify({"error": "week_start (YYYY-MM-DD) is required"}), 400

    try:
        week_start_dt = datetime.fromisoformat(week_start_str)
        result = CourseService.generate_courses_from_templates(week_start_dt)
        created_count = result["created_count"]
        skipped = result["skipped"]

        message = f"成功套用每週課表模板，建立了 {created_count} 堂課程"
        if skipped:
            skipped_desc = "、".join(f"{s['student_name']}（{s['reason']}）" for s in skipped)
            message += f"；有 {len(skipped)} 位學員因故未被排入：{skipped_desc}"

        return jsonify({
            "message": message,
            "created_count": created_count,
            "skipped": skipped
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
