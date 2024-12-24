from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import delete, select, func
import logging
import traceback
from app.core.security import decode_access_token
from app.core.websocket import ConnectionManager
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.quiz import Quiz, Question
from app.models.quiz_connection import QuizConnection
from app.models.quiz_score import QuizParticipantScore
from sqlalchemy import func
from typing import Dict, Set

router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Store only active websocket connections
active_connections: Dict[str, Set[WebSocket]] = {}

async def broadcast_to_quiz(quiz_code: str, message: dict, exclude_ws: WebSocket = None):
    """Send message to all connections in a quiz except the sender"""
    if quiz_code in active_connections:
        for websocket in active_connections[quiz_code]:
            if websocket != exclude_ws:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to websocket: {str(e)}")

async def get_quiz_participants(db, quiz_id: int):
    """Get current quiz participants from DB"""
    result = await db.execute(
        select(User)
        .join(QuizConnection, QuizConnection.user_id == User.id)
        .where(QuizConnection.quiz_id == quiz_id)
    )
    return [
        {
            "id": str(user.id),
            "email": user.email
        }
        for user in result.scalars().all()
    ]

async def handle_start_quiz(db, quiz_id: int):
    """Initialize scores for all participants"""
    # Get current participants
    result = await db.execute(
        select(User.id)
        .join(QuizConnection, QuizConnection.user_id == User.id)
        .where(QuizConnection.quiz_id == quiz_id)
    )
    
    # Update quiz status to running
    quiz = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = quiz.scalar_one()
    quiz.status = 'running'
    
    # Initialize scores
    for (user_id,) in result.all():
        existing_score = await db.execute(
            select(QuizParticipantScore)
            .where(
                QuizParticipantScore.quiz_id == quiz_id,
                QuizParticipantScore.user_id == user_id
            )
        )
        if not existing_score.scalar_one_or_none():
            score = QuizParticipantScore(
                quiz_id=quiz_id,
                user_id=user_id,
                score=0
            )
            db.add(score)
    await db.commit()

async def get_leaderboard(db, quiz_id: int):
    """Get current leaderboard from DB"""
    result = await db.execute(
        select(
            QuizParticipantScore.user_id,
            User.email,
            QuizParticipantScore.score
        )
        .join(User, User.id == QuizParticipantScore.user_id)
        .where(QuizParticipantScore.quiz_id == quiz_id)
        .order_by(QuizParticipantScore.score.desc())
    )
    return [
        {
            "user_id": str(user_id),
            "email": email,
            "score": score
        }
        for user_id, email, score in result.all()
    ]

