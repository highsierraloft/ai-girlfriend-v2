"""User service for managing user profiles and loan system."""

import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from inspect import iscoroutine

from app.database.models import UserProfile
from app.config.settings import settings

logger = logging.getLogger(__name__)


# Helper to await AsyncMock coroutines in tests transparently
async def _maybe_await(value):
    """Await value if it's a coroutine (helpful when using AsyncMock)."""
    if iscoroutine(value):
        return await value
    return value


class UserService:
    """Service for managing user profiles and loan system."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def get_or_create_user(self, chat_id: int) -> UserProfile:
        """Get existing user or create new one with default settings."""
        # Try to get existing user
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.chat_id == chat_id)
        )
        user = await _maybe_await(result.scalar_one_or_none())
        
        if user is None:
            # Create new user with default settings
            user = UserProfile(
                chat_id=chat_id,
                loan_balance=settings.free_daily_loans,
                age_verified=False,
                preference="",
                created_at=datetime.utcnow(),
                last_reset_at=datetime.utcnow()
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info(f"Created new user profile for chat_id: {chat_id}")
        
        return user
    
    async def get_user(self, chat_id: int) -> Optional[UserProfile]:
        """Get user profile by chat_id."""
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.chat_id == chat_id)
        )
        return await _maybe_await(result.scalar_one_or_none())
    
    async def verify_age(self, chat_id: int) -> bool:
        """Mark user as age-verified."""
        user = await self.get_or_create_user(chat_id)
        user.age_verified = True
        await self.db.commit()
        logger.info(f"User {chat_id} verified age")
        return True
    
    async def is_age_verified(self, chat_id: int) -> bool:
        """Check if user is age-verified."""
        user = await self.get_user(chat_id)
        return user.age_verified if user else False
    
    async def check_and_deduct_loan(self, chat_id: int) -> bool:
        """Check if user has loans and deduct one. Returns True if successful."""
        user = await self.get_or_create_user(chat_id)
        
        if user.deduct_loan():
            await self.db.commit()
            logger.info(f"Deducted loan for user {chat_id}. Remaining: {user.loan_balance}")
            return True
        else:
            logger.info(f"User {chat_id} has no loans remaining")
            return False
    
    async def get_loan_balance(self, chat_id: int) -> int:
        """Get user's current loan balance."""
        user = await self.get_or_create_user(chat_id)
        return user.loan_balance
    
    async def add_loans(self, chat_id: int, amount: int) -> int:
        """Add loans to user's balance. Returns new balance."""
        user = await self.get_or_create_user(chat_id)
        user.add_loans(amount)
        await self.db.commit()
        logger.info(f"Added {amount} loans to user {chat_id}. New balance: {user.loan_balance}")
        return user.loan_balance
    
    async def reset_chat_history(self, chat_id: int) -> bool:
        """Reset user's chat history timestamp."""
        user = await self.get_or_create_user(chat_id)
        user.last_reset_at = datetime.utcnow()
        await self.db.commit()
        logger.info(f"Reset chat history for user {chat_id}")
        return True
    
    async def update_preferences(self, chat_id: int, preferences: str) -> bool:
        """Update user's preferences."""
        user = await self.get_or_create_user(chat_id)
        user.preference = preferences
        await self.db.commit()
        logger.info(f"Updated preferences for user {chat_id}")
        return True
    
    async def get_preferences(self, chat_id: int) -> str:
        """Get user's preferences."""
        user = await self.get_or_create_user(chat_id)
        return user.preference or ""
    
    async def daily_loan_refill(self) -> int:
        """Refill loans for all users. Returns number of users updated."""
        from sqlalchemy import update
        
        result = await self.db.execute(
            update(UserProfile).values(
                loan_balance=UserProfile.loan_balance + settings.free_daily_loans
            )
        )
        await self.db.commit()
        
        affected_rows = result.rowcount
        logger.info(f"Daily loan refill completed. Updated {affected_rows} users")
        return affected_rows 