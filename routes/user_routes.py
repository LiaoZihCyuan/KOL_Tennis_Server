from flask import Blueprint, request, jsonify
from services.user_service import UserService
import logging

user_bp = Blueprint("user_bp", __name__, url_prefix="/api/users")

@user_bp.route("/coaches", methods=["GET"])
def get_coaches():
    try:
        coaches = UserService.get_coaches()
        result = [{"id": str(c.id), "display_name": c.display_name} for c in coaches]
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error fetching coaches: {e}")
        return jsonify({"error": "Internal server error"}), 500

@user_bp.route("/students", methods=["GET"])
def get_students():
    try:
        students = UserService.get_students()
        result = [{"id": str(s.id), "display_name": s.display_name} for s in students]
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error fetching students: {e}")
        return jsonify({"error": "Internal server error"}), 500

@user_bp.route("/", methods=["POST"])
def create_user():
    data = request.get_json()
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
                "credits": user.credits
            }
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Error creating user: {e}")
        return jsonify({"error": "Internal server error"}), 500

@user_bp.route("/", methods=["GET"])
def get_users():
    try:
        users = UserService.get_all_users()
        result = []
        for user in users:
            result.append({
                "id": str(user.id),
                "display_name": user.display_name,
                "email": user.email,
                "line_id": user.line_id,
                "role": user.role.value,
                "credits": user.credits,
                "description": user.description,
                "level": user.level,
                "preferred_venues": user.preferred_venues
            })
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error fetching users: {e}")
        return jsonify({"error": "Internal server error"}), 500
