"""Drop activity_id foreign key from activity_assignments

Revision ID: drop_activity_fk_001
Revises: add_student_login_cols, add_webinar_school_reg
Create Date: 2026-01-09

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'drop_activity_fk_001'
down_revision = ('add_student_login_cols', 'add_webinar_school_reg')
branch_labels = None
depends_on = None


def upgrade():
    # Drop the foreign key constraint on activity_id
    # Activities can come from external activity engine service
    op.drop_constraint(
        'b2b_activity_assignments_activity_id_fkey',
        'b2b_activity_assignments',
        type_='foreignkey'
    )


def downgrade():
    # Re-add the foreign key constraint
    op.create_foreign_key(
        'b2b_activity_assignments_activity_id_fkey',
        'b2b_activity_assignments',
        'b2b_activities',
        ['activity_id'],
        ['activity_id']
    )
