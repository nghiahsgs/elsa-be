"""initial schema

Revision ID: initial_schema_001
Revises: 
Create Date: 2024-12-24 09:47:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'initial_schema_001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Create quizzes table
    op.create_table('quizzes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=6), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='idle'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quizzes_code'), 'quizzes', ['code'], unique=True)

    # Create questions table
    op.create_table('questions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('quiz_id', sa.Integer(), nullable=True),
        sa.Column('text', sa.String(length=500), nullable=False),
        sa.Column('options', sa.JSON(), nullable=False),
        sa.Column('correct_answer', sa.Integer(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('order', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create quiz_connections table
    op.create_table(
        'quiz_connections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quiz_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('connected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quiz_connections_id'), 'quiz_connections', ['id'], unique=False)

    # Create quiz_participant_scores table
    op.create_table(
        'quiz_participant_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quiz_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quiz_participant_scores_id'), 'quiz_participant_scores', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_quiz_participant_scores_id'), table_name='quiz_participant_scores')
    op.drop_table('quiz_participant_scores')
    op.drop_index(op.f('ix_quiz_connections_id'), table_name='quiz_connections')
    op.drop_table('quiz_connections')
    op.drop_table('questions')
    op.drop_index(op.f('ix_quizzes_code'), table_name='quizzes')
    op.drop_table('quizzes')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
