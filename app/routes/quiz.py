from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.security import get_current_user
from app.core.utils import generate_unique_quiz_code
from app.schemas.quiz import QuizCreate, Quiz as QuizSchema
from app.models.quiz import Quiz, Question
from app.models.user import User
from typing import List
import json

router = APIRouter()

@router.post("/quizzes", response_model=QuizSchema)
async def create_quiz(
    quiz_data: QuizCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new quiz."""
    try:
        # Generate a unique code for the quiz
        quiz_code = await generate_unique_quiz_code(db)
        
        # Create quiz
        quiz = Quiz(
            code=quiz_code,
            title=quiz_data.title,
            description=quiz_data.description,
            created_by_id=current_user.id,
            settings=quiz_data.settings.dict()
        )
        db.add(quiz)
        
        # Create questions
        for i, q_data in enumerate(quiz_data.questions):
            question = Question(
                quiz=quiz,
                text=q_data.text,
                options=q_data.options,
                correct_answer=q_data.correctAnswer,
                score=q_data.score,
                order=i
            )
            db.add(question)
        
        await db.commit()
        await db.refresh(quiz)
        
        # Format response
        return {
            "id": quiz.id,
            "code": quiz.code,
            "createdAt": quiz.created_at,
            "createdBy": {
                "id": current_user.id,
                "email": current_user.email
            },
            "title": quiz.title,
            "description": quiz.description,
            "questions": [
                {
                    "id": q.id,
                    "text": q.text,
                    "options": q.options,
                    "correctAnswer": q.correct_answer,
                    "score": q.score
                }
                for q in sorted(quiz.questions, key=lambda x: x.order)
            ],
            "settings": quiz.settings
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail={
                "error": "ValidationError",
                "message": "Failed to create quiz",
                "details": [{"field": "", "message": str(e)}]
            }
        )
