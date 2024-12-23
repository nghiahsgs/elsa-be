"""remove questions_answered column

Revision ID: remove_questions_answered
Revises: create_quiz_scores
Create Date: 2023-12-23 22:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'remove_questions_answered'
down_revision = 'create_quiz_scores'
branch_labels = None
depends_on = None

def upgrade():
    # Drop questions_answered column
    op.drop_column('quiz_participant_scores', 'questions_answered')

def downgrade():
    # Add questions_answered column back
    op.add_column('quiz_participant_scores',
        sa.Column('questions_answered', sa.Integer(), nullable=False, server_default='0')
    )
