"""create quiz participant scores table

Revision ID: create_quiz_scores
Revises: create_quiz_connections
Create Date: 2024-12-23 09:39:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'create_quiz_scores'
down_revision = 'create_quiz_connections'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'quiz_participant_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quiz_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('questions_answered', sa.Integer(), nullable=False, server_default='0'),
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
