"""Tests for Phase 2: Core Bot Logic - age-gate, loans, basic commands, token counting."""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.database.models import UserProfile, MessageLog
from app.services.user_service import UserService
from app.services.message_service import MessageService
from app.services.rate_limiter import RateLimiter
from app.config.settings import settings


class TestUserService:
    """Test user service functionality."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return AsyncMock()
    
    # UserService now uses static methods, no need for fixture
    
    @pytest.mark.asyncio
    async def test_create_new_user(self, mock_db_session):
        """Test creating a new user profile."""
        chat_id = 12345
        
        # Mock Telegram user object
        mock_telegram_user = AsyncMock()
        mock_telegram_user.id = 123456
        mock_telegram_user.is_bot = False
        mock_telegram_user.first_name = "Test"
        mock_telegram_user.last_name = "User"
        mock_telegram_user.username = "testuser"
        mock_telegram_user.language_code = "en"
        
        # Mock get_database to return our mock session
        with patch('app.services.user_service.get_database') as mock_get_db:
            async def mock_db_generator():
                yield mock_db_session
            mock_get_db.return_value = mock_db_generator()
            
            # Mock database returning None (user doesn't exist)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db_session.execute = AsyncMock(return_value=mock_result)
            mock_db_session.add = MagicMock()
            mock_db_session.commit = AsyncMock()
            
            # Create user
            user = await UserService.get_or_create_user(mock_telegram_user, chat_id)
            
            # Verify user was created with correct defaults
            assert user.chat_id == chat_id
            assert user.user_id == 123456
            assert user.first_name == "Test"
            # age_verified may be None when created directly, that's OK
            
            # Verify database operations
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_age_verification(self, mock_db_session):
        """Test age verification functionality."""
        chat_id = 12345
        
        # Mock get_database to return our mock session
        with patch('app.services.user_service.get_database') as mock_get_db:
            async def mock_db_generator():
                yield mock_db_session
            mock_get_db.return_value = mock_db_generator()
            
            # Mock database execution result
            mock_db_session.execute.return_value.rowcount = 1
            
            # Verify age
            result = await UserService.verify_user_age(chat_id)
            
            assert result is True
            mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_loan_deduction(self, mock_db_session):
        """Test loan deduction system."""
        chat_id = 12345
        user = UserProfile(chat_id=chat_id, loan_balance=5)
        
        # Mock get_database to return our mock session
        with patch('app.services.user_service.get_database') as mock_get_db:
            async def mock_db_generator():
                yield mock_db_session
            mock_get_db.return_value = mock_db_generator()
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = user
            mock_db_session.execute = AsyncMock(return_value=mock_result)
            mock_db_session.commit = AsyncMock()
            
            # Mock UserService._get_or_create_today_stats
            with patch('app.services.user_service.UserService._get_or_create_today_stats') as mock_stats:
                mock_stats_obj = MagicMock()
                mock_stats.return_value = mock_stats_obj
                
                # Deduct loan
                result = await UserService.deduct_loan(chat_id)
            
            assert result is True
            assert user.loan_balance == 4
            mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_loan_deduction_insufficient_balance(self, mock_db_session):
        """Test loan deduction when balance is zero."""
        chat_id = 12345
        user = UserProfile(chat_id=chat_id, loan_balance=0)
        
        # Mock get_database to return our mock session
        with patch('app.services.user_service.get_database') as mock_get_db:
            async def mock_db_generator():
                yield mock_db_session
            mock_get_db.return_value = mock_db_generator()
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = user
            mock_db_session.execute = AsyncMock(return_value=mock_result)
            mock_db_session.commit = AsyncMock()
            
            # Try to deduct loan
            result = await UserService.deduct_loan(chat_id)
            
            assert result is False
            assert user.loan_balance == 0
    
    @pytest.mark.asyncio
    async def test_reset_chat_history(self, mock_db_session):
        """Test chat history reset."""
        chat_id = 12345
        
        # Mock get_database to return our mock session
        with patch('app.services.user_service.get_database') as mock_get_db:
            async def mock_db_generator():
                yield mock_db_session
            mock_get_db.return_value = mock_db_generator()
            
            # Mock database execution result
            mock_db_session.execute.return_value.rowcount = 1
            
            # Reset chat history
            result = await UserService.reset_chat_history(chat_id)
            
            assert result is True
            mock_db_session.commit.assert_called_once()


class TestMessageService:
    """Test message service functionality."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def message_service(self, mock_db_session):
        """Create message service with mocked database."""
        return MessageService(mock_db_session)
    
    @pytest.mark.asyncio
    async def test_save_user_message(self, message_service, mock_db_session):
        """Test saving user message."""
        chat_id = 12345
        content = "Hello Alice!"
        
        # Save message
        message = await message_service.save_user_message(chat_id, content)
        
        assert message.chat_id == chat_id
        assert message.content == content
        assert message.role == "user"
        assert message.tokens_used > 0
        
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    def test_token_counting(self, message_service):
        """Test token counting approximation."""
        # Test short message
        short_text = "Hi"
        tokens = message_service._count_tokens(short_text)
        assert tokens >= 0
        
        # Test long message
        long_text = "This is a much longer message that should have more tokens than the short one."
        long_tokens = message_service._count_tokens(long_text)
        assert long_tokens > tokens
    
    @pytest.mark.asyncio
    async def test_build_context_prompt(self, message_service, mock_db_session):
        """Test context prompt building."""
        chat_id = 12345
        
        # Mock user with last_reset_at
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = datetime.now(timezone.utc)
        
        # Mock empty message history
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []
        
        # Build context
        context = await message_service.build_context_prompt(chat_id, "user likes cats")
        
        assert "prompt" in context
        assert "tokens_used" in context
        assert "messages_included" in context
        assert context["tokens_used"] <= settings.max_context_tokens
        assert "user likes cats" in context["prompt"]
    
    def test_prompt_truncation(self, message_service):
        """Test prompt truncation when exceeding token limits."""
        # Create a very long list of messages
        long_messages = [
            "This is a very long message that should exceed token limits when combined with many other messages"
        ] * 100
        
        system_prompt = "You are Alice"
        user_preferences = "likes long conversations"
        
        # Test truncation
        truncated = message_service._truncate_prompt(long_messages, system_prompt, user_preferences)
        
        # Should be within limits
        tokens = message_service._count_tokens(truncated)
        assert tokens <= settings.max_context_tokens


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter instance."""
        limiter = RateLimiter()
        limiter.redis = AsyncMock()  # Mock Redis
        return limiter
    
    @pytest.mark.asyncio
    async def test_first_request_allowed(self, rate_limiter):
        """Test that first request is always allowed."""
        chat_id = 12345
        
        # Mock Redis returning None (no existing rate limit)
        rate_limiter.redis.get.return_value = None
        
        # Check rate limit
        is_limited = await rate_limiter.is_rate_limited(chat_id)
        
        assert is_limited is False
        rate_limiter.redis.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_subsequent_request_blocked(self, rate_limiter):
        """Test that subsequent requests are blocked."""
        chat_id = 12345
        
        # Mock Redis returning existing rate limit
        rate_limiter.redis.get.return_value = "1"
        
        # Check rate limit
        is_limited = await rate_limiter.is_rate_limited(chat_id)
        
        assert is_limited is True
    
    @pytest.mark.asyncio
    async def test_redis_error_allows_request(self, rate_limiter):
        """Test that Redis errors don't block requests."""
        chat_id = 12345
        
        # Mock Redis raising an exception
        rate_limiter.redis.get.side_effect = Exception("Redis error")
        
        # Check rate limit
        is_limited = await rate_limiter.is_rate_limited(chat_id)
        
        assert is_limited is False  # Should allow on error