@router.websocket("/ws/quiz/{quiz_code}")
async def websocket_endpoint(websocket: WebSocket, quiz_code: str):
    db = None
    current_user = None
    quiz = None

    try:
        # Validate token
        token = websocket.query_params.get("token")
        await websocket.accept()

        if not token:
            logger.error("No token provided")
            await websocket.close(code=4001, reason="No authentication token provided")
            return

        try:
            payload = decode_access_token(token)
            email = payload.get("sub")
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            await websocket.close(code=4004, reason="Token validation failed")
            return

        # Initialize database session
        db = AsyncSessionLocal()

        # Get user and quiz
        result = await db.execute(
            select(User).where(User.email == email)
        )
        current_user = result.scalar_one_or_none()

        if not current_user:
            await websocket.close(code=4002, reason="User not found")
            return

        result = await db.execute(
            select(Quiz).where(Quiz.code == quiz_code)
        )
        quiz = result.scalar_one_or_none()

        if not quiz:
            await websocket.close(code=4003, reason="Quiz not found")
            return

        # Create connection record
        connection = QuizConnection(quiz_id=quiz.id, user_id=current_user.id)
        db.add(connection)
        await db.commit()

        # Add to active connections
        if quiz_code not in active_connections:
            active_connections[quiz_code] = set()
        active_connections[quiz_code].add(websocket)

        # Send initial participant list
        participants = await get_quiz_participants(db, quiz.id)
        await websocket.send_json({
            "type": "room_participants",
            "quiz": {
                "id": str(quiz.id),
                "code": quiz.code,
                "title": quiz.title,
                "description": quiz.description,
                "created_by": str(quiz.created_by_id)
            },
            "participants": participants
        })

        # Broadcast updated participant list to all connections
        await broadcast_to_quiz(quiz_code, {
            "type": "room_participants",
            "participants": participants
        }, websocket)

        # Main message loop
        while True:
            try:
                data = await websocket.receive_json()
                
                if data["type"] == "start_quiz":
                    await handle_start_quiz(db, quiz.id)
                    leaderboard = await get_leaderboard(db, quiz.id)
                    
                    # Format questions
                    questions = [
                        {
                            "id": q.id,
                            "text": q.text,
                            "options": q.options,
                            "correctAnswer": int(q.correct_answer),  # Ensure it's an integer
                            "score": q.score
                        }
                        for q in sorted(quiz.questions, key=lambda x: x.order if x.order is not None else 0)  # Handle None order values
                    ]
                    
                    await broadcast_to_quiz(quiz_code, {
                        "type": "start_quiz_now",
                        "quiz_id": str(quiz.id),
                        "leaderboard": leaderboard,
                        "questions": questions
                    })
                
                elif data["type"] == "end_quiz":
                    # Delete all participant scores for this quiz
                    await db.execute(
                        delete(QuizParticipantScore).where(
                            QuizParticipantScore.quiz_id == quiz.id
                        )
                    )
                    
                    # Update quiz status to idle
                    quiz.status = 'idle'
                    await db.commit()
                    
                    # Broadcast end_quiz_now to all connections
                    await broadcast_to_quiz(quiz_code, {
                        "type": "end_quiz_now",
                        "quiz_id": str(quiz.id)
                    })

                elif data["type"] == "submit_answer":
                    question_id = int(data["question_id"])
                    answer = int(data["answer"])  # Convert answer to int for comparison

                    # Verify answer
                    result = await db.execute(
                        select(Question.correct_answer)
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
                                QuizParticipantScore.quiz_id == quiz.id,
                                QuizParticipantScore.user_id == current_user.id
                            )
                            .values(
                                score=QuizParticipantScore.score + question_score
                            )
                        )
                    else:
                        # Wrong answer, no score update needed
                        pass
                    await db.commit()

                    # Get updated leaderboard and broadcast
                    leaderboard = await get_leaderboard(db, quiz.id)
                    await broadcast_to_quiz(quiz_code, {
                        "type": "leaderboard_update",
                        "leaderboard": leaderboard,
                        "answer_result": {
                            "user_id": str(current_user.id),
                            "question_id": question_id,
                            "is_correct": is_correct
                        }
                    })

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling message: {str(e)}")
                logger.error(traceback.format_exc())
                break

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        logger.error(traceback.format_exc())

    finally:
        print("Cleaning up...")
        if current_user and quiz and db:
            try:
                # Remove connection from DB
                await db.execute(
                    delete(QuizConnection).where(
                        QuizConnection.quiz_id == quiz.id,
                        QuizConnection.user_id == current_user.id
                    )
                )
                
                # Delete participant scores
                await db.execute(
                    delete(QuizParticipantScore).where(
                        QuizParticipantScore.user_id == current_user.id
                    )
                )
                
                await db.commit()

                # Remove from active connections
                if quiz_code in active_connections:
                    active_connections[quiz_code].discard(websocket)
                    if not active_connections[quiz_code]:
                        del active_connections[quiz_code]

                # Broadcast updated participant list
                participants = await get_quiz_participants(db, quiz.id)
                await broadcast_to_quiz(quiz_code, {
                    "type": "room_participants",
                    "participants": participants
                })
            except Exception as e:
                logger.error(f"Error cleaning up: {str(e)}")
                logger.error(traceback.format_exc())
            finally:
                await db.close()

        logger.info(f"Client disconnected from quiz {quiz_code}")
