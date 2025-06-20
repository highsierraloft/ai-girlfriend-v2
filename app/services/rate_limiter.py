"""Redis-based rate limiter for user messages."""

import asyncio
import logging
from typing import Optional
import redis.asyncio as redis

from app.config.settings import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-based rate limiter using sliding window."""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def init_redis(self) -> None:
        """Initialize Redis connection."""
        try:
            self.redis = redis.from_url(settings.redis_url, decode_responses=True)
            # Test connection
            await self.redis.ping()
            logger.info("Redis connection initialized")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def close_redis(self) -> None:
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")
    
    async def is_rate_limited(self, chat_id: int) -> bool:
        """Check if user is rate limited."""
        if not self.redis:
            # If Redis is not available, allow all requests
            logger.warning("Redis not available, skipping rate limiting")
            return False
        
        key = f"rate_limit:{chat_id}"
        
        try:
            # Get current count
            current = await self.redis.get(key)
            
            if current is None:
                # First request, set with expiration
                await self.redis.setex(key, settings.rate_limit_per_user_sec, 1)
                return False
            else:
                # User is rate limited
                logger.info(f"User {chat_id} is rate limited")
                return True
                
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # On error, allow the request
            return False
    
    async def get_remaining_time(self, chat_id: int) -> int:
        """Get remaining time in seconds before user can send another message."""
        if not self.redis:
            return 0
            
        key = f"rate_limit:{chat_id}"
        
        try:
            ttl = await self.redis.ttl(key)
            return max(0, ttl)
        except Exception as e:
            logger.error(f"Error getting remaining time: {e}")
            return 0


class HuggingFaceRateLimiter:
    """Global rate limiter for Hugging Face API calls."""
    
    def __init__(self):
        self.semaphore = asyncio.Semaphore(settings.hf_max_rps)
        self.last_request_time = 0.0
        self.min_interval = 1.0 / settings.hf_max_rps
    
    async def acquire(self) -> None:
        """Acquire a slot for making HF API request."""
        await self.semaphore.acquire()
        
        # Ensure minimum interval between requests
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_interval:
            await asyncio.sleep(self.min_interval - time_since_last)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    def release(self) -> None:
        """Release the semaphore slot."""
        self.semaphore.release()


# Global instances
rate_limiter = RateLimiter()
hf_rate_limiter = HuggingFaceRateLimiter() 