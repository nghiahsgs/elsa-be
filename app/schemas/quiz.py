from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class QuestionBase(BaseModel):
    text: str
    options: List[str]
    correctAnswer: int
    score: int = 10

class QuestionCreate(QuestionBase):
    pass

class Question(QuestionBase):
    id: int

    class Config:
        from_attributes = True

class QuizSettings(BaseModel):
    timeLimit: int
    shuffleQuestions: bool

class QuizBase(BaseModel):
    title: str
    description: Optional[str] = None
    settings: QuizSettings

class QuizCreate(QuizBase):
    questions: List[QuestionCreate]

class UserInfo(BaseModel):
    id: str
    email: str

class Quiz(QuizBase):
    id: int
    code: str
    createdAt: datetime
    createdBy: UserInfo
    questions: List[Question]

    class Config:
        from_attributes = True
