from flask import Blueprint, request, jsonify, g

from services.feedback_service import FeedbackService
from utils.auth import roles_required

feedback_bp = Blueprint("feedback_bp", __name__)


def _clean_text(value) -> str:
    """去掉資料庫存不進去的字元：NUL，以及無法編碼成 UTF-8 的半個 emoji
    （lone surrogate，貼上被截斷的文字時會出現）。非字串一律當成空字串。"""
    if not isinstance(value, str):
        return ""
    return value.replace("\x00", "").encode("utf-8", "ignore").decode("utf-8").strip()


# 只有送出，沒有讀取：回饋由開發端直接從資料庫看，網站上任何人都看不到清單。
@feedback_bp.route("/api/feedback", methods=["POST"])
@roles_required("admin", "coach")
def create_feedback():
    # silent=True 只會吞掉格式錯誤；巢狀太深的 JSON 會丟 RecursionError，
    # 這裡一併當成「沒有內容」回 400，不要變成 500。
    try:
        data = request.get_json(silent=True)
    except Exception:
        data = None
    if not isinstance(data, dict):
        data = {}

    content = _clean_text(data.get("content"))
    if not content:
        return jsonify({"error": "請輸入回饋內容"}), 400
    if len(content) > FeedbackService.MAX_CONTENT_LENGTH:
        return jsonify({"error": f"回饋內容請勿超過 {FeedbackService.MAX_CONTENT_LENGTH} 字"}), 400

    page_url = _clean_text(data.get("page_url")) or None

    FeedbackService.create_feedback(
        user_id=g.current_user.id,
        role=g.current_user.role.value,
        content=content,
        page_url=page_url,
    )
    return jsonify({"message": "已收到您的回饋，謝謝！"}), 201
