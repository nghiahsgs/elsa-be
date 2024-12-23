from sqlalchemy import select, func
from app.models.quiz import Question
from app.models.quiz_score import QuizParticipantScore
from app.models.user import User
from app.models.quiz_connection import QuizConnection
from .models import QuizRoom, ParticipantInfo

async def handle_start_quiz(db, room: QuizRoom, quiz_id: int):
    # Initialize scores for all participants
    for user_id in room.participants.keys():
        existing_score = await db.execute(
            select(QuizParticipantScore)
            .where(
                QuizParticipantScore.quiz_id == quiz_id,
                QuizParticipantScore.user_id == int(user_id)
            )
        )
        if not existing_score.scalar_one_or_none():
            score = QuizParticipantScore(
                quiz_id=quiz_id,
                user_id=int(user_id),
                score=0,
                questions_answered=0
            )
            db.add(score)
    await db.commit()

    # Get initial leaderboard
    leaderboard = await get_leaderboard(db, quiz_id)

    # Broadcast start quiz event
    await room.broadcast({
        "type": "start_quiz_now",
        "quiz_id": str(quiz_id),
        "leaderboard": leaderboard
    })

async def handle_submit_answer(db, room: QuizRoom, quiz_id: int, user_id: int, question_id: int, answer: str):
    # Get correct answer
    result = await db.execute(
        select(func.json_extract(Question.correct_answer, '$'))
        .where(Question.id == question_id)
    )
    correct_answer = result.scalar_one()
    is_correct = answer == correct_answer

    if is_correct:
        # Get question score
        result = await db.execute(
            select(Question.score)
            .where(Question.id == question_id)
        )
        question_score = result.scalar_one()

        # Update score
        await db.execute(
            QuizParticipantScore.__table__.update()
            .where(
                QuizParticipantScore.quiz_id == quiz_id,
                QuizParticipantScore.user_id == user_id
            )
            .values(
                score=QuizParticipantScore.score + question_score,
                questions_answered=QuizParticipantScore.questions_answered + 1
            )
        )
    else:
        # Update questions answered for wrong answer
        await db.execute(
            QuizParticipantScore.__table__.update()
            .where(
                QuizParticipantScore.quiz_id == quiz_id,
                QuizParticipantScore.user_id == user_id
            )
            .values(
                questions_answered=QuizParticipantScore.questions_answered + 1
            )
        )
    await db.commit()

    # Get updated leaderboard and broadcast
    leaderboard = await get_leaderboard(db, quiz_id)
    await room.broadcast({
        "type": "leaderboard_update",
        "leaderboard": leaderboard,
        "answer_result": {
            "user_id": str(user_id),
            "question_id": question_id,
            "is_correct": is_correct
        }
    })

async def get_leaderboard(db, quiz_id: int):
    result = await db.execute(
        select(
            QuizParticipantScore.user_id,
            User.email,
            QuizParticipantScore.score,
            QuizParticipantScore.questions_answered
        )
        .join(User, User.id == QuizParticipantScore.user_id)
        .where(QuizParticipantScore.quiz_id == quiz_id)
        .order_by(QuizParticipantScore.score.desc())
    )
    
    return [{
        "user_id": str(user_id),
        "email": email,
        "score": score,
        "questions_answered": questions_answered
    } for user_id, email, score, questions_answered in result.all()]

async def get_room_participants(db, quiz_id: int, host_id: int) -> list[ParticipantInfo]:
    result = await db.execute(
        select(User)
        .join(QuizConnection, QuizConnection.user_id == User.id)
        .where(QuizConnection.quiz_id == quiz_id)
    )
    
    return [
        ParticipantInfo(
            id=str(user.id),
            email=user.email,
            is_host=user.id == host_id
        )
        for user in result.scalars().all()
    ]
