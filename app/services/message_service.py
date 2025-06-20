"""Message service for context building and token management."""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from inspect import iscoroutine

from app.database.models import MessageLog, UserProfile
from app.config.settings import settings
from app.config.prompts import ALICE_BASE_PROMPT, CHAT_TEMPLATES

logger = logging.getLogger(__name__)

async def _maybe_await(value):
    """Await value if it's a coroutine (helps with AsyncMock)."""
    if iscoroutine(value):
        return await value
    return value

class MessageService:
    """Service for managing chat messages and building context."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        # TODO: Phase 3 - Initialize tokenizer here
        # from transformers import AutoTokenizer
        # self.tokenizer = AutoTokenizer.from_pretrained("tokenizer_name")
    
    async def save_user_message(self, chat_id: int, content: str) -> MessageLog:
        """Save user message to database."""
        message = MessageLog.create_user_message(
            chat_id=chat_id,
            content=content,
            tokens_used=self._count_tokens(content)
        )
        
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        
        logger.info(f"Saved user message for chat {chat_id}, tokens: {message.tokens_used}")
        return message
    
    async def save_assistant_message(self, chat_id: int, content: str) -> MessageLog:
        """Save assistant message to database."""
        message = MessageLog.create_assistant_message(
            chat_id=chat_id,
            content=content,
            tokens_used=self._count_tokens(content)
        )
        
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        
        logger.info(f"Saved assistant message for chat {chat_id}, tokens: {message.tokens_used}")
        return message
    
    async def get_chat_history(self, chat_id: int, limit: Optional[int] = None) -> List[MessageLog]:
        """Get chat history for a user after their last reset."""
        # Get user's last_reset_at timestamp
        user_result = await self.db.execute(
            select(UserProfile.last_reset_at).where(UserProfile.chat_id == chat_id)
        )
        last_reset_at = await _maybe_await(user_result.scalar_one_or_none())
        
        if last_reset_at is None:
            return []
        
        # Get messages after last reset, ordered by creation time
        query = select(MessageLog).where(
            and_(
                MessageLog.chat_id == chat_id,
                MessageLog.created_at > last_reset_at
            )
        ).order_by(MessageLog.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.db.execute(query)
        scalars_result = result.scalars()
        scalars_result = await _maybe_await(scalars_result)
        messages = await _maybe_await(scalars_result.all())
        
        # Return in chronological order (oldest first)
        return list(reversed(messages))
    
    async def build_context_prompt(self, chat_id: int, user_preferences: str = "") -> Dict[str, Any]:
        """Build context prompt for AI generation within token limits."""
        # Get chat history
        history = await self.get_chat_history(chat_id)
        
        # Build base prompt
        system_prompt = ALICE_BASE_PROMPT
        if user_preferences:
            system_prompt += f"\n\nUser preferences: {user_preferences}"
        
        # Format system message
        formatted_messages = [
            CHAT_TEMPLATES["system"].format(content=system_prompt)
        ]
        
        # Add chat history
        for message in history:
            if message.role == "user":
                formatted_messages.append(
                    CHAT_TEMPLATES["user"].format(content=message.content)
                )
            elif message.role == "assistant":
                formatted_messages.append(
                    CHAT_TEMPLATES["assistant"].format(content=message.content)
                )
        
        # Add assistant prefix for generation
        formatted_messages.append(CHAT_TEMPLATES["assistant_prefix"])
        
        # Join all messages
        full_prompt = "\n".join(formatted_messages)
        
        # Check token count and truncate if necessary
        total_tokens = self._count_tokens(full_prompt)
        
        if total_tokens > settings.max_context_tokens:
            logger.info(f"Prompt too long ({total_tokens} tokens), truncating...")
            full_prompt = self._truncate_prompt(formatted_messages, system_prompt, user_preferences)
            total_tokens = self._count_tokens(full_prompt)
        
        logger.info(f"Built context prompt for chat {chat_id}, tokens: {total_tokens}")
        
        return {
            "prompt": full_prompt,
            "tokens_used": total_tokens,
            "messages_included": len(history)
        }
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text. Placeholder implementation."""
        # TODO: Phase 3 - Implement proper tokenizer
        # return len(self.tokenizer.encode(text))
        
        # For now, use rough approximation: 1 token ≈ 4 characters
        return len(text) // 4
    
    def _truncate_prompt(self, formatted_messages: List[str], system_prompt: str, user_preferences: str) -> str:
        """Truncate prompt to fit within token limits."""
        # Always keep system prompt and assistant prefix
        system_msg = CHAT_TEMPLATES["system"].format(
            content=system_prompt + (f"\n\nUser preferences: {user_preferences}" if user_preferences else "")
        )
        assistant_prefix = CHAT_TEMPLATES["assistant_prefix"]
        
        # Calculate tokens for required parts
        required_tokens = self._count_tokens(system_msg + assistant_prefix)
        available_tokens = settings.max_context_tokens - required_tokens - 100  # Safety buffer
        
        # Add history messages from newest to oldest until we hit the limit
        history_messages = []
        current_tokens = 0
        
        # Skip system message and assistant prefix (first and last items)
        for message in reversed(formatted_messages[1:-1]):
            message_tokens = self._count_tokens(message)
            if current_tokens + message_tokens > available_tokens:
                break
            
            history_messages.insert(0, message)  # Insert at beginning to maintain order
            current_tokens += message_tokens
        
        # Build final prompt
        final_messages = [system_msg] + history_messages + [assistant_prefix]
        final_prompt = "\n".join(final_messages)
        
        logger.info(f"Truncated prompt to {self._count_tokens(final_prompt)} tokens")
        return final_prompt
    
    async def clear_chat_history(self, chat_id: int) -> int:
        """Clear chat history for a user. Returns number of messages deleted."""
        from sqlalchemy import delete
        
        result = await self.db.execute(
            delete(MessageLog).where(MessageLog.chat_id == chat_id)
        )
        await self.db.commit()
        
        deleted_count = result.rowcount
        logger.info(f"Cleared {deleted_count} messages for chat {chat_id}")
        return deleted_count
    
    async def get_message_stats(self, chat_id: int) -> Dict[str, Any]:
        """Get message statistics for a user."""
        from sqlalchemy import func
        
        # Count messages by role
        result = await self.db.execute(
            select(
                MessageLog.role,
                func.count(MessageLog.id).label('count'),
                func.sum(MessageLog.tokens_used).label('total_tokens')
            ).where(MessageLog.chat_id == chat_id).group_by(MessageLog.role)
        )
        
        stats = {}
        for role, count, total_tokens in result:
            stats[role] = {
                'count': count,
                'total_tokens': total_tokens or 0
            }
        
        return stats
    
    async def generate_ai_response(self, user_message: str, chat_id: int) -> str:
        """Generate AI response using Spice8B model.
        
        Args:
            user_message: The user's message
            chat_id: User's chat ID for context
            
        Returns:
            AI-generated response
        """
        from app.services.ai_service import ai_service, AIServiceError, RateLimitExceededError, ModelUnavailableError
        from app.services.user_service import UserService
        
        try:
            # Get user profile for preferences
            user_profile = await UserService.get_user_by_chat_id(chat_id)
            user_preferences = user_profile.preference if user_profile else None
            
            # Get recent chat history
            chat_history = await self.get_chat_history(chat_id, limit=20)
            
            # Convert to format expected by AI service
            history_for_ai = []
            for msg in chat_history:
                history_for_ai.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Generate AI response
            ai_response = await ai_service.generate_response(
                user_message=user_message,
                chat_history=history_for_ai,
                user_preferences=user_preferences
            )
            
            return ai_response
            
        except RateLimitExceededError:
            return "Whoa there, babe! 😅 I'm getting a bit overwhelmed with requests right now. Give me just a minute to catch my breath, okay? 💕"
            
        except ModelUnavailableError:
            return "Ugh, my brain is being a bit slow right now! 🙄 The servers are loading up - can you try again in like 30 seconds? I promise I'll be worth the wait! 😘"
            
        except AIServiceError as e:
            logger.error(f"AI service error for chat {chat_id}: {e}")
            return "Oops! 😔 Something went wrong in my pretty little head. Can you try asking me again? If this keeps happening, maybe give me a few minutes to get my act together! 💅"
            
        except Exception as e:
            logger.error(f"Unexpected error generating AI response for chat {chat_id}: {e}")
            return "Aww, I'm having a total brain freeze right now! 🥶 Try me again in a sec? I promise I'm usually much smarter than this! 😅" 