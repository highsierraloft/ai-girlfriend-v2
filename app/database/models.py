"""SQLAlchemy models for the AI girlfriend bot."""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import BigInteger, Boolean, Integer, String, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .connection import Base


class UserProfile(Base):
    """User profile model with complete Telegram user data and bot-specific fields."""
    
    __tablename__ = "user_profile"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    
    # Telegram User fields
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    added_to_attachment_menu: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Bot-specific fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    preference: Mapped[str] = mapped_column(Text, default="")  # Current active preference
    loan_balance: Mapped[int] = mapped_column(Integer, default=10)
    last_reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    age_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )
    
    # Additional metadata
    first_interaction_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_interaction_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    total_messages_sent: Mapped[int] = mapped_column(Integer, default=0)
    total_loans_purchased: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    messages: Mapped[List["MessageLog"]] = relationship(
        "MessageLog", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )
    preference_history: Mapped[List["PreferenceHistory"]] = relationship(
        "PreferenceHistory",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    stats: Mapped[List["UserStats"]] = relationship(
        "UserStats",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<UserProfile(chat_id={self.chat_id}, name='{self.full_name}', loans={self.loan_balance})>"
    
    @property
    def full_name(self) -> str:
        """Get user's full name (first_name + last_name if available)."""
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name
    
    @property
    def display_name(self) -> str:
        """Get user's display name (username if available, otherwise full_name)."""
        if self.username:
            return f"@{self.username}"
        return self.full_name
    
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
        if self.total_loans_purchased is None:
            self.total_loans_purchased = 0
        self.total_loans_purchased += amount
    
    def update_from_telegram_user(self, telegram_user) -> None:
        """Update profile data from Telegram User object."""
        self.user_id = telegram_user.id
        self.is_bot = telegram_user.is_bot
        self.first_name = telegram_user.first_name
        self.last_name = telegram_user.last_name
        self.username = telegram_user.username
        self.language_code = telegram_user.language_code
        self.is_premium = getattr(telegram_user, 'is_premium', False)
        self.added_to_attachment_menu = getattr(telegram_user, 'added_to_attachment_menu', False)
        self.last_interaction_at = func.now()


class PreferenceHistory(Base):
    """History of all user preference changes with timestamps."""
    
    __tablename__ = "preference_history"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.chat_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    preference_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    change_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Relationship
    user: Mapped["UserProfile"] = relationship("UserProfile", back_populates="preference_history")
    
    def __repr__(self) -> str:
        return f"<PreferenceHistory(chat_id={self.chat_id}, active={self.is_active}, reason='{self.change_reason}')>"
    
    @classmethod
    def create_new_preference(
        cls, 
        chat_id: int, 
        preference_text: str, 
        change_reason: str = "user_edit"
    ) -> "PreferenceHistory":
        """Create a new preference entry."""
        return cls(
            chat_id=chat_id,
            preference_text=preference_text,
            change_reason=change_reason,
            is_active=True
        )


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
    message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    
    # Relationship to user
    user: Mapped["UserProfile"] = relationship("UserProfile", back_populates="messages")
    
    def __repr__(self) -> str:
        return f"<MessageLog(chat_id={self.chat_id}, role={self.role}, tokens={self.tokens_used})>"
    
    @classmethod
    def create_user_message(
        cls, 
        chat_id: int, 
        content: str, 
        tokens_used: int = 0,
        message_id: Optional[int] = None
    ) -> "MessageLog":
        """Create a user message log entry."""
        return cls(
            chat_id=chat_id,
            role="user",
            content=content,
            tokens_used=tokens_used,
            message_id=message_id
        )
    
    @classmethod
    def create_assistant_message(
        cls, 
        chat_id: int, 
        content: str, 
        tokens_used: int = 0,
        message_id: Optional[int] = None
    ) -> "MessageLog":
        """Create an assistant message log entry."""
        return cls(
            chat_id=chat_id,
            role="assistant", 
            content=content,
            tokens_used=tokens_used,
            message_id=message_id
        )
    
    @classmethod
    def create_system_message(
        cls, 
        chat_id: int, 
        content: str,
        message_id: Optional[int] = None
    ) -> "MessageLog":
        """Create a system message log entry."""
        return cls(
            chat_id=chat_id,
            role="system",
            content=content,
            tokens_used=0,
            message_id=message_id
        )


class UserStats(Base):
    """Daily user interaction statistics."""
    
    __tablename__ = "user_stats"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profile.chat_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    stat_date: Mapped[date] = mapped_column(Date, server_default=func.current_date(), index=True)
    messages_sent: Mapped[int] = mapped_column(Integer, default=0)
    loans_used: Mapped[int] = mapped_column(Integer, default=0)
    tokens_consumed: Mapped[int] = mapped_column(Integer, default=0)
    session_duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationship
    user: Mapped["UserProfile"] = relationship("UserProfile", back_populates="stats")
    
    def __repr__(self) -> str:
        return f"<UserStats(chat_id={self.chat_id}, date={self.stat_date}, messages={self.messages_sent})>"
    
    def increment_message(self) -> None:
        """Increment message count."""
        if self.messages_sent is None:
            self.messages_sent = 0
        self.messages_sent += 1
    
    def add_tokens(self, tokens: int) -> None:
        """Add tokens to consumed count."""
        if self.tokens_consumed is None:
            self.tokens_consumed = 0
        self.tokens_consumed += tokens
    
    def use_loan(self) -> None:
        """Increment loans used count."""
        if self.loans_used is None:
            self.loans_used = 0
        self.loans_used += 1 