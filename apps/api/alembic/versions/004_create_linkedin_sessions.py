"""Create linkedin_sessions table

Revision ID: 004_create_linkedin_sessions
Revises: 003_create_applications
Create Date: 2024-01-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '004_create_linkedin_sessions'
down_revision: Union[str, None] = '003_create_applications'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

linkedin_status = postgresql.ENUM(
    "connected",
    "expired",
    "invalid",
    "not_set",
    name="linkedin_status",
    create_type=False
)


def upgrade() -> None:
    linkedin_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'linkedin_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), unique=True, nullable=False),
        sa.Column('encrypted_cookie', sa.Text(), nullable=False),
        sa.Column('status', linkedin_status, nullable=False, server_default='not_set'),
        sa.Column('last_validated_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('idx_linkedin_sessions_user_id', 'linkedin_sessions', ['user_id'])
    op.create_index('idx_linkedin_sessions_status', 'linkedin_sessions', ['status'])


def downgrade() -> None:
    op.drop_index('idx_linkedin_sessions_status', table_name='linkedin_sessions')
    op.drop_index('idx_linkedin_sessions_user_id', table_name='linkedin_sessions')
    op.drop_table('linkedin_sessions')

    linkedin_status.drop(op.get_bind(), checkfirst=True)
