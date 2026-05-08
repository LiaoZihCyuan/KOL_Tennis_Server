import os
import jwt
from functools import wraps
from flask import request, jsonify
from extensions import db
from models.user import User

def get_secret_key():
    return os.getenv("SECRET_KEY", "a_very_secret_key_for_dev")

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid token"}), 401
        
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, get_secret_key(), algorithms=["HS256"])
            user_id = payload.get("user_id")
            
            user = User.get(user_id)
            if not user or user.role.value != "admin":
                return jsonify({"error": "Admin privileges required"}), 403
                
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
            
        return f(*args, **kwargs)
    return decorated_function
