import uuid
from flask import Blueprint, request, jsonify, g

from services.notification_service import NotificationService
from utils.auth import roles_required, admin_required

notification_bp = Blueprint("notification_bp", __name__)


@notification_bp.route("/api/notifications", methods=["GET"])
@roles_required("admin", "coach")
def list_notifications():
    notifications = NotificationService.list_notifications()
    result = [
        {
            "id": str(n.id),
            "message": n.message,
            "created_by_name": n.author.display_name if n.author else None,
            "created_at": n.created_at.isoformat()
        }
        for n in notifications
    ]
    return jsonify(result), 200


@notification_bp.route("/api/notifications", methods=["POST"])
@admin_required
def create_notification():
    data = request.get_json(silent=True)
    message = (data or {}).get("message", "").strip()
    if not message:
        return jsonify({"error": "請輸入通知內容"}), 400

    notification = NotificationService.create_notification(
        message=message,
        created_by=g.current_user.id
    )
    return jsonify({"id": str(notification.id), "message": "已新增通知"}), 201


@notification_bp.route("/api/notifications/<notification_id>", methods=["DELETE"])
@admin_required
def delete_notification(notification_id):
    try:
        n_id = uuid.UUID(notification_id)
    except ValueError:
        return jsonify({"error": "Invalid notification id"}), 400

    ok = NotificationService.delete_notification(n_id)
    if not ok:
        return jsonify({"error": "通知不存在"}), 404
    return jsonify({"message": "已刪除通知"}), 200
