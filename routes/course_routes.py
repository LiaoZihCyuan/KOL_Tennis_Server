import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify
from services.course_service import CourseService
from utils.auth import admin_required

course_bp = Blueprint("course_bp", __name__)

@course_bp.route("/api/courses", methods=["GET"])
def get_courses():
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    
    if not start_date_str or not end_date_str:
        return jsonify({"error": "start_date and end_date are required"}), 400
        
    try:
        start_date = datetime.fromisoformat(start_date_str)
        end_date = datetime.fromisoformat(end_date_str)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use ISO 8601."}), 400
        
    courses = CourseService.get_courses(start_date, end_date)
    return jsonify([{
        "course_id": str(c.id),
        "coach_id": str(c.coach_id),
        "coach_name": c.coach.display_name if c.coach else "未知",
        "title": c.title,
        "start_time": c.start_time.isoformat(),
        "end_time": c.end_time.isoformat(),
        "capacity": c.capacity,
        "location": c.location,
        "credit_cost": c.credit_cost,
        "description": c.description,
        "status": c.status.value,
        "students": [{"id": str(b.student.id), "name": b.student.display_name, "status": b.status.value} for b in c.bookings if b.student]
    } for c in courses]), 200

@course_bp.route("/api/courses", methods=["POST"])
def create_course_public():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
        
    required_fields = ["coach_id", "start_time", "end_time", "capacity", "location", "credit_cost"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
            
    try:
        coach_id = uuid.UUID(data["coach_id"])
        start_time = datetime.fromisoformat(data["start_time"])
        end_time = datetime.fromisoformat(data["end_time"])
        capacity = int(data["capacity"])
        credit_cost = int(data["credit_cost"])
        
        course = CourseService.create_course(
            coach_id=coach_id,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            location=data["location"],
            credit_cost=credit_cost,
            description=data.get("description"),
            title=data.get("title")
        )
        return jsonify({
            "message": "Course created successfully",
            "course_id": str(course.id)
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500

@course_bp.route("/admin/courses", methods=["POST"])
@admin_required
def create_course():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
        
    required_fields = ["coach_id", "start_time", "end_time", "capacity", "location", "credit_cost"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
            
    try:
        coach_id = uuid.UUID(data["coach_id"])
        start_time = datetime.fromisoformat(data["start_time"])
        end_time = datetime.fromisoformat(data["end_time"])
        capacity = int(data["capacity"])
        credit_cost = int(data["credit_cost"])
        
        course = CourseService.create_course(
            coach_id=coach_id,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            location=data["location"],
            credit_cost=credit_cost,
            description=data.get("description"),
            title=data.get("title")
        )
        return jsonify({
            "message": "Course created successfully",
            "course_id": str(course.id)
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500

@course_bp.route("/admin/courses/<course_id>", methods=["PUT"])
@admin_required
def update_course(course_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
        
    try:
        c_id = uuid.UUID(course_id)
        
        # Convert date strings if present
        if "start_time" in data:
            data["start_time"] = datetime.fromisoformat(data["start_time"])
        if "end_time" in data:
            data["end_time"] = datetime.fromisoformat(data["end_time"])
        if "coach_id" in data:
            data["coach_id"] = uuid.UUID(data["coach_id"])
            
        course = CourseService.update_course(c_id, **data)
        if not course:
            return jsonify({"error": "Course not found"}), 404
            
        return jsonify({"message": "Course updated successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500

@course_bp.route("/admin/courses/<course_id>/cancel", methods=["POST"])
@admin_required
def cancel_course(course_id):
    # Retrieve user_id from token
    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ")[1]
    import jwt
    from utils.auth import get_secret_key
    payload = jwt.decode(token, get_secret_key(), algorithms=["HS256"])
    admin_id = uuid.UUID(payload.get("user_id"))
    
    try:
        c_id = uuid.UUID(course_id)
        course = CourseService.cancel_course(c_id, admin_id)
        
        if not course:
            return jsonify({"error": "Course not found"}), 404
            
        return jsonify({"message": "Course cancelled successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500
