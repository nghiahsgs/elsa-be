from pydantic import BaseModel
from datetime import datetime
from typing import List

class QuizParticipant(BaseModel):
    user_id: int
    email: str
    connected_at: datetime
    
    class Config:
        from_attributes = True

class QuizParticipantList(BaseModel):
    participants: List[QuizParticipant]
