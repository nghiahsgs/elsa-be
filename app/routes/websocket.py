from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from app.core.websocket import manager
from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
import logging
from sqlalchemy import select, delete
from app.models.user import User
from app.models.quiz import Quiz
from app.models.quiz_connection import QuizConnection
import traceback

router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set to DEBUG level

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
