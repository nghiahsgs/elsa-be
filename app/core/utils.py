import random
import string
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.quiz import Quiz

async def generate_unique_quiz_code(db: AsyncSession) -> str:
    """Generate a unique 6-character code for a quiz."""
    while True:
        # Generate a random 6-character code (3 letters followed by 3 numbers)
        letters = ''.join(random.choices(string.ascii_uppercase, k=3))
        numbers = ''.join(random.choices(string.digits, k=3))
        code = f"{letters}{numbers}"
        
        # Check if code exists
        exists = await db.execute(
            "SELECT 1 FROM quizzes WHERE code = :code",
            {"code": code}
        )
        if not exists.scalar():
            return code
