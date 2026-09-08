import uuid
import logging
from flask import Blueprint, request, jsonify, g
from werkzeug.security import check_password_hash
from extensions import db
from models.user import User
from models.booking import Booking
from models.course import Course
from models.credit_transaction import CreditTransaction
from models.course_template import CourseTemplate
from services.user_service import UserService
from utils.auth import admin_required, login_required

user_bp = Blueprint("user_bp", __name__, url_prefix="/api/users")


@user_bp.route("/coaches", methods=["GET"])
@login_required
def get_coaches():
    try:
        coaches = UserService.get_coaches()
        result = [{"id": str(c.id), "display_name": c.display_name, "color": c.color} for c in coaches]
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error fetching coaches: {e}")
        return jsonify({"error": "Internal server error"}), 500


@user_bp.route("/students", methods=["GET"])
@admin_required
def get_students():
    try:
        students = UserService.get_students()
        result = [{"id": str(s.id), "display_name": s.display_name, "nickname": s.nickname, "phone": s.phone, "credits": s.credits, "lesson_count": s.lesson_count} for s in students]
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error fetching students: {e}")
        return jsonify({"error": "Internal server error"}), 500


@user_bp.route("/students/stats", methods=["GET"])
@admin_required
def get_students_stats():
    try:
        stats = UserService.get_student_attendance_stats()
        return jsonify(stats), 200
    except Exception as e:
        logging.error(f"Error fetching students stats: {e}")
        return jsonify({"error": "Internal server error"}), 500


@user_bp.route("/<user_id>/full-profile", methods=["GET"])
@login_required
def get_user_full_profile(user_id):
    try:
        uid = uuid.UUID(user_id)

        current_user = g.current_user
        if current_user.role.value != "admin" and current_user.id != uid:
            return jsonify({"error": "權限不足，僅能查看自己的資料"}), 403

        user = User.get(uid)
        if not user or user.deleted_at is not None:
            return jsonify({"error": "使用者不存在"}), 404

        # 1. Attendance history (bookings join courses, plus courses titled with student name)
        bookings = db.session.query(Booking).join(Course).filter(
            Booking.user_id == uid,
            Booking.deleted_at.is_(None),
            Course.deleted_at.is_(None)
        ).order_by(Course.start_time.desc()).all()

        attendance_list = []
        for b in bookings:
            c = b.course
            attendance_list.append({
                "booking_id": str(b.id),
                "course_id": str(c.id) if c else "",
                "course_title": c.title if c else "課程",
                "coach_name": c.coach.display_name if c and c.coach else "未知",
                "coach_color": c.coach.color if c and c.coach else "#3b82f6",
                "start_time": c.start_time.isoformat() if c else "",
                "location": c.location if c else "",
                "status": b.status.value
            })

        # Also find standalone courses with student's name in title
        titled_courses = db.session.query(Course).filter(
            Course.title.ilike(f"%{user.display_name}%"),
            Course.deleted_at.is_(None)
        ).order_by(Course.start_time.desc()).limit(30).all()

        seen_course_ids = {a["course_id"] for a in attendance_list}
        for c in titled_courses:
            if str(c.id) not in seen_course_ids:
                attendance_list.append({
                    "booking_id": "",
                    "course_id": str(c.id),
                    "course_title": c.title,
                    "coach_name": c.coach.display_name if c.coach else "未知",
                    "coach_color": c.coach.color if c.coach else "#3b82f6",
                    "start_time": c.start_time.isoformat(),
                    "location": c.location,
                    "status": "leave_approved" if c.status.value == "cancelled" else ("completed" if c.status.value == "completed" else "confirmed")
                })

        # Sort all attendance by start_time desc
        attendance_list.sort(key=lambda x: x["start_time"], reverse=True)

        # 2. Transaction history
        txs = db.session.query(CreditTransaction).filter(
            CreditTransaction.user_id == uid,
            CreditTransaction.deleted_at.is_(None)
        ).order_by(CreditTransaction.transaction_time.desc()).all()

        tx_list = []
        for t in txs:
            tx_list.append({
                "id": str(t.id),
                "type": t.type.value,
                "amount": t.amount,
                "transaction_time": t.transaction_time.isoformat() if t.transaction_time else "",
                "description": t.description,
                "admin_name": t.admin.display_name if t.admin else "系統"
            })

        # 3. Fixed weekly schedule templates
        day_names = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
        loc_names = {'court_out_1': '室外場 1', 'court_out_2': '室外場 2', 'court_in': '室內場'}
        templates = db.session.query(CourseTemplate).filter(
            CourseTemplate.title.ilike(f"%{user.display_name}%"),
            CourseTemplate.is_active.is_(True),
            CourseTemplate.deleted_at.is_(None)
        ).all()

        fixed_schedules = [{
            "id": str(t.id),
            "day_name": day_names[t.day_of_week] if 0 <= t.day_of_week <= 6 else f"星期{t.day_of_week}",
            "time_range": f"{t.start_time} ~ {t.end_time}",
            "location_name": loc_names.get(t.location, t.location),
            "coach_name": t.coach.display_name if t.coach else "未知"
        } for t in templates]

        return jsonify({
            "user": {
                "id": str(user.id),
                "display_name": user.display_name,
                "username": user.username,
                "nickname": user.nickname,
                "phone": user.phone,
                "email": user.email,
                "line_id": user.line_id,
                "line_display_name": user.line_display_name,
                "gender": user.gender.value if user.gender else None,
                "role": user.role.value,
                "credits": user.credits,
                "lesson_count": user.lesson_count,
                "level": user.level,
                "color": user.color,
                "notes": user.notes,
                "description": user.description,
                "preferred_venues": user.preferred_venues
            },
            "attendance_history": attendance_list,
            "transactions": tx_list,
            "fixed_schedules": fixed_schedules
        }), 200
    except Exception as e:
        logging.error(f"Error fetching user full profile: {e}")
        return jsonify({"error": str(e)}), 500


