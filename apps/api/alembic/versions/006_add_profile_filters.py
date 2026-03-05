"""Add experience_level and job_type to job_search_profiles

Revision ID: 006
Revises: 005_add_job_match_score
Create Date: 2024-03-05 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add experience_level and job_type columns to job_search_profiles table
    op.add_column(
        'job_search_profiles',
        sa.Column('experience_level', sa.String(length=50), nullable=True)
    )
    op.add_column(
        'job_search_profiles',
        sa.Column('job_type', sa.String(length=50), nullable=True)
    )


def downgrade() -> None:
    # Remove columns
    op.drop_column('job_search_profiles', 'job_type')
    op.drop_column('job_search_profiles', 'experience_level')
