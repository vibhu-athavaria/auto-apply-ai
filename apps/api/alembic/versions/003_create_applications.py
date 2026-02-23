"""Create applications table

Revision ID: 003_create_applications
Revises: 002_create_llm_tables
Create Date: 2024-01-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '003_create_applications'
down_revision: Union[str, None] = '002_create_llm_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

application_status = postgresql.ENUM(
    "pending",
    "submitted",
    "completed",
    "failed",
    "skipped",
    name="application_status",
    create_type=False
)


def upgrade() -> None:
    application_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'applications',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('jobs.id'), nullable=False),
        sa.Column('tailored_resume_id', sa.String(36), sa.ForeignKey('tailored_resumes.id'), nullable=True),
        sa.Column('status', application_status, nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('linkedin_application_id', sa.String(100), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('idx_applications_user_id', 'applications', ['user_id'])
    op.create_index('idx_applications_job_id', 'applications', ['job_id'])
    op.create_index('idx_applications_status', 'applications', ['status'])
    op.create_index('idx_applications_user_job', 'applications', ['user_id', 'job_id'], unique=True)


def downgrade() -> None:
    op.drop_index('idx_applications_user_job', table_name='applications')
    op.drop_index('idx_applications_status', table_name='applications')
    op.drop_index('idx_applications_job_id', table_name='applications')
    op.drop_index('idx_applications_user_id', table_name='applications')
    op.drop_table('applications')

    application_status.drop(op.get_bind(), checkfirst=True)
