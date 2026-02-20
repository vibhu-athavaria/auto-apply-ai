"""Create jobs table

Revision ID: 001_create_jobs
Revises:
Create Date: 2024-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_create_jobs'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('linkedin_job_id', sa.String(100), nullable=False, unique=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('job_url', sa.Text(), nullable=False),
        sa.Column('easy_apply', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('search_profile_id', sa.String(36), sa.ForeignKey('job_search_profiles.id'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='discovered'),
        sa.Column('discovered_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create indexes
    op.create_index('idx_jobs_linkedin_job_id', 'jobs', ['linkedin_job_id'])
    op.create_index('idx_jobs_user_id', 'jobs', ['user_id'])
    op.create_index('idx_jobs_search_profile_id', 'jobs', ['search_profile_id'])
    op.create_index('idx_jobs_status', 'jobs', ['status'])
    op.create_index('idx_jobs_discovered_at', 'jobs', ['discovered_at'])


def downgrade() -> None:
    op.drop_index('idx_jobs_discovered_at', table_name='jobs')
    op.drop_index('idx_jobs_status', table_name='jobs')
    op.drop_index('idx_jobs_search_profile_id', table_name='jobs')
    op.drop_index('idx_jobs_user_id', table_name='jobs')
    op.drop_index('idx_jobs_linkedin_job_id', table_name='jobs')
    op.drop_table('jobs')
