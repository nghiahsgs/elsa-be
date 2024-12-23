from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import delete
import logging
import traceback
from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.quiz import Quiz
from app.models.quiz_connection import QuizConnection
from .models import RoomManager, QuizParticipant, ParticipantInfo, QuizInfo
from .handlers import (
    handle_start_quiz,
    handle_submit_answer,
    get_room_participants
)

router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

room_manager = RoomManager()

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
            user_id = int(payload.get("sub"))
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            await websocket.close(code=4004, reason="Token validation failed")
            return

        # Initialize database session
        db = AsyncSessionLocal()

        # Get user and quiz
        current_user = await db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()

        if not current_user:
            await websocket.close(code=4002, reason="User not found")
            return

        quiz = await db.execute(
            select(Quiz).where(Quiz.code == quiz_code)
        ).scalar_one_or_none()

        if not quiz:
            await websocket.close(code=4003, reason="Quiz not found")
            return

        # Create connection record
        connection = QuizConnection(quiz_id=quiz.id, user_id=current_user.id)
        db.add(connection)
        await db.commit()

        # Setup room and participant
        quiz_info = QuizInfo(
            id=str(quiz.id),
            code=quiz.code,
            title=quiz.title,
            description=quiz.description,
            created_by=str(quiz.created_by_id)
        )
        
        participant_info = ParticipantInfo(
            id=str(current_user.id),
            email=current_user.email,
            is_host=current_user.id == quiz.created_by_id
        )

        room = room_manager.get_or_create_room(quiz_info)
        participant = QuizParticipant(websocket, participant_info)
        room.add_participant(participant)

        # Send initial participant list
        participants = await get_room_participants(db, quiz.id, quiz.created_by_id)
        await participant.send_message({
            "type": "room_participants",
            "quiz": quiz_info.dict(),
            "participants": [p.dict() for p in participants]
        })

        # Main message loop
        while True:
            try:
                data = await websocket.receive_json()
                
                if data["type"] == "start_quiz":
                    await handle_start_quiz(db, room, quiz.id)
                
                elif data["type"] == "submit_answer":
                    await handle_submit_answer(
                        db, room, quiz.id,
                        current_user.id,
                        int(data["question_id"]),
                        data["answer"]
                    )

                # Update participant list after each action
                participants = await get_room_participants(db, quiz.id, quiz.created_by_id)
                await room.broadcast({
                    "type": "room_participants",
                    "quiz": quiz_info.dict(),
                    "participants": [p.dict() for p in participants]
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
        if current_user and quiz and db:
            try:
                # Remove connection from DB
                await db.execute(
                    delete(QuizConnection).where(
                        QuizConnection.quiz_id == quiz.id,
                        QuizConnection.user_id == current_user.id
                    )
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Error removing connection: {str(e)}")
                logger.error(traceback.format_exc())
            finally:
                await db.close()

        if quiz_code in room_manager.rooms:
            room = room_manager.rooms[quiz_code]
            room.remove_participant(str(current_user.id))
            if not room.participants:
                room_manager.remove_room(quiz_code)
