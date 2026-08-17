import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from extensions import db
from models.renewal_request import RenewalRequest, RenewalStatus
from models.credit_transaction import CreditTransaction, TransactionType
from models.user import User
from utils.auth import admin_required, login_required

renewal_bp = Blueprint("renewal_bp", __name__, url_prefix="/api/renewals")


@renewal_bp.route("/apply", methods=["POST"])
@login_required
def apply_renewal():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "請提供申請資料"}), 400

    current_user = g.current_user
    if current_user.role.value == "student":
        # students may only apply for themselves, never on behalf of others
        user_id = current_user.id
    else:
        user_id_str = data.get("user_id")
        if not user_id_str:
            return jsonify({"error": "user_id 為必填"}), 400
        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            return jsonify({"error": "user_id 格式錯誤"}), 400

    try:
        user = User.get(user_id)
        if not user:
            return jsonify({"error": "學生不存在"}), 404

        req = RenewalRequest(
            user_id=user_id,
            credits_requested=int(data.get("credits", 10)),
            amount_paid=int(data.get("amount", 0)) if data.get("amount") else None,
            payment_proof=data.get("payment_proof", ""),
            status=RenewalStatus.PENDING
        )
        req.save()
        RenewalRequest.commit()

        return jsonify({
            "message": "續課申請已送出，小編確認繳費後將立即為您入點！",
            "request_id": str(req.id)
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@renewal_bp.route("/", methods=["GET"])
@admin_required
def get_renewals():
    status_filter = request.args.get("status")
    stmt = db.select(RenewalRequest).where(RenewalRequest.deleted_at.is_(None))
    if status_filter:
        try:
            stmt = stmt.where(RenewalRequest.status == RenewalStatus(status_filter))
        except ValueError:
            pass
            
    stmt = stmt.order_by(RenewalRequest.created_at.desc())
    requests = list(db.session.scalars(stmt))

    return jsonify([{
        "id": str(r.id),
        "user_id": str(r.user_id),
        "student_name": r.student.display_name if r.student else "未知",
        "student_phone": r.student.phone if r.student else "",
        "credits_requested": r.credits_requested,
        "amount_paid": r.amount_paid,
        "payment_proof": r.payment_proof,
        "status": r.status.value,
        "created_at": r.created_at.isoformat() if r.created_at else ""
    } for r in requests]), 200


@renewal_bp.route("/<request_id>/approve", methods=["POST"])
@admin_required
def approve_renewal(request_id):
    data = request.get_json(silent=True) or {}

    try:
        r_id = uuid.UUID(request_id)
        req = RenewalRequest.get(r_id)
        if not req or req.status != RenewalStatus.PENDING:
            return jsonify({"error": "申請單不存在或已被處理"}), 404

        admin_id = g.current_user.id

        # 1. Update status
        req.status = RenewalStatus.APPROVED
        req.admin_user_id = admin_id
        req.admin_notes = data.get("admin_notes", "已確認繳費核准入點")

        # 2. Add credits (real balance) and lesson_count (matching "堂數" display) to student
        student = req.student
        student.credits += req.credits_requested
        student.lesson_count += req.credits_requested

        # 3. Create credit transaction log
        tx = CreditTransaction(
            user_id=student.id,
            type=TransactionType.PURCHASE,
            amount=req.credits_requested,
            admin_user_id=admin_id,
            description=f"學生續課：{req.credits_requested} 堂 (金額: ${req.amount_paid or 0})"
        )
        tx.save()

        db.session.commit()
        return jsonify({
            "message": f"已核准 {student.display_name} 的續課申請，成功存入 {req.credits_requested} 堂課！",
            "new_credits": student.credits
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@renewal_bp.route("/quick-topup", methods=["POST"])
@admin_required
def quick_topup():
    """Admin directly tops up credits for a student."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "請提供儲值資料"}), 400

    student_id_str = data.get("student_id")
    credits_add = int(data.get("credits", 0))
    amount = data.get("amount")
    note = data.get("note", "小編手動儲值續課")

    if not student_id_str or credits_add <= 0:
        return jsonify({"error": "請提供有效的學生ID與儲值堂數"}), 400

    try:
        student_id = uuid.UUID(student_id_str)
        student = User.get(student_id)
        if not student:
            return jsonify({"error": "學生不存在"}), 404

        admin_id = g.current_user.id

        # Add credits (real balance) and lesson_count (matching "堂數" display)
        student.credits += credits_add
        student.lesson_count += credits_add

        # Log transaction
        tx = CreditTransaction(
            user_id=student.id,
            type=TransactionType.PURCHASE,
            amount=credits_add,
            admin_user_id=admin_id,
            description=f"續課儲值：{credits_add} 堂 (實收: ${amount or 0}) - {note}"
        )
        tx.save()

        db.session.commit()
        return jsonify({
            "message": f"成功為 {student.display_name} 儲值 {credits_add} 堂課！",
            "credits": student.credits
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
