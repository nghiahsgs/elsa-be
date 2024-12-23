import random
import string
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.quiz import Quiz

async def generate_unique_quiz_code(db: AsyncSession) -> str:
    """Generate a unique 6-character code for a quiz."""
    while True:
        # Generate a random 6-character code (3 letters followed by 3 numbers)
        letters = ''.join(random.choices(string.ascii_uppercase, k=3))
        numbers = ''.join(random.choices(string.digits, k=3))
        code = f"{letters}{numbers}"
        
        # Check if code exists using SQLAlchemy's select
        stmt = select(Quiz).where(Quiz.code == code)
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            return code
