from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base
import uuid

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(6), unique=True, index=True, nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(String(36), ForeignKey("users.id"))
    settings = Column(JSON)

    # Relationships
    created_by = relationship("User", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    quiz_id = Column(String(36), ForeignKey("quizzes.id"))
    text = Column(String(500), nullable=False)
    options = Column(JSON, nullable=False)  # Store as JSON array
    correct_answer = Column(Integer, nullable=False)
    score = Column(Integer, default=10)
    order = Column(Integer)

    # Relationships
    quiz = relationship("Quiz", back_populates="questions")
