import os
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
import jwt
from werkzeug.security import check_password_hash, generate_password_hash
from extensions import db
from models.user import User
from utils.auth import get_secret_key

auth_bp = Blueprint("auth_bp", __name__, url_prefix="/api/auth")


@auth_bp.route("/config", methods=["GET"])
def get_auth_config():
    """Returns public auth config such as LINE_LIFF_ID."""
    liff_id = os.getenv("LINE_LIFF_ID", "2011132056-28GhLpgi")
    return jsonify({
        "line_liff_id": liff_id
    }), 200


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "請提供帳號與密碼"}), 400

    identifier = (data.get("identifier") or data.get("username") or "").strip()
    password = data.get("password", "")

    if not identifier or not password:
        return jsonify({"error": "帳號與密碼為必填"}), 400

    # Search user by username, phone, email, or line_id.
    # display_name is deliberately NOT a login identifier: it is the name shown on
    # the calendar, it gets renamed, and it is not unique (the roster legitimately
    # contains people with the same name), so matching on it could log the wrong
    # person in. Every account that can actually log in has a unique username.
    user = db.session.query(User).filter(
        (User.username == identifier) |
        (User.phone == identifier) |
        (User.email == identifier) |
        (User.line_id == identifier),
        User.deleted_at.is_(None)
    ).first()

    if not user:
        return jsonify({"error": "帳號或密碼錯誤"}), 401

    if not user.password_hash or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "帳號或密碼錯誤"}), 401

    # Generate JWT token (expires in 7 days)
    payload = {
        "user_id": str(user.id),
        "role": user.role.value,
        "display_name": user.display_name,
        "exp": datetime.now(timezone.utc) + timedelta(days=7)
    }
    token = jwt.encode(payload, get_secret_key(), algorithm="HS256")

    return jsonify({
        "message": "登入成功",
        "token": token,
        "user": {
            "id": str(user.id),
            "display_name": user.display_name,
            "role": user.role.value,
            "color": user.color
        }
    }), 200


# ============================================================
# LINE LIFF 免密碼登入與綁定
# ============================================================

@auth_bp.route("/line-liff", methods=["POST"])
def line_liff_login():
    """Handles automatic authentication when opened via LINE LIFF."""
    data = request.get_json(silent=True)
    if not data or not data.get("line_user_id"):
        return jsonify({"error": "請提供有效的 LINE User ID"}), 400

    line_user_id = data["line_user_id"].strip()
    line_display_name = data.get("display_name", "")

    # Check if a user with this line_id already exists
    user = db.session.query(User).filter(
        User.line_id == line_user_id,
        User.deleted_at.is_(None)
    ).first()

    if user:
        # Update line_display_name if changed
        if line_display_name and user.line_display_name != line_display_name:
            user.line_display_name = line_display_name
            db.session.commit()

        # Issue JWT Token
        payload = {
            "user_id": str(user.id),
            "role": user.role.value,
            "display_name": user.display_name,
            "exp": datetime.now(timezone.utc) + timedelta(days=14)
        }
        token = jwt.encode(payload, get_secret_key(), algorithm="HS256")

        return jsonify({
            "is_bound": True,
            "message": f"歡迎回來，{user.display_name}！",
            "token": token,
            "user": {
                "id": str(user.id),
                "display_name": user.display_name,
                "role": user.role.value,
                "credits": user.credits,
                "color": user.color
            }
        }), 200
    else:
        return jsonify({
            "is_bound": False,
            "message": "此 LINE 帳號尚未綁定學員資料，請輸入報名手機號碼以完成綁定。",
            "line_user_id": line_user_id,
            "line_display_name": line_display_name
        }), 200


@auth_bp.route("/line-bind", methods=["POST"])
def line_bind_student():
    """Binds LINE User ID with pre-existing student profile via phone number."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "請提供綁定資料"}), 400

    line_user_id = data.get("line_user_id", "").strip()
    phone = data.get("phone", "").strip()
    student_name = data.get("student_name", "").strip()
    line_display_name = data.get("line_display_name", "").strip()

    if not line_user_id or not phone:
        return jsonify({"error": "LINE User ID 與手機號碼為必填"}), 400

    # Search student by phone
    query = db.session.query(User).filter(
        User.phone == phone,
        User.deleted_at.is_(None)
    )
    if student_name:
        query = query.filter(User.display_name.ilike(f"%{student_name}%"))

    student = query.first()

    if not student:
        return jsonify({
            "error": "找不到符合的學員資料。請確認手機號碼是否與報名時填寫的一致，或聯繫小編確認！"
        }), 404

    # Bind LINE ID
    student.line_id = line_user_id
    if line_display_name:
        student.line_display_name = line_display_name

    db.session.commit()

    # Generate JWT token
    payload = {
        "user_id": str(student.id),
        "role": student.role.value,
        "display_name": student.display_name,
        "exp": datetime.now(timezone.utc) + timedelta(days=14)
    }
    token = jwt.encode(payload, get_secret_key(), algorithm="HS256")

    return jsonify({
        "message": f"🎉 綁定成功！歡迎 {student.display_name} 進入 KOL 網球專區",
        "token": token,
        "user": {
            "id": str(student.id),
            "display_name": student.display_name,
            "role": student.role.value,
            "credits": student.credits,
            "color": student.color
        }
    }), 200


@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "未登入"}), 401

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=["HS256"])
        user_id = payload.get("user_id")
        user = User.get(user_id)
        if not user or user.deleted_at is not None:
            return jsonify({"error": "使用者不存在"}), 404

        return jsonify({
            "id": str(user.id),
            "display_name": user.display_name,
            "role": user.role.value,
            "color": user.color
        }), 200
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({"error": "登入憑證無效或已過期"}), 401
