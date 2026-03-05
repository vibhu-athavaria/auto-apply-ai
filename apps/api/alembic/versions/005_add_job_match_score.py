"""Add match_score to jobs table

Revision ID: 005
Revises: 004_create_linkedin_sessions
Create Date: 2024-03-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004_create_linkedin_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add match_score column to jobs table
    op.add_column(
        'jobs',
        sa.Column('match_score', sa.Integer(), nullable=True)
    )
    # Create index on match_score for efficient filtering
    op.create_index('idx_jobs_match_score', 'jobs', ['match_score'])


def downgrade() -> None:
    # Remove index and column
    op.drop_index('idx_jobs_match_score', table_name='jobs')
    op.drop_column('jobs', 'match_score')
