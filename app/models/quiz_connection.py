from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.db.base_class import Base

class QuizConnection(Base):
    __tablename__ = "quiz_connections"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    connected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    class Config:
        orm_mode = True