class TestLoanSystem:
    """Integration tests for the loan system."""
    
    def test_loan_invariant(self):
        """Test the core invariant: 1 loan per assistant reply."""
        user = UserProfile(chat_id=12345, loan_balance=10)
        
        # User should have loans
        assert user.has_loans() is True
        
        # Deduct one loan
        result = user.deduct_loan()
        assert result is True
        assert user.loan_balance == 9
        
        # Should still have loans
        assert user.has_loans() is True
        
        # Deduct all remaining loans
        for _ in range(9):
            user.deduct_loan()
        
        # Should have no loans left
        assert user.loan_balance == 0
        assert user.has_loans() is False
        
        # Should not be able to deduct more
        result = user.deduct_loan()
        assert result is False
        assert user.loan_balance == 0
    
    def test_daily_loan_refill(self):
        """Test daily loan addition."""
        user = UserProfile(chat_id=12345, loan_balance=0)
        
        # Add daily loans
        user.add_loans(settings.free_daily_loans)
        
        assert user.loan_balance == settings.free_daily_loans
        assert user.has_loans() is True


class TestTokenManagement:
    """Test token counting and context management."""
    
    def test_max_context_limit(self):
        """Test that context respects 8k token limit."""
        message_service = MessageService(AsyncMock())
        
        # Test with content that would exceed limits
        very_long_text = "word " * 10000  # Very long text
        tokens = message_service._count_tokens(very_long_text)
        
        # Should count tokens (even if approximate)
        assert tokens > 0
        
        # Max context should be respected
        assert settings.max_context_tokens == 8000
    
    def test_chat_template_format(self):
        """Test ChatML template formatting."""
        from app.config.prompts import CHAT_TEMPLATES
        
        # Test system message format
        system_msg = CHAT_TEMPLATES["system"].format(content="You are Alice")
        assert "<|im_start|>system" in system_msg
        assert "<|im_end|>" in system_msg
        
        # Test user message format
        user_msg = CHAT_TEMPLATES["user"].format(content="Hello!")
        assert "<|im_start|>user" in user_msg
        assert "<|im_end|>" in user_msg
        
        # Test assistant format
        assistant_msg = CHAT_TEMPLATES["assistant"].format(content="Hi there!")
        assert "<|im_start|>assistant" in assistant_msg
        assert "<|im_end|>" in assistant_msg


