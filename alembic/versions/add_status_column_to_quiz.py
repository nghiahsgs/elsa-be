"""add_status_column_to_quiz

Revision ID: add_status_column_to_quiz
Revises: 
Create Date: 2024-12-24 07:34:24.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_status_column_to_quiz'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('quizzes', sa.Column('status', sa.String(20), nullable=False, server_default='idle'))


def downgrade() -> None:
    op.drop_column('quizzes', 'status')
