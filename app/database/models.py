"""SQLAlchemy models for the AI girlfriend bot."""

from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Boolean, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .connection import Base


class UserProfile(Base):
    """User profile model with loan balance and preferences."""
    
    __tablename__ = "user_profile"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    preference: Mapped[str] = mapped_column(Text, default="")
    loan_balance: Mapped[int] = mapped_column(Integer, default=10)
    last_reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    age_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )
    
    # Relationship to messages
    messages: Mapped[list["MessageLog"]] = relationship(
        "MessageLog", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<UserProfile(chat_id={self.chat_id}, loans={self.loan_balance}, verified={self.age_verified})>"
    
    def has_loans(self) -> bool:
        """Check if user has available loans."""
        return self.loan_balance > 0
    
    def deduct_loan(self) -> bool:
        """Deduct one loan from balance. Returns True if successful."""
        if self.loan_balance > 0:
            self.loan_balance -= 1
            return True
        return False
    
    def add_loans(self, amount: int) -> None:
        """Add loans to balance."""
        self.loan_balance += amount


class MessageLog(Base):
    """Message log model for chat history."""
    
    __tablename__ = "message_log"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger, 
        ForeignKey("user_profile.chat_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        index=True
    )
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationship to user
    user: Mapped["UserProfile"] = relationship("UserProfile", back_populates="messages")
    
    def __repr__(self) -> str:
        return f"<MessageLog(chat_id={self.chat_id}, role={self.role}, tokens={self.tokens_used})>"
    
    @classmethod
    def create_user_message(cls, chat_id: int, content: str, tokens_used: int = 0) -> "MessageLog":
        """Create a user message log entry."""
        return cls(
            chat_id=chat_id,
            role="user",
            content=content,
            tokens_used=tokens_used
        )
    
    @classmethod
    def create_assistant_message(cls, chat_id: int, content: str, tokens_used: int = 0) -> "MessageLog":
        """Create an assistant message log entry."""
        return cls(
            chat_id=chat_id,
            role="assistant", 
            content=content,
            tokens_used=tokens_used
        )
    
    @classmethod
    def create_system_message(cls, chat_id: int, content: str) -> "MessageLog":
        """Create a system message log entry."""
        return cls(
            chat_id=chat_id,
            role="system",
            content=content,
            tokens_used=0
        ) 