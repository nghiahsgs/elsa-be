from typing import Dict, Set, Optional
from fastapi import WebSocket
from pydantic import BaseModel

class ParticipantInfo(BaseModel):
    id: str
    email: str
    is_host: bool

class QuizInfo(BaseModel):
    id: str
    code: str
    title: str
    description: str
    created_by: str

class QuizParticipant:
    def __init__(self, websocket: WebSocket, info: ParticipantInfo):
        self.websocket = websocket
        self.info = info

    async def send_message(self, message: dict):
        await self.websocket.send_json(message)

class QuizRoom:
    def __init__(self, quiz_info: QuizInfo):
        self.quiz_info = quiz_info
        self.participants: Dict[str, QuizParticipant] = {}

    def add_participant(self, participant: QuizParticipant):
        self.participants[participant.info.id] = participant

    def remove_participant(self, user_id: str):
        if user_id in self.participants:
            del self.participants[user_id]

    async def broadcast(self, message: dict, exclude_user_id: Optional[str] = None):
        for user_id, participant in self.participants.items():
            if exclude_user_id and user_id == exclude_user_id:
                continue
            await participant.send_message(message)

class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, QuizRoom] = {}

    def get_or_create_room(self, quiz_info: QuizInfo) -> QuizRoom:
        if quiz_info.code not in self.rooms:
            self.rooms[quiz_info.code] = QuizRoom(quiz_info)
        return self.rooms[quiz_info.code]

    def remove_room(self, quiz_code: str):
        if quiz_code in self.rooms:
            del self.rooms[quiz_code]
