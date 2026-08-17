"""
Seed script: Import students from CSV and create coach/admin accounts.
Run via: docker compose exec api python seed_data.py
"""
import csv
import os
import sys

# Ensure the app directory is in the Python path
sys.path.insert(0, os.path.dirname(__file__))

from __init__ import create_app
from extensions import db
from models.user import User, UserRole, Gender
from werkzeug.security import generate_password_hash


def parse_gender(value: str) -> Gender | None:
    mapping = {
        '男': Gender.MALE,
        '女': Gender.FEMALE,
        '其他': Gender.OTHER,
    }
    return mapping.get(value.strip())


def parse_venues(value: str) -> list[str] | None:
    mapping = {
        '室內': ['室內'],
        '室外': ['室外'],
    }
    return mapping.get(value.strip())


def seed_coaches():
    """Create the 6 coaches + 1 admin (小編) with assigned colors."""
    coaches = [
        {"display_name": "王教練", "color": "#60A5FA", "phone": None},   # 淺藍色
        {"display_name": "宋教練", "color": "#F472B6", "phone": None},   # 粉紅色
        {"display_name": "張教練", "color": "#FACC15", "phone": None},   # 黃色
        {"display_name": "柯教練", "color": "#4ADE80", "phone": None},   # 綠色
        {"display_name": "湯教練", "color": "#FB923C", "phone": None},   # 橘色
        {"display_name": "蔡教練", "color": "#2563EB", "phone": None},   # 深藍色
    ]

    created = 0
    for coach_data in coaches:
        # Check if already exists
        existing = db.session.query(User).filter(
            User.display_name == coach_data["display_name"],
            User.role == UserRole.COACH,
            User.deleted_at.is_(None)
        ).first()
        if existing:
            print(f"  [SKIP] 教練 '{coach_data['display_name']}' 已存在")
            continue

        coach = User(
            display_name=coach_data["display_name"],
            role=UserRole.COACH,
            color=coach_data["color"],
            phone=coach_data.get("phone"),
            password_hash=generate_password_hash("coach123"),  # Default password for coaches
        )
        db.session.add(coach)
        created += 1
        print(f"  [CREATE] 教練 '{coach_data['display_name']}' (顏色: {coach_data['color']})")

    # Create admin account (小編)
    existing_admin = db.session.query(User).filter(
        User.display_name == "小編",
        User.role == UserRole.ADMIN,
        User.deleted_at.is_(None)
    ).first()
    if not existing_admin:
        admin = User(
            display_name="小編",
            role=UserRole.ADMIN,
            password_hash=generate_password_hash("admin123"),
        )
        db.session.add(admin)
        created += 1
        print(f"  [CREATE] 管理員 '小編'")
    else:
        print(f"  [SKIP] 管理員 '小編' 已存在")

    # Make 蔡教練 also have admin privileges by creating a separate admin account
    # or we note that 蔡教練 already exists as coach and admins can manage everything
    existing_tsai_admin = db.session.query(User).filter(
        User.display_name == "蔡教練(管理)",
        User.role == UserRole.ADMIN,
        User.deleted_at.is_(None)
    ).first()
    if not existing_tsai_admin:
        tsai_admin = User(
            display_name="蔡教練(管理)",
            role=UserRole.ADMIN,
            password_hash=generate_password_hash("admin123"),
        )
        db.session.add(tsai_admin)
        created += 1
        print(f"  [CREATE] 管理員 '蔡教練(管理)'")
    else:
        print(f"  [SKIP] 管理員 '蔡教練(管理)' 已存在")

    db.session.commit()
    print(f"  教練/管理員建立完成: {created} 筆新增\n")


def seed_students_from_csv(csv_path: str):
    """Import students from CSV file with deduplication."""
    if not os.path.exists(csv_path):
        print(f"  [ERROR] CSV 檔案不存在: {csv_path}")
        return

    # Read CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"  CSV 讀取到 {len(rows)} 筆記錄")

    # Deduplicate by phone number (keep last occurrence)
    seen_phones = {}
    for row in rows:
        phone = row.get('聯絡電話 ', '').strip()
        if phone:
            seen_phones[phone] = row  # Later entries overwrite earlier ones

    unique_rows = list(seen_phones.values())
    print(f"  去重後 {len(unique_rows)} 筆唯一學生")

    created = 0
    skipped = 0
    for row in unique_rows:
        name = row.get('學生姓名', '').strip()
        nickname = row.get('小名', '').strip()
        gender_str = row.get('性別', '').strip()
        phone = row.get('聯絡電話 ', '').strip()
        line_id = row.get('LINE ID', '').strip()
        line_display_name = row.get('LINE 名稱', '').strip()
        venue = row.get('場地選擇', '').strip()
        notes = row.get('有什麼想跟教練說的?', '').strip()

        if not name or not phone:
            print(f"  [SKIP] 缺少必要欄位: name='{name}', phone='{phone}'")
            skipped += 1
            continue

        # Special handling: LINE ID "同電話" → use phone number
        if line_id == '同電話':
            line_id = phone

        # Check if already exists (by phone)
        existing = db.session.query(User).filter(
            User.phone == phone,
            User.deleted_at.is_(None)
        ).first()
        if existing:
            print(f"  [SKIP] 學生 '{name}' (電話: {phone}) 已存在")
            skipped += 1
            continue

        # Check if line_id already exists (skip if duplicate)
        if line_id:
            existing_line = db.session.query(User).filter(
                User.line_id == line_id,
                User.deleted_at.is_(None)
            ).first()
            if existing_line:
                print(f"  [WARN] LINE ID '{line_id}' 已被 '{existing_line.display_name}' 使用，學生 '{name}' 的 line_id 將設為 None")
                line_id = None

        student = User(
            display_name=name,
            nickname=nickname if nickname else None,
            gender=parse_gender(gender_str),
            phone=phone,
            line_id=line_id if line_id else None,
            line_display_name=line_display_name if line_display_name else None,
            role=UserRole.STUDENT,
            credits=0,
            preferred_venues=parse_venues(venue),
            notes=notes if notes else None,
            password_hash=generate_password_hash(phone),  # Password = phone number
        )
        db.session.add(student)
        created += 1
        print(f"  [CREATE] 學生 '{name}' (小名: {nickname}, 電話: {phone})")

    db.session.commit()
    print(f"\n  學生匯入完成: {created} 筆新增, {skipped} 筆跳過\n")


def main():
    app = create_app()
    with app.app_context():
        print("=" * 50)
        print("KOL 網球管理系統 — 資料初始化")
        print("=" * 50)

        print("\n[1/2] 建立教練與管理員帳號...")
        seed_coaches()

        print("[2/2] 匯入學生資料...")
        csv_path = os.path.join(os.path.dirname(__file__), '網球學生名單與聯絡資訊.csv')
        seed_students_from_csv(csv_path)

        # Summary
        total_users = db.session.query(User).filter(User.deleted_at.is_(None)).count()
        coaches = db.session.query(User).filter(User.role == UserRole.COACH, User.deleted_at.is_(None)).count()
        admins = db.session.query(User).filter(User.role == UserRole.ADMIN, User.deleted_at.is_(None)).count()
        students = db.session.query(User).filter(User.role == UserRole.STUDENT, User.deleted_at.is_(None)).count()

        print("=" * 50)
        print(f"資料庫統計:")
        print(f"  總使用者: {total_users}")
        print(f"  教練: {coaches}")
        print(f"  管理員: {admins}")
        print(f"  學生: {students}")
        print("=" * 50)


if __name__ == '__main__':
    main()