@user_bp.route("/", methods=["POST"])
@admin_required
def create_user():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    try:
        user = UserService.create_user(data)
        return jsonify({
            "message": "User created successfully",
            "user": {
                "id": str(user.id),
                "display_name": user.display_name,
                "role": user.role.value,
                "credits": user.credits,
                "lesson_count": user.lesson_count
            }
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Error creating user: {e}")
        return jsonify({"error": "Internal server error"}), 500


SELF_SERVICE_FIELDS = {"display_name", "username", "nickname", "phone", "gender", "line_id", "line_display_name", "password"}


@user_bp.route("/<user_id>", methods=["PUT"])
@login_required
def update_user(user_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    try:
        uid = uuid.UUID(user_id)
        current_user = g.current_user

        # current_password is a credential used for verification, never a column to
        # write — pull it out before any whitelisting so it can't be persisted, and
        # so the whitelist below doesn't discard it before we get to check it.
        current_password = (data.pop("current_password", "") or "")

        if current_user.role.value != "admin":
            # Non-admin users may only edit their own profile, and only
            # identity/contact fields — never credits, notes, level, etc.
            if current_user.id != uid:
                return jsonify({"error": "權限不足，僅能編輯自己的資料"}), 403
            data = {k: v for k, v in data.items() if k in SELF_SERVICE_FIELDS}

            # Changing your own account name or password requires proving you know
            # the current password, so a walked-away-from session can't be used to
            # take the account over. Admins resetting someone else's credentials
            # are exempt — they are the recovery path when a user forgets it.
            sensitive = bool(data.get("password")) or "username" in data
            if sensitive:
                if not current_user.password_hash or not check_password_hash(
                    current_user.password_hash, current_password
                ):
                    return jsonify({"error": "目前密碼不正確"}), 403

        user = UserService.update_user(uid, data)
        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "message": "使用者資料更新成功",
            "user": {
                "id": str(user.id),
                "display_name": user.display_name,
                "phone": user.phone,
                "credits": user.credits,
                "lesson_count": user.lesson_count
            }
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Error updating user: {e}")
        return jsonify({"error": "Internal server error"}), 500


@user_bp.route("/", methods=["GET"])
@admin_required
def get_users():
    try:
        users = UserService.get_all_users()
        result = []
        for user in users:
            result.append({
                "id": str(user.id),
                "display_name": user.display_name,
                "username": user.username,
                "email": user.email,
                "line_id": user.line_id,
                "role": user.role.value,
                "credits": user.credits,
                "lesson_count": user.lesson_count,
                "description": user.description,
                "level": user.level,
                "preferred_venues": user.preferred_venues,
                "phone": user.phone,
                "nickname": user.nickname,
                "gender": user.gender.value if user.gender else None,
                "color": user.color,
                "line_display_name": user.line_display_name,
                "notes": user.notes,
            })
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error fetching users: {e}")
        return jsonify({"error": "Internal server error"}), 500
