from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from app.core.websocket import manager
from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
import logging
import traceback
from sqlalchemy import select, delete, func
from app.models.user import User
from app.models.quiz import Quiz, Question
from app.models.quiz_connection import QuizConnection
from app.models.quiz_score import QuizParticipantScore

router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

async def broadcast_to_room(quiz_code: str, message: dict):
    """Helper function to broadcast message to all connections in a room"""
    connections = manager.active_connections.get(quiz_code, set())
    for connection in connections:
        await connection.send_json(message)

async def get_leaderboard(db, quiz_id: int):
    """Helper function to get current leaderboard"""
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
    leaderboard = []
    for user_id, email, score, questions_answered in result.all():
        leaderboard.append({
            "user_id": str(user_id),
            "email": email,
            "score": score,
            "questions_answered": questions_answered
        })
    return leaderboard

@router.websocket("/ws/quiz/{quiz_code}")
async def websocket_endpoint(websocket: WebSocket, quiz_code: str):
    """WebSocket endpoint for quiz room."""
    db = None
    print("WebSocket endpoint called")
    try:
        # Get token from query parameters
        token = websocket.query_params.get("token")
        logger.debug(f"Received WebSocket connection request for quiz {quiz_code}")
        
        # Accept the connection first to avoid connection timeout
        await websocket.accept()
        logger.debug("WebSocket connection accepted")

        if not token:
            logger.error("No token provided")
            await websocket.close(code=4001, reason="No authentication token provided")
            return

        # Verify token and get user
        try:
            logger.debug(f"Decoding token: {token}")
            try:
                payload = decode_access_token(token)
                logger.debug(f"Token decoded successfully. User ID: {payload.get('sub')}")
            except Exception as e:
                logger.error(f"Token validation failed: {str(e)}")
                logger.error(f"Stack trace: {traceback.format_exc()}")
                await websocket.close(code=4004, reason="Token validation failed")
                return
            
            db = AsyncSessionLocal()
            logger.debug("Database session created")
            
            # Get user
            logger.debug("Fetching user from database...")
            result = await db.execute(
                select(User).where(User.id == int(payload.get("sub")))
            )
            current_user = result.scalar_one_or_none()
            if not current_user:
                logger.error(f"User with ID {payload.get('sub')} not found")
                await websocket.close(code=4002, reason="User not found")
                return
            logger.debug(f"User found: {current_user.email}")

            # Get quiz
            logger.debug(f"Fetching quiz with code {quiz_code}...")
            result = await db.execute(
                select(Quiz).where(Quiz.code == quiz_code)
            )
            quiz = result.scalar_one_or_none()
            if not quiz:
                logger.error(f"Quiz with code {quiz_code} not found")
                await websocket.close(code=4003, reason="Quiz not found")
                return
            logger.debug(f"Quiz found: {quiz.title}")

            # Create connection record in DB
            logger.debug("Creating connection record in database...")
            connection = QuizConnection(
                quiz_id=quiz.id,
                user_id=current_user.id
            )
            db.add(connection)
            await db.commit()
            logger.debug("Connection record created successfully")

            # User info for the connection
            user_info = {
                "id": str(current_user.id),
                "email": current_user.email,
                "is_host": current_user.id == quiz.created_by_id
            }

            # Connect to room (still keep in memory for real-time communication)
            logger.debug("Adding connection to memory manager...")
            await manager.connect(websocket, quiz_code, user_info)
            logger.debug("Connection added to memory manager")

            # Get all participants from DB
            logger.debug("Fetching participants from database...")
            result = await db.execute(
                select(User)
                .join(QuizConnection, QuizConnection.user_id == User.id)
                .where(QuizConnection.quiz_id == quiz.id)
            )
            participants = []
            for user in result.scalars().all():
                participants.append({
                    "id": str(user.id),
                    "email": user.email,
                    "is_host": user.id == quiz.created_by_id
                })
            logger.debug(f"Found {len(participants)} participants")

            # Send initial participant list
            logger.debug("Sending initial participant list...")
            initial_message = {
                "type": "room_participants",
                "quiz": {
                    "id": str(quiz.id),
                    "code": quiz.code,
                    "title": quiz.title,
                    "description": quiz.description,
                    "created_by": str(quiz.created_by_id)
                },
                "participants": participants
            }
            await websocket.send_json(initial_message)
            logger.debug("Initial participant list sent")

            # Keep connection alive and handle messages
            while True:
                try:
                    data = await websocket.receive_json()
                    logger.debug(f"Received message from {current_user.email}: {data}")
                    
                    if data["type"] == "start_quiz":
                        # Initialize scores for all participants
                        participants_query = await db.execute(
                            select(User.id)
                            .join(QuizConnection, QuizConnection.user_id == User.id)
                            .where(QuizConnection.quiz_id == quiz.id)
                        )
                        for (user_id,) in participants_query.all():
                            # Check if score record already exists
                            existing_score = await db.execute(
                                select(QuizParticipantScore)
                                .where(
                                    QuizParticipantScore.quiz_id == quiz.id,
                                    QuizParticipantScore.user_id == user_id
                                )
                            )
                            if not existing_score.scalar_one_or_none():
                                score = QuizParticipantScore(
                                    quiz_id=quiz.id,
                                    user_id=user_id,
                                    score=0,
                                    questions_answered=0
                                )
                                db.add(score)
                        await db.commit()

                        # Get initial leaderboard
                        leaderboard = await get_leaderboard(db, quiz.id)

                        # Broadcast start quiz event to all participants
                        await broadcast_to_room(quiz_code, {
                            "type": "start_quiz_now",
                            "quiz_id": str(quiz.id),
                            "leaderboard": leaderboard
                        })

                    elif data["type"] == "submit_answer":
                        question_id = int(data["question_id"])
                        answer = data["answer"]
                        
                        # Get question and verify answer
                        result = await db.execute(
                            select(func.json_extract(Question.correct_answer, '$'))
                            .where(Question.id == question_id)
                        )
                        correct_answer = result.scalar_one()
                        
                        # Update score if answer is correct
                        if answer == correct_answer:
                            result = await db.execute(
                                select(Question.score)
                                .where(Question.id == question_id)
                            )
                            question_score = result.scalar_one()
                            
                            # Update participant's score
                            await db.execute(
                                QuizParticipantScore.__table__.update()
                                .where(
                                    QuizParticipantScore.quiz_id == quiz.id,
                                    QuizParticipantScore.user_id == current_user.id
                                )
                                .values(
                                    score=QuizParticipantScore.score + question_score,
                                    questions_answered=QuizParticipantScore.questions_answered + 1
                                )
                            )
                        else:
                            # Even for wrong answers, increment questions_answered
                            await db.execute(
                                QuizParticipantScore.__table__.update()
                                .where(
                                    QuizParticipantScore.quiz_id == quiz.id,
                                    QuizParticipantScore.user_id == current_user.id
                                )
                                .values(
                                    questions_answered=QuizParticipantScore.questions_answered + 1
                                )
                            )
                        await db.commit()

                        # Get updated leaderboard
                        leaderboard = await get_leaderboard(db, quiz.id)
                        
                        # Broadcast leaderboard update and answer result
                        await broadcast_to_room(quiz_code, {
                            "type": "leaderboard_update",
                            "leaderboard": leaderboard,
                            "answer_result": {
                                "user_id": str(current_user.id),
                                "question_id": question_id,
                                "is_correct": answer == correct_answer
                            }
                        })

                    # Get updated participant list from DB
                    result = await db.execute(
                        select(User)
                        .join(QuizConnection, QuizConnection.user_id == User.id)
                        .where(QuizConnection.quiz_id == quiz.id)
                    )
                    participants = []
                    for user in result.scalars().all():
                        participants.append({
                            "id": str(user.id),
                            "email": user.email,
                            "is_host": user.id == quiz.created_by_id
                        })

                    # Send updated participant list
                    update_message = {
                        "type": "room_participants",
                        "quiz": {
                            "id": str(quiz.id),
                            "code": quiz.code,
                            "title": quiz.title,
                            "description": quiz.description,
                            "created_by": str(quiz.created_by_id)
                        },
                        "participants": participants
                    }
                    await websocket.send_json(update_message)
                    logger.debug("Updated participant list sent")

                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected for user {current_user.email}")
                    break
                except Exception as e:
                    logger.error(f"Error handling message: {str(e)}")
                    logger.error(f"Stack trace: {traceback.format_exc()}")
                    break

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            await websocket.close(code=4004, reason="Authentication failed")
            return

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
    finally:
        if db:
            # Remove connection from DB
            try:
                logger.debug("Removing connection from database...")
                await db.execute(
                    delete(QuizConnection).where(
                        QuizConnection.quiz_id == quiz.id,
                        QuizConnection.user_id == current_user.id
                    )
                )
                await db.commit()
                logger.debug("Connection removed from database")
            except Exception as e:
                logger.error(f"Error removing connection from DB: {str(e)}")
                logger.error(f"Stack trace: {traceback.format_exc()}")
            finally:
                await db.close()
                logger.debug("Database session closed")
                
        manager.disconnect(websocket)
        logger.info(f"Client disconnected from quiz {quiz_code}")
