"""add username login field to users

Revision ID: fd4cd81414f5
Revises: ace2c0a2dc2f
Create Date: 2026-09-08 11:12:40.877706

登入帳號從 display_name 獨立出來。display_name 是課表上顯示的名字，會被改、
而且本來就允許同名（名冊裡有 13 組同名的人），拿它當登入識別會抓錯人。

回填只針對「真的會登入」的使用者（password_hash 不為 NULL），把 username 設成
現有的 display_name，這樣既有帳號的登入方式完全不變。其餘純排課名冊的學生
（沒有密碼、沒有手機、沒有 LINE）留 NULL——Postgres 的 unique 允許多筆 NULL。
回填當下已確認有密碼的使用者之間沒有同名，不會撞到唯一鍵。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fd4cd81414f5'
down_revision = 'ace2c0a2dc2f'
branch_labels = None
depends_on = None

# 具名約束：不命名的話 downgrade 的 drop_constraint(None) 會失敗
UNIQUE_CONSTRAINT_NAME = 'uq_users_username'


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('username', sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint(UNIQUE_CONSTRAINT_NAME, ['username'])

    # 回填：只給會登入的使用者，避免大量無密碼名冊資料佔用帳號名稱
    op.execute(
        """
        UPDATE users
        SET username = display_name
        WHERE password_hash IS NOT NULL
          AND deleted_at IS NULL
          AND username IS NULL
        """
    )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint(UNIQUE_CONSTRAINT_NAME, type_='unique')
        batch_op.drop_column('username')
