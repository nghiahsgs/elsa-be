"""create quiz connections table

Revision ID: create_quiz_connections
Revises: 
Create Date: 2024-12-23 09:09:09.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'create_quiz_connections'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index(op.f('ix_quiz_connections_id'), table_name='quiz_connections')
    op.drop_table('quiz_connections')
