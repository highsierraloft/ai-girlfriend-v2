"""Scheduler service for managing periodic tasks like daily loan replenishment."""

import logging
from datetime import datetime, timezone
from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_database
from app.database.models import UserProfile
from app.config.settings import settings

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing scheduled tasks."""
    
    @staticmethod
    async def replenish_daily_loans() -> dict:
        """
        Replenish loans to minimum 10 for users who have less than 10 loans.
        
        New logic:
        - If user has < 10 loans: set to 10 loans
        - If user has >= 10 loans: do nothing
        
        Returns:
            dict: Statistics about the replenishment process
        """
        logger.info("Starting daily loan replenishment task")
        
        stats = {
            "total_users_checked": 0,
            "users_replenished": 0,
            "loans_added": 0,
            "errors": 0,
            "timestamp": datetime.now(timezone.utc)
        }
        
        try:
            async for session in get_database():
                # Get all users who have less than the minimum loan balance
                min_loans = settings.free_daily_loans  # 10
                
                # Select users with loan_balance < 10
                stmt = select(UserProfile).where(UserProfile.loan_balance < min_loans)
                result = await session.execute(stmt)
                users_to_replenish = result.scalars().all()
                
                logger.info(f"Found {len(users_to_replenish)} users with < {min_loans} loans")
                stats["total_users_checked"] = len(users_to_replenish)
                
                # Replenish loans for each user
                for user in users_to_replenish:
                    try:
                        old_balance = user.loan_balance
                        loans_to_add = min_loans - old_balance
                        
                        # Update user's loan balance to minimum
                        user.loan_balance = min_loans
                        
                        stats["users_replenished"] += 1
                        stats["loans_added"] += loans_to_add
                        
                        logger.debug(f"Replenished loans for user {user.chat_id}: {old_balance} -> {min_loans} (+{loans_to_add})")
                        
                    except Exception as e:
                        logger.error(f"Error replenishing loans for user {user.chat_id}: {e}")
                        stats["errors"] += 1
                
                # Commit all changes at once
                if stats["users_replenished"] > 0:
                    await session.commit()
                    logger.info(f"Successfully replenished loans for {stats['users_replenished']} users")
                else:
                    logger.info("No users needed loan replenishment")
                
        except Exception as e:
            logger.error(f"Critical error during daily loan replenishment: {e}")
            stats["errors"] += 1
            raise
        
        logger.info(f"Daily loan replenishment completed: {stats}")
        return stats
    
    @staticmethod
    async def get_users_loan_stats() -> dict:
        """Get statistics about user loan balances."""
        try:
            async for session in get_database():
                # Get loan balance distribution
                result = await session.execute(
                    text("""
                        SELECT 
                            COUNT(*) as total_users,
                            COUNT(CASE WHEN loan_balance = 0 THEN 1 END) as zero_loans,
                            COUNT(CASE WHEN loan_balance > 0 AND loan_balance < 10 THEN 1 END) as low_loans,
                            COUNT(CASE WHEN loan_balance >= 10 AND loan_balance < 50 THEN 1 END) as medium_loans,
                            COUNT(CASE WHEN loan_balance >= 50 THEN 1 END) as high_loans,
                            AVG(loan_balance) as avg_loans,
                            MIN(loan_balance) as min_loans,
                            MAX(loan_balance) as max_loans
                        FROM user_profile
                    """)
                )
                
                row = result.fetchone()
                
                return {
                    "total_users": row.total_users,
                    "zero_loans": row.zero_loans,
                    "low_loans": row.low_loans,  # 1-9 loans
                    "medium_loans": row.medium_loans,  # 10-49 loans
                    "high_loans": row.high_loans,  # 50+ loans
                    "avg_loans": float(row.avg_loans) if row.avg_loans else 0,
                    "min_loans": row.min_loans,
                    "max_loans": row.max_loans,
                    "timestamp": datetime.now(timezone.utc)
                }
                
        except Exception as e:
            logger.error(f"Error getting loan statistics: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc)
            } 