"""remove credit_cost from courses and course_templates

Revision ID: a1f3c9d02b77
Revises: 9a241962b518
Create Date: 2026-08-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1f3c9d02b77'
down_revision = '9a241962b518'
branch_labels = None
depends_on = None


def upgrade():
    # Course-level credit_cost is no longer tracked or enforced by the
    # system — course info (including any point cost) is now managed
    # manually by the client outside this app.
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('credit_cost')

    with op.batch_alter_table('course_templates', schema=None) as batch_op:
        batch_op.drop_column('credit_cost')


def downgrade():
    with op.batch_alter_table('course_templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('credit_cost', sa.Integer(), nullable=False, server_default='1'))

    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('credit_cost', sa.Integer(), nullable=False, server_default='1'))
