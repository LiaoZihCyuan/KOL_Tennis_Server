import os
import jwt
from functools import wraps
from flask import request, jsonify, g
from extensions import db
from models.user import User, UserRole

def get_secret_key():
    return os.getenv("SECRET_KEY", "a_very_secret_key_for_dev")


def _resolve_current_user():
    """Decode the Authorization: Bearer <jwt> header and load the User.
    Returns (user, None) on success, or (None, (message, status_code)) on failure."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, ("請先登入", 401)

    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None, ("登入憑證已過期，請重新登入", 401)
    except jwt.InvalidTokenError:
        return None, ("登入憑證無效，請重新登入", 401)

    user = User.get(payload.get("user_id"))
    if not user or user.deleted_at is not None:
        return None, ("使用者不存在", 401)
    return user, None


def login_required(f):
    """Any authenticated user (student / coach / admin)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user, err = _resolve_current_user()
        if err:
            return jsonify({"error": err[0]}), err[1]
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def roles_required(*roles):
    """Restrict to specific roles, e.g. @roles_required('admin', 'coach')."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user, err = _resolve_current_user()
            if err:
                return jsonify({"error": err[0]}), err[1]
            if user.role.value not in roles:
                return jsonify({"error": "權限不足"}), 403
            g.current_user = user
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Admin / 小編 only."""
    return roles_required(UserRole.ADMIN.value)(f)
