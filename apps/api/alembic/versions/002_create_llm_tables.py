"""Create tailored_resumes and llm_usage_logs tables

Revision ID: 002_create_llm_tables
Revises: 001_create_jobs
Create Date: 2024-01-15 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_create_llm_tables'
down_revision: Union[str, None] = '001_create_jobs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tailored_resumes table
    op.create_table(
        'tailored_resumes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('jobs.id'), nullable=False),
        sa.Column('original_resume_id', sa.String(36), sa.ForeignKey('resumes.id'), nullable=False),
        sa.Column('tailored_resume_text', sa.Text(), nullable=False),
        sa.Column('cover_letter', sa.Text(), nullable=True),
        sa.Column('input_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create indexes for tailored_resumes
    op.create_index('idx_tailored_resumes_user_id', 'tailored_resumes', ['user_id'])
    op.create_index('idx_tailored_resumes_job_id', 'tailored_resumes', ['job_id'])
    op.create_index('idx_tailored_resumes_input_hash', 'tailored_resumes', ['input_hash'])
    op.create_index('idx_tailored_resumes_user_job', 'tailored_resumes', ['user_id', 'job_id'], unique=True)

    # Create llm_usage_logs table
    op.create_table(
        'llm_usage_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('estimated_cost', sa.Numeric(10, 6), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('operation', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create indexes for llm_usage_logs
    op.create_index('idx_llm_usage_logs_user_id', 'llm_usage_logs', ['user_id'])


def downgrade() -> None:
    # Drop llm_usage_logs
    op.drop_index('idx_llm_usage_logs_user_id', table_name='llm_usage_logs')
    op.drop_table('llm_usage_logs')

    # Drop tailored_resumes
    op.drop_index('idx_tailored_resumes_user_job', table_name='tailored_resumes')
    op.drop_index('idx_tailored_resumes_input_hash', table_name='tailored_resumes')
    op.drop_index('idx_tailored_resumes_job_id', table_name='tailored_resumes')
    op.drop_index('idx_tailored_resumes_user_id', table_name='tailored_resumes')
    op.drop_table('tailored_resumes')
