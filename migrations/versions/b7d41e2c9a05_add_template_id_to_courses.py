"""add template_id to courses

Links an auto-generated course back to the CourseTemplate it came from, so we
can tell "delete just this occurrence" from "stop the whole weekly series",
and so a deleted occurrence is not silently regenerated on the next calendar
load.

Revision ID: b7d41e2c9a05
Revises: a1f3c9d02b77
Create Date: 2026-08-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7d41e2c9a05'
down_revision = 'a1f3c9d02b77'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('template_id', sa.UUID(), nullable=True))
        batch_op.create_foreign_key(
            'fk_courses_template_id', 'course_templates', ['template_id'], ['id']
        )

    # Backfill: courses already generated from a template predate this column,
    # so without this they'd stay unlinked and would keep coming back after
    # being deleted. Match on the same key generate_courses_from_templates
    # uses -- weekday + local start time + location -- in Asia/Taipei, which is
    # the timezone template times are defined in.
    op.execute(
        """
        UPDATE courses c
        SET template_id = t.id
        FROM course_templates t
        WHERE c.template_id IS NULL
          AND t.deleted_at IS NULL
          AND c.location = t.location
          AND EXTRACT(ISODOW FROM (c.start_time AT TIME ZONE 'Asia/Taipei')) - 1 = t.day_of_week
          AND to_char(c.start_time AT TIME ZONE 'Asia/Taipei', 'HH24:MI') = t.start_time
        """
    )


def downgrade():
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_constraint('fk_courses_template_id', type_='foreignkey')
        batch_op.drop_column('template_id')
