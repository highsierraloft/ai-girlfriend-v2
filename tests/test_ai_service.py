"""Tests for AI Service functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.ai_service import (
    AIService, 
    AIServiceError, 
    TokenLimitExceededError, 
    ModelUnavailableError,
    RateLimitExceededError
)
from app.config.prompts import ALICE_BASE_PROMPT, CHAT_TEMPLATES


class TestAIService:
    """Test AI Service functionality."""
    
    @pytest.fixture
    def ai_service(self):
        """Create AI service instance for testing."""
        return AIService()
    
    @pytest.fixture
    def mock_tokenizer(self):
        """Mock tokenizer for testing."""
        tokenizer = MagicMock()
        tokenizer.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens
        tokenizer.pad_token = None
        tokenizer.eos_token = "</s>"
        return tokenizer
    
    @pytest.fixture
    def sample_chat_history(self):
        """Sample chat history for testing."""
        return [
            {"role": "user", "content": "Hi Alice!"},
            {"role": "assistant", "content": "Hey there cutie! 😘"},
            {"role": "user", "content": "How are you today?"},
            {"role": "assistant", "content": "I'm doing great, thanks for asking! 💕"}
        ]
    
    def test_token_counting_with_tokenizer(self, ai_service, mock_tokenizer):
        """Test token counting with real tokenizer."""
        ai_service.tokenizer = mock_tokenizer
        
        text = "Hello world"
        tokens = ai_service.count_tokens(text)
        
        assert tokens == 5
        mock_tokenizer.encode.assert_called_once_with(text, add_special_tokens=True)
    
    def test_token_counting_fallback(self, ai_service):
        """Test token counting fallback without tokenizer."""
        ai_service.tokenizer = None
        
        text = "Hello world test"  # 16 chars
        tokens = ai_service.count_tokens(text)
        
        assert tokens == 4  # 16 // 4
    
    def test_token_counting_with_error(self, ai_service, mock_tokenizer):
        """Test token counting fallback when tokenizer fails."""
        mock_tokenizer.encode.side_effect = Exception("Tokenizer error")
        ai_service.tokenizer = mock_tokenizer
        
        text = "Hello world test"  # 16 chars
        tokens = ai_service.count_tokens(text)
        
        assert tokens == 4  # Fallback to estimation
    
    def test_build_chat_prompt_basic(self, ai_service, sample_chat_history):
        """Test basic prompt building."""
        ai_service.count_tokens = MagicMock(return_value=100)  # Mock token counting
        
        prompt, token_count = ai_service.build_chat_prompt(
            user_message="What's your favorite color?",
            chat_history=sample_chat_history
        )
        
        assert token_count == 100
        assert ALICE_BASE_PROMPT in prompt
        assert "What's your favorite color?" in prompt
        assert CHAT_TEMPLATES["assistant_prefix"] in prompt
        assert "<|im_start|>system" in prompt
        assert "<|im_start|>user" in prompt
    
    def test_build_chat_prompt_with_preferences(self, ai_service, sample_chat_history):
        """Test prompt building with user preferences."""
        ai_service.count_tokens = MagicMock(return_value=100)
        
        prompt, _ = ai_service.build_chat_prompt(
            user_message="Hello",
            chat_history=sample_chat_history,
            user_preferences="Loves cats and video games"
        )
        
        assert "Loves cats and video games" in prompt
    
    def test_build_chat_prompt_token_limit(self, ai_service):
        """Test prompt building with token limit truncation."""
        # Mock token counting to simulate different sizes
        def mock_count_tokens(text):
            if "system" in text:
                return 100
            if "assistant_prefix" in text:
                return 10
            if "user" in text and "current" in text:
                return 50
            return 200  # History messages
        
        ai_service.count_tokens = MagicMock(side_effect=mock_count_tokens)
        
        # Create large chat history
        large_history = []
        for i in range(10):
            large_history.extend([
                {"role": "user", "content": f"Message {i}"},
                {"role": "assistant", "content": f"Response {i}"}
            ])
        
        with patch('app.config.settings.settings.max_context_tokens', 500):
            with patch('app.config.settings.settings.hf_max_tokens', 100):
                prompt, token_count = ai_service.build_chat_prompt(
                    user_message="current message",
                    chat_history=large_history
                )
        
        # Should have truncated some history to fit token limit
        assert token_count <= 500
        assert "current message" in prompt  # Current message always included
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, ai_service):
        """Test successful AI service initialization."""
        with patch('app.services.ai_service.AutoTokenizer') as mock_tokenizer_class:
            with patch('app.services.ai_service.httpx.AsyncClient') as mock_client_class:
                with patch('app.services.ai_service.settings.hf_endpoint', 'https://api-inference.huggingface.co/models/test'):
                    mock_tokenizer = MagicMock()
                    mock_tokenizer.pad_token = None
                    mock_tokenizer.eos_token = "</s>"
                    mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer
        
                    mock_client = AsyncMock()
                    mock_client_class.return_value = mock_client
        
                    await ai_service.initialize()
        
                    assert ai_service._initialized is True
                    assert ai_service.tokenizer is not None
                    assert ai_service.client is not None
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self, ai_service):
        """Test AI service initialization failure."""
        with patch('app.services.ai_service.AutoTokenizer') as mock_tokenizer_class:
            with patch('app.services.ai_service.settings.hf_endpoint', 'https://api-inference.huggingface.co/models/test'):
                mock_tokenizer_class.from_pretrained.side_effect = Exception("Model not found")
    
                with pytest.raises(AIServiceError, match="Initialization failed"):
                    await ai_service.initialize()
    
    @pytest.mark.asyncio
    async def test_close(self, ai_service):
        """Test AI service cleanup."""
        mock_client = AsyncMock()
        ai_service.client = mock_client
        ai_service._initialized = True
        
        await ai_service.close()
        
        mock_client.aclose.assert_called_once()
        assert ai_service.client is None
        assert ai_service._initialized is False
    
    @pytest.mark.asyncio
    async def test_make_api_request_success(self, ai_service):
        """Test successful API request."""
        mock_client = AsyncMock()
        mock_response = MagicMock()  # Changed to MagicMock
        mock_response.status_code = 200
        mock_response.json.return_value = [{"generated_text": "Hello there!"}]
        mock_client.post.return_value = mock_response
        
        ai_service.client = mock_client
        ai_service._initialized = True
        
        result = await ai_service._make_api_request("test prompt")
        
        assert result == [{"generated_text": "Hello there!"}]
        mock_client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_make_api_request_rate_limit(self, ai_service):
        """Test API request rate limit error."""
        mock_client = AsyncMock()
        mock_response = MagicMock()  # Changed to MagicMock
        mock_response.status_code = 429
        mock_client.post.return_value = mock_response
        
        ai_service.client = mock_client
        ai_service._initialized = True
        
        with pytest.raises(RateLimitExceededError):
            await ai_service._make_api_request("test prompt")
    
    @pytest.mark.asyncio
    async def test_make_api_request_model_unavailable(self, ai_service):
        """Test API request when model is unavailable."""
        mock_client = AsyncMock()
        mock_response = MagicMock()  # Changed to MagicMock
        mock_response.status_code = 503
        mock_client.post.return_value = mock_response
        
        ai_service.client = mock_client
        ai_service._initialized = True
        
        with pytest.raises(ModelUnavailableError):
            await ai_service._make_api_request("test prompt")
    
    @pytest.mark.asyncio
    async def test_generate_response_success(self, ai_service, sample_chat_history):
        """Test successful response generation."""
        # Mock all dependencies
        ai_service._initialized = True
        ai_service.build_chat_prompt = MagicMock(return_value=("test prompt", 100))
        ai_service._make_api_request = AsyncMock(return_value=[{"generated_text": "Hi cutie! 😘"}])
        ai_service._clean_response = MagicMock(return_value="Hi cutie! 😘")
        
        with patch('app.config.settings.settings.max_context_tokens', 8000):
            response = await ai_service.generate_response(
                user_message="Hello",
                chat_history=sample_chat_history,
                user_preferences="Loves anime"
            )
        
        assert response == "Hi cutie! 😘"
        ai_service.build_chat_prompt.assert_called_once_with("Hello", sample_chat_history, "Loves anime")
        ai_service._make_api_request.assert_called_once_with("test prompt", "Hello", sample_chat_history, "Loves anime")
    
    @pytest.mark.asyncio
    async def test_generate_response_token_limit_exceeded(self, ai_service, sample_chat_history):
        """Test response generation with token limit exceeded."""
        ai_service._initialized = True
        ai_service.build_chat_prompt = MagicMock(return_value=("test prompt", 9000))  # Too many tokens
        
        with patch('app.config.settings.settings.max_context_tokens', 8000):
            with pytest.raises(TokenLimitExceededError):
                await ai_service.generate_response(
                    user_message="Hello",
                    chat_history=sample_chat_history
                )
    
    @pytest.mark.asyncio
    async def test_generate_response_empty_response(self, ai_service, sample_chat_history):
        """Test response generation with empty AI response."""
        ai_service._initialized = True
        ai_service.build_chat_prompt = MagicMock(return_value=("test prompt", 100))
        ai_service._make_api_request = AsyncMock(return_value=[{"generated_text": ""}])
        
        with pytest.raises(AIServiceError, match="Empty response"):
            await ai_service.generate_response(
                user_message="Hello",
                chat_history=sample_chat_history
            )
    
    def test_clean_response(self, ai_service):
        """Test response cleaning."""
        # Test removing ChatML tokens
        dirty_response = "<|im_start|>assistant\nHello there!<|im_end|>"
        cleaned = ai_service._clean_response(dirty_response)
        assert cleaned == "Hello there!"
        
        # Test removing assistant prefix
        dirty_response = "assistant\nHi cutie!"
        cleaned = ai_service._clean_response(dirty_response)
        assert cleaned == "Hi cutie!"
        
        # Test length truncation
        long_response = "A" * 2500
        cleaned = ai_service._clean_response(long_response)
        assert len(cleaned) <= 2000
        assert cleaned.endswith("...")
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, ai_service):
        """Test health check when service is healthy."""
        ai_service._initialized = True
        ai_service.tokenizer = MagicMock()
        ai_service.client = AsyncMock()
        ai_service._make_api_request = AsyncMock(return_value=[{"generated_text": "OK"}])
        
        health = await ai_service.health_check()
        
        assert health["initialized"] is True
        assert health["tokenizer_loaded"] is True
        assert health["client_ready"] is True
        assert health["api_responsive"] is True
        assert "timestamp" in health
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, ai_service):
        """Test health check when service has issues."""
        ai_service._initialized = True
        ai_service.tokenizer = MagicMock()
        ai_service.client = AsyncMock()
        ai_service._make_api_request = AsyncMock(side_effect=Exception("API error"))
        
        health = await ai_service.health_check()
        
        assert health["initialized"] is True
        assert health["tokenizer_loaded"] is True
        assert health["client_ready"] is True
        assert health["api_responsive"] is False
        assert "error" in health

    @pytest.mark.asyncio
    async def test_initialize_dedicated_endpoint(self, ai_service):
        """Test AI service initialization with dedicated endpoint (skips tokenizer)."""
        with patch('app.services.ai_service.httpx.AsyncClient') as mock_client_class:
            with patch('app.services.ai_service.settings.hf_endpoint', 'https://test.endpoints.huggingface.cloud'):
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client
    
                await ai_service.initialize()
    
                assert ai_service._initialized is True
                assert ai_service.tokenizer is None  # Should skip tokenizer for dedicated endpoints


class TestAIServiceIntegration:
    """Integration tests for AI Service."""
    
    @pytest.mark.asyncio
    async def test_full_conversation_flow(self):
        """Test a complete conversation flow with mocked API."""
        ai_service = AIService()
        
        # Mock tokenizer
        with patch('app.services.ai_service.AutoTokenizer') as mock_tokenizer_class:
            mock_tokenizer = MagicMock()
            mock_tokenizer.pad_token = None
            mock_tokenizer.eos_token = "</s>"
            mock_tokenizer.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens always
            mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer
            
            # Mock HTTP client
            with patch('app.services.ai_service.httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_response = MagicMock()  # Changed to MagicMock
                mock_response.status_code = 200
                mock_response.json.return_value = [{"generated_text": "Hey there! How can I help you today? 😊"}]
                mock_client.post.return_value = mock_response
                mock_client_class.return_value = mock_client
                
                # Initialize service
                await ai_service.initialize()
                
                # Test conversation
                chat_history = [
                    {"role": "user", "content": "Hi Alice!"},
                    {"role": "assistant", "content": "Hello! Nice to meet you!"}
                ]
                
                response = await ai_service.generate_response(
                    user_message="How are you today?",
                    chat_history=chat_history,
                    user_preferences="Loves friendly conversation"
                )
                
                assert "Hey there!" in response
                assert len(response) > 0
                
                # Cleanup
                await ai_service.close() 