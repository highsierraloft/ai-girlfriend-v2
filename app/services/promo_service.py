"""Promo code service for handling promotional codes and rewards."""

import logging
from typing import Optional, Tuple
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.database.connection import get_database
from app.database.models import PromoCode, PromoCodeUsage, UserProfile

logger = logging.getLogger(__name__)


class PromoCodeService:
    """Service for handling promo code operations."""
    
    @staticmethod
    async def use_promo_code(chat_id: int, code: str) -> Tuple[bool, str, int]:
        """
        Attempt to use a promo code for a user.
        
        Args:
            chat_id: User's chat ID
            code: Promo code to use
            
        Returns:
            Tuple of (success: bool, message: str, loans_received: int)
        """
        async for session in get_database():
            try:
                # Find the promo code
                stmt = (
                    select(PromoCode)
                    .options(selectinload(PromoCode.usage_history))
                    .where(PromoCode.code == code.upper().strip())
                )
                result = await session.execute(stmt)
                promo_code = result.scalar_one_or_none()
                
                if not promo_code:
                    return False, "❌ Промокод не найден", 0
                
                # Check if promo code is valid
                if not promo_code.is_valid():
                    if not promo_code.is_active:
                        return False, "❌ Промокод неактивен", 0
                    elif promo_code.max_uses and promo_code.current_uses >= promo_code.max_uses:
                        return False, "❌ Промокод исчерпан", 0
                    else:
                        return False, "❌ Промокод истёк", 0
                
                # Check if user can use this code
                if not promo_code.can_be_used_by(chat_id):
                    return False, "❌ Вы уже использовали этот промокод", 0
                
                # Get user profile
                user_stmt = select(UserProfile).where(UserProfile.chat_id == chat_id)
                user_result = await session.execute(user_stmt)
                user = user_result.scalar_one_or_none()
                
                if not user:
                    return False, "❌ Пользователь не найден", 0
                
                # Add loans to user
                user.add_loans(promo_code.loan_reward)
                
                # Create usage record
                usage = PromoCodeUsage(
                    chat_id=chat_id,
                    promo_code_id=promo_code.id,
                    loans_received=promo_code.loan_reward
                )
                session.add(usage)
                
                # Update promo code usage count
                promo_code.current_uses += 1
                
                await session.commit()
                
                logger.info(f"Promo code '{code}' used by chat_id={chat_id}, received {promo_code.loan_reward} loans")
                
                return True, f"✅ Промокод активирован! Получено {promo_code.loan_reward} кредитов", promo_code.loan_reward
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error using promo code '{code}' for chat_id={chat_id}: {e}")
                return False, "❌ Произошла ошибка при активации промокода", 0
    
    @staticmethod
    async def get_promo_code_info(code: str) -> Optional[dict]:
        """Get information about a promo code."""
        async for session in get_database():
            stmt = select(PromoCode).where(PromoCode.code == code.upper().strip())
            result = await session.execute(stmt)
            promo_code = result.scalar_one_or_none()
            
            if not promo_code:
                return None
            
            return {
                "code": promo_code.code,
                "loan_reward": promo_code.loan_reward,
                "is_active": promo_code.is_active,
                "is_valid": promo_code.is_valid(),
                "current_uses": promo_code.current_uses,
                "max_uses": promo_code.max_uses,
                "expires_at": promo_code.expires_at
            }
    
    @staticmethod
    async def has_user_used_promo(chat_id: int, code: str) -> bool:
        """Check if user has already used a specific promo code."""
        async for session in get_database():
            # Get promo code ID first
            promo_stmt = select(PromoCode.id).where(PromoCode.code == code.upper().strip())
            promo_result = await session.execute(promo_stmt)
            promo_id = promo_result.scalar_one_or_none()
            
            if not promo_id:
                return False
            
            # Check usage
            usage_stmt = select(PromoCodeUsage).where(
                PromoCodeUsage.chat_id == chat_id,
                PromoCodeUsage.promo_code_id == promo_id
            )
            usage_result = await session.execute(usage_stmt)
            usage = usage_result.scalar_one_or_none()
            
            return usage is not None
    
    @staticmethod
    async def get_user_promo_history(chat_id: int, limit: int = 10) -> list:
        """Get user's promo code usage history."""
        async for session in get_database():
            stmt = (
                select(PromoCodeUsage, PromoCode.code, PromoCode.loan_reward)
                .join(PromoCode)
                .where(PromoCodeUsage.chat_id == chat_id)
                .order_by(PromoCodeUsage.used_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            
            history = []
            for usage, code, reward in result:
                history.append({
                    "code": code,
                    "loans_received": reward,
                    "used_at": usage.used_at
                })
            
            return history 