from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from app.core.websocket import manager
from app.core.security import decode_access_token
from app.crud.crud_user import user as crud_user
from app.crud.crud_quiz import quiz as crud_quiz
from app.db.session import SessionLocal
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/quiz/{quiz_code}")
async def websocket_endpoint(websocket: WebSocket, quiz_code: str):
    """WebSocket endpoint for quiz room."""
    try:
        # Get token from query parameters
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=4001, reason="No authentication token provided")
            return

        # Verify token and get user
        try:
            payload = decode_access_token(token)
            db = SessionLocal()
            current_user = crud_user.get(db, id=payload.get("sub"))
            if not current_user:
                await websocket.close(code=4002, reason="User not found")
                return

            # Get quiz and verify it exists
            quiz = crud_quiz.get_by_code(db, code=quiz_code)
            if not quiz:
                await websocket.close(code=4003, reason="Quiz not found")
                return

            # Accept the connection
            await websocket.accept()
            logger.info(f"WebSocket connection accepted for quiz {quiz_code} by user {current_user.email}")

            # User info for the connection
            user_info = {
                "id": str(current_user.id),
                "email": current_user.email,
                "full_name": current_user.full_name
            }

            # Connect to room
            await manager.connect(websocket, quiz_code, user_info)

            # Get all participants in the quiz
            participants = []
            for ws in manager.active_connections.get(quiz_code, set()):
                if ws in manager.connection_info:
                    participant_info = manager.connection_info[ws][1]
                    participants.append(participant_info)

            # Send initial participant list
            await websocket.send_json({
                "type": "room_participants",
                "quiz": {
                    "id": str(quiz.id),
                    "code": quiz.code,
                    "title": quiz.title,
                    "description": quiz.description,
                    "created_by": str(quiz.created_by)
                },
                "participants": participants
            })

            # Keep connection alive and handle messages
            while True:
                try:
                    data = await websocket.receive_json()
                    logger.info(f"Received message from {current_user.email}: {data}")
                    
                    # Get updated participant list
                    participants = []
                    for ws in manager.active_connections.get(quiz_code, set()):
                        if ws in manager.connection_info:
                            participant_info = manager.connection_info[ws][1]
                            participants.append(participant_info)

                    # Send updated participant list
                    await websocket.send_json({
                        "type": "room_participants",
                        "quiz": {
                            "id": str(quiz.id),
                            "code": quiz.code,
                            "title": quiz.title,
                            "description": quiz.description,
                            "created_by": str(quiz.created_by)
                        },
                        "participants": participants
                    })

                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error handling message: {str(e)}")
                    break

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            await websocket.close(code=4004, reason="Authentication failed")
            return
        finally:
            db.close()

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        manager.disconnect(websocket)
        logger.info(f"Client disconnected from quiz {quiz_code}")
