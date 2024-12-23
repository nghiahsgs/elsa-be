from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.core.security import get_current_user
from app.core.utils import generate_unique_quiz_code
from app.schemas.quiz import QuizCreate, Quiz as QuizSchema
from app.schemas.quiz_connection import QuizParticipantList
from app.models.quiz import Quiz, Question
from app.models.quiz_connection import QuizConnection
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
        await db.flush()  # Flush to get the quiz ID
        
        # Create questions
        for i, q_data in enumerate(quiz_data.questions):
            question = Question(
                quiz_id=quiz.id,  # Use quiz.id directly
                text=q_data.text,
                options=q_data.options,
                correct_answer=q_data.correctAnswer,
                score=q_data.score,
                order=i
            )
            db.add(question)
        
        await db.commit()
        
        # Get the quiz with questions using eager loading
        stmt = select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.id == quiz.id)
        result = await db.execute(stmt)
        quiz = result.scalar_one()
        
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

@router.get("/quizzes/{quiz_id}", response_model=QuizSchema)
async def get_quiz(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get quiz details by ID."""
    try:
        # Get quiz with questions
        stmt = select(Quiz).options(
            selectinload(Quiz.questions),
            selectinload(Quiz.created_by)
        ).where(Quiz.id == quiz_id)
        result = await db.execute(stmt)
        quiz = result.scalar_one_or_none()
        
        if not quiz:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NotFound",
                    "message": "Quiz not found",
                    "details": [{"field": "quiz_id", "message": f"Quiz with ID {quiz_id} does not exist"}]
                }
            )
        
        # Format response
        return {
            "id": quiz.id,
            "code": quiz.code,
            "createdAt": quiz.created_at,
            "createdBy": {
                "id": quiz.created_by.id,
                "email": quiz.created_by.email
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
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=400,
            detail={
                "error": "ValidationError",
                "message": "Failed to get quiz",
                "details": [{"field": "", "message": str(e)}]
            }
        )

@router.get("/quizzes/code/{quiz_code}", response_model=QuizSchema)
async def get_quiz_by_code(
    quiz_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get quiz details by code."""
    try:
        # Get quiz with questions
        stmt = select(Quiz).options(
            selectinload(Quiz.questions),
            selectinload(Quiz.created_by)
        ).where(Quiz.code == quiz_code)
        result = await db.execute(stmt)
        quiz = result.scalar_one_or_none()
        
        if not quiz:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NotFound",
                    "message": "Quiz not found",
                    "details": [{"field": "quiz_code", "message": f"Quiz with code {quiz_code} does not exist"}]
                }
            )
        
        # Format response
        return {
            "id": quiz.id,
            "code": quiz.code,
            "createdAt": quiz.created_at,
            "createdBy": {
                "id": quiz.created_by.id,
                "email": quiz.created_by.email
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
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=400,
            detail={
                "error": "ValidationError",
                "message": "Failed to get quiz",
                "details": [{"field": "", "message": str(e)}]
            }
        )

@router.get("/quizzes/{quiz_id}/participants", response_model=QuizParticipantList)
async def get_quiz_participants(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all participants of a quiz."""
    # Check if quiz exists
    result = await db.execute(
        select(Quiz).where(Quiz.id == quiz_id)
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Get all participants
    result = await db.execute(
        select(User.id, User.email, QuizConnection.connected_at)
        .join(QuizConnection, QuizConnection.user_id == User.id)
        .where(QuizConnection.quiz_id == quiz_id)
    )
    
    participants = []
    for user_id, email, connected_at in result.all():
        participants.append({
            "user_id": user_id,
            "email": email,
            "connected_at": connected_at
        })
    
    return {"participants": participants}
