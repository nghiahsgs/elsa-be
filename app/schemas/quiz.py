from pydantic import BaseModel, constr, conlist, validator, Field
from typing import List, Optional
from datetime import datetime

class QuizSettings(BaseModel):
    timeLimit: int = Field(30, ge=10, le=300)
    shuffleQuestions: bool = True

    class Config:
        orm_mode = True

class QuestionCreate(BaseModel):
    text: constr(min_length=1, max_length=500)
    options: conlist(str, min_items=4, max_items=4)
    correctAnswer: int = Field(..., ge=0, le=3)
    score: int = Field(10, ge=1)

    @validator('options')
    def validate_options(cls, v):
        if not all(isinstance(option, str) and len(option.strip()) > 0 for option in v):
            raise ValueError('All options must be non-empty strings')
        return v

class QuizCreate(BaseModel):
    title: constr(min_length=3, max_length=100)
    description: Optional[str] = None
    questions: conlist(QuestionCreate, min_items=1)
    settings: Optional[QuizSettings] = QuizSettings()

class UserInfo(BaseModel):
    id: str
    email: str

    class Config:
        orm_mode = True

class Question(QuestionCreate):
    id: str

    class Config:
        orm_mode = True

class Quiz(BaseModel):
    id: str
    code: str
    createdAt: datetime
    createdBy: UserInfo
    title: str
    description: Optional[str]
    questions: List[Question]
    settings: QuizSettings

    class Config:
        orm_mode = True
