"""User service for managing user profiles and preferences."""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from app.database.models import UserProfile, PreferenceHistory, UserStats
from app.database.connection import get_database

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing user profiles and preferences."""
    
    @staticmethod
    async def get_or_create_user(telegram_user, chat_id: int) -> UserProfile:
        """Get existing user or create new one from Telegram user data."""
        async for session in get_database():
            # Try to get existing user
            stmt = select(UserProfile).where(UserProfile.chat_id == chat_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user:
                # Update existing user with latest Telegram data
                user.update_from_telegram_user(telegram_user)
                await session.commit()
                logger.info(f"Updated existing user profile for chat_id={chat_id}")
            else:
                # Create new user
                user = UserProfile(
                    chat_id=chat_id,
                    user_id=telegram_user.id,
                    is_bot=telegram_user.is_bot,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name,
                    username=telegram_user.username,
                    language_code=telegram_user.language_code,
                    is_premium=getattr(telegram_user, 'is_premium', False),
                    added_to_attachment_menu=getattr(telegram_user, 'added_to_attachment_menu', False)
                )
                session.add(user)
                await session.commit()
                logger.info(f"Created new user profile for chat_id={chat_id}, user_id={telegram_user.id}")
            
            return user
    
    @staticmethod
    async def get_user_by_chat_id(chat_id: int) -> Optional[UserProfile]:
        """Get user profile by chat ID."""
        async for session in get_database():
            stmt = select(UserProfile).where(UserProfile.chat_id == chat_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_with_preferences(chat_id: int) -> Optional[UserProfile]:
        """Get user profile with preference history loaded."""
        async for session in get_database():
            stmt = (
                select(UserProfile)
                .options(selectinload(UserProfile.preference_history))
                .where(UserProfile.chat_id == chat_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    @staticmethod
    async def update_user_preference(
        chat_id: int, 
        preference_text: str, 
        change_reason: str = "user_edit"
    ) -> bool:
        """Update user preference and create history entry."""
        async for session in get_database():
            # Check if user exists
            user = await UserService.get_user_by_chat_id(chat_id)
            if not user:
                logger.error(f"User not found for chat_id={chat_id}")
                return False
            
            # Create new preference history entry
            preference_history = PreferenceHistory.create_new_preference(
                chat_id=chat_id,
                preference_text=preference_text,
                change_reason=change_reason
            )
            session.add(preference_history)
            
            try:
                await session.commit()
                logger.info(f"Updated preference for chat_id={chat_id}, reason={change_reason}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update preference for chat_id={chat_id}: {e}")
                return False
    
    @staticmethod
    async def clear_user_preference(chat_id: int) -> bool:
        """Clear user preference by setting empty text."""
        return await UserService.update_user_preference(
            chat_id=chat_id,
            preference_text="",
            change_reason="user_clear"
        )
    
    @staticmethod
    async def get_user_preference_history(chat_id: int, limit: int = 10) -> List[PreferenceHistory]:
        """Get user's preference change history."""
        async for session in get_database():
            stmt = (
                select(PreferenceHistory)
                .where(PreferenceHistory.chat_id == chat_id)
                .order_by(PreferenceHistory.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    @staticmethod
    async def get_current_preference(chat_id: int) -> Optional[str]:
        """Get user's current active preference."""
        async for session in get_database():
            stmt = (
                select(PreferenceHistory.preference_text)
                .where(
                    PreferenceHistory.chat_id == chat_id,
                    PreferenceHistory.is_active == True
                )
            )
            result = await session.execute(stmt)
            preference = result.scalar_one_or_none()
            return preference if preference else ""
    
    @staticmethod
    async def verify_user_age(chat_id: int) -> bool:
        """Mark user as age verified."""
        async for session in get_database():
            stmt = (
                update(UserProfile)
                .where(UserProfile.chat_id == chat_id)
                .values(age_verified=True)
            )
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                logger.info(f"Age verified for chat_id={chat_id}")
                return True
            else:
                logger.error(f"Failed to verify age for chat_id={chat_id} - user not found")
                return False
    
    @staticmethod
    async def _get_or_create_today_stats(session, chat_id: int) -> UserStats:
        """Get or create today's stats entry for user."""
        from datetime import date
        today = date.today()
        
        # Try to get existing stats
        stmt = select(UserStats).where(
            UserStats.chat_id == chat_id,
            UserStats.stat_date == today
        )
        result = await session.execute(stmt)
        stats = result.scalar_one_or_none()
        
        if not stats:
            # Create new stats entry with explicit defaults
            stats = UserStats(
                chat_id=chat_id, 
                stat_date=today,
                messages_sent=0,
                loans_used=0,
                tokens_consumed=0,
                session_duration_minutes=0
            )
            session.add(stats)
        
        return stats

    @staticmethod
    async def deduct_loan(chat_id: int) -> bool:
        """Deduct one loan from user balance."""
        try:
            async for session in get_database():
                # Get user
                stmt = select(UserProfile).where(UserProfile.chat_id == chat_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if not user or not user.has_loans():
                    return False
                
                # Deduct loan
                user.deduct_loan()
                
                # Update daily stats
                today_stats = await UserService._get_or_create_today_stats(session, chat_id)
                today_stats.use_loan()
                
                await session.commit()
                logger.info(f"Deducted loan for chat_id={chat_id}, remaining={user.loan_balance}")
                return True
        except Exception as e:
            logger.error(f"Error deducting loan for chat_id={chat_id}: {e}")
            return False
    
    @staticmethod
    async def add_loans(chat_id: int, amount: int) -> bool:
        """Add loans to user balance."""
        async for session in get_database():
            stmt = select(UserProfile).where(UserProfile.chat_id == chat_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                logger.error(f"User not found for chat_id={chat_id}")
                return False
            
            user.add_loans(amount)
            await session.commit()
            logger.info(f"Added {amount} loans for chat_id={chat_id}, new balance={user.loan_balance}")
            return True
    
    @staticmethod
    async def reset_chat_history(chat_id: int) -> bool:
        """Reset user's chat history timestamp."""
        async for session in get_database():
            stmt = (
                update(UserProfile)
                .where(UserProfile.chat_id == chat_id)
                .values(last_reset_at=datetime.now(timezone.utc))
            )
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                logger.info(f"Reset chat history for chat_id={chat_id}")
                return True
            else:
                logger.error(f"Failed to reset chat history for chat_id={chat_id} - user not found")
                return False
    
    @staticmethod
    async def get_user_stats(chat_id: int, days: int = 7) -> List[UserStats]:
        """Get user statistics for the last N days."""
        async for session in get_database():
            stmt = (
                select(UserStats)
                .where(UserStats.chat_id == chat_id)
                .order_by(UserStats.stat_date.desc())
                .limit(days)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    @staticmethod
    async def update_user_interaction(chat_id: int, tokens_used: int = 0) -> None:
        """Update user interaction statistics."""
        async for session in get_database():
            # Update daily stats
            today_stats = await UserService._get_or_create_today_stats(session, chat_id)
            today_stats.increment_message()
            if tokens_used > 0:
                today_stats.add_tokens(tokens_used)
            
            await session.commit()

    @staticmethod
    async def increment_user_message_count(chat_id: int) -> None:
        """Increment total_messages_sent counter for user."""
        try:
            async for session in get_database():
                # Update user's total message count and last interaction time
                stmt = (
                    update(UserProfile)
                    .where(UserProfile.chat_id == chat_id)
                    .values(
                        total_messages_sent=UserProfile.total_messages_sent + 1,
                        last_interaction_at=datetime.now(timezone.utc)
                    )
                )
                result = await session.execute(stmt)
                await session.commit()
                
                if result.rowcount > 0:
                    logger.info(f"Incremented message count for chat_id={chat_id}")
                else:
                    logger.warning(f"User not found for chat_id={chat_id} when incrementing message count")
        except Exception as e:
            logger.error(f"Error incrementing message count for chat_id={chat_id}: {e}")
    
    @staticmethod
    async def get_users_by_language(language_code: str, limit: int = 100) -> List[UserProfile]:
        """Get users by language code for analytics."""
        async for session in get_database():
            stmt = (
                select(UserProfile)
                .where(UserProfile.language_code == language_code)
                .order_by(UserProfile.last_interaction_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    @staticmethod
    async def get_premium_users(limit: int = 100) -> List[UserProfile]:
        """Get Telegram Premium users for analytics."""
        async for session in get_database():
            stmt = (
                select(UserProfile)
                .where(UserProfile.is_premium == True)
                .order_by(UserProfile.last_interaction_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    @staticmethod
    async def get_user_summary(chat_id: int) -> Optional[dict]:
        """Get comprehensive user summary with stats."""
        user = await UserService.get_user_with_preferences(chat_id)
        if not user:
            return None
        
        # Get recent stats
        recent_stats = await UserService.get_user_stats(chat_id, days=7)
        
        # Get active preference
        current_preference = await UserService.get_current_preference(chat_id)
        
        return {
            "user_info": {
                "chat_id": user.chat_id,
                "user_id": user.user_id,
                "full_name": user.full_name,
                "username": user.username,
                "language_code": user.language_code,
                "is_premium": user.is_premium,
                "age_verified": user.age_verified,
            },
            "bot_data": {
                "loan_balance": user.loan_balance,
                "total_messages_sent": user.total_messages_sent,
                "total_loans_purchased": user.total_loans_purchased,
                "first_interaction_at": user.first_interaction_at,
                "last_interaction_at": user.last_interaction_at,
                "last_reset_at": user.last_reset_at,
            },
            "current_preference": current_preference,
            "preference_changes": len(user.preference_history),
            "recent_stats": [
                {
                    "date": stat.stat_date,
                    "messages": stat.messages_sent,
                    "loans_used": stat.loans_used,
                    "tokens": stat.tokens_consumed,
                }
                for stat in recent_stats
            ]
        } 