class TestPersonalization:
    """Test personalization features."""
    
    def test_personalize_message_with_first_name(self):
        """Test personalizing message with first_name."""
        from app.bot.handlers import personalize_message
        from app.database.models import UserProfile
        
        # Create mock user profile with first_name
        user_profile = UserProfile(
            chat_id=12345,
            user_id=12345,
            first_name="Герман",
            username="herman_user"
        )
        
        # Test message with {{user}} placeholder
        message = "Привет, {{user}}! Как дела?"
        result = personalize_message(message, user_profile)
        
        assert result == "Привет, Герман! Как дела?"
    
    def test_personalize_message_with_username_fallback(self):
        """Test personalizing message with username when no first_name."""
        from app.bot.handlers import personalize_message
        from app.database.models import UserProfile
        
        # Create mock user profile without first_name
        user_profile = UserProfile(
            chat_id=12345,
            user_id=12345,
            first_name=None,
            username="herman_user"
        )
        
        message = "Привет, {{user}}! Как дела?"
        result = personalize_message(message, user_profile)
        
        assert result == "Привет, herman_user! Как дела?"
    
    def test_personalize_message_with_default_fallback(self):
        """Test personalizing message with default when no name available."""
        from app.bot.handlers import personalize_message
        from app.database.models import UserProfile
        
        # Create mock user profile without names
        user_profile = UserProfile(
            chat_id=12345,
            user_id=12345,
            first_name=None,
            username=None
        )
        
        message = "Привет, {{user}}! Как дела?"
        result = personalize_message(message, user_profile)
        
        assert result == "Привет, дорогой! Как дела?"
    
    def test_personalize_message_no_placeholder(self):
        """Test personalizing message without {{user}} placeholder."""
        from app.bot.handlers import personalize_message
        from app.database.models import UserProfile
        
        user_profile = UserProfile(
            chat_id=12345,
            user_id=12345,
            first_name="Герман"
        )
        
        message = "Привет! Как дела?"
        result = personalize_message(message, user_profile)
        
        # Should return unchanged
        assert result == "Привет! Как дела?"
    
    def test_personalize_message_no_user_profile(self):
        """Test personalizing message with None user_profile."""
        from app.bot.handlers import personalize_message
        
        message = "Привет, {{user}}! Как дела?"
        result = personalize_message(message, None)
        
        # Should return unchanged
        assert result == "Привет, {{user}}! Как дела?"


# Message counter functionality will be tested in integration tests


if __name__ == "__main__":
    pytest.main([__file__]) 