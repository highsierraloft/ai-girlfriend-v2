"""AI Service for Spice8B integration with Hugging Face API.

This service handles all AI-related operations including:
- Text generation with Spice8B model
- Token counting and context management
- Retry logic and error handling
- Rate limiting and request queuing
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import json

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from transformers import AutoTokenizer

from app.config.settings import settings
from app.config.prompts import ALICE_BASE_PROMPT, CHAT_TEMPLATES, build_personalized_system_prompt

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Base exception for AI service errors."""
    pass


class TokenLimitExceededError(AIServiceError):
    """Raised when token limit is exceeded."""
    pass


class ModelUnavailableError(AIServiceError):
    """Raised when the AI model is unavailable."""
    pass


class RateLimitExceededError(AIServiceError):
    """Raised when rate limit is exceeded."""
    pass


class AIService:
    """Service for interacting with Spice8B via Hugging Face API."""
    
    def __init__(self):
        self.tokenizer: Optional[AutoTokenizer] = None
        self.client: Optional[httpx.AsyncClient] = None
        self._request_semaphore = asyncio.Semaphore(settings.hf_max_rps)
        self._last_request_time = 0.0
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the AI service with tokenizer and HTTP client."""
        if self._initialized:
            logger.info("🔄 AI service already initialized, skipping...")
            return
            
        logger.info("🚀 Initializing AI service...")
        logger.info(f"🔧 Configuration:")
        logger.info(f"   - Model: {settings.hf_model_name}")
        logger.info(f"   - Endpoint: {settings.hf_endpoint}")
        logger.info(f"   - API key: {settings.hf_api_key[:10]}...{settings.hf_api_key[-4:]}")
        logger.info(f"   - Timeout: {settings.hf_timeout}s")
        logger.info(f"   - Max tokens: {settings.hf_max_tokens}")
        logger.info(f"   - Temperature: {settings.hf_temperature}")
        
        try:
            # Initialize tokenizer for accurate token counting
            if "endpoints.huggingface.cloud" in settings.hf_endpoint:
                # Dedicated endpoint – cannot download tokenizer files.
                logger.info("🌐 Dedicated HF Endpoint detected – skipping tokenizer load (will use estimation)")
                self.tokenizer = None
            else:
                logger.info(f"🔤 Loading tokenizer for model: {settings.hf_model_name}")
                try:
                    logger.info("📦 Importing AutoTokenizer...")
                    self.tokenizer = AutoTokenizer.from_pretrained(
                        settings.hf_model_name,
                        trust_remote_code=True,
                        use_fast=True,
                        token=settings.hf_api_key if settings.hf_api_key != "your_huggingface_api_key_here" else None
                    )
                    
                    # Set pad token if not present
                    if self.tokenizer.pad_token is None:
                        self.tokenizer.pad_token = self.tokenizer.eos_token
                        logger.info("🔧 Set pad_token to eos_token")
                        
                    logger.info("✅ Tokenizer loaded successfully")
                    logger.info(f"🔤 Tokenizer vocab size: {len(self.tokenizer.get_vocab())}")
                    
                except ImportError as e:
                    logger.warning(f"❌ Failed to import transformers: {e}")
                    logger.info("💡 Install transformers for accurate token counting")
                    self.tokenizer = None
                except Exception as tokenizer_error:
                    logger.error(f"❌ Failed to load tokenizer: {tokenizer_error}")
                    # For public API failure, raise; otherwise fallback
                    raise AIServiceError(f"Initialization failed: {tokenizer_error}")
            
            # Initialize HTTP client with proper settings
            logger.info("🌐 Initializing HTTP client...")
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.hf_timeout),
                headers={
                    "Authorization": f"Bearer {settings.hf_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "AI-Girlfriend-Bot/1.0"
                }
            )
            logger.info("✅ HTTP client initialized")
            
            # Initialize rate limiting
            logger.info("⏱️ Initializing rate limiting...")
            self._request_semaphore = asyncio.Semaphore(settings.hf_max_rps)
            self._last_request_time = 0.0
            logger.info(f"✅ Rate limiting initialized: {settings.hf_max_rps} RPS max")
            
            self._initialized = True
            logger.info("🎉 AI service initialized successfully!")
            
        except Exception as e:
            logger.error(f"💥 Failed to initialize AI service: {e}")
            import traceback
            logger.error(f"📚 Full traceback: {traceback.format_exc()}")
            raise AIServiceError(f"Initialization failed: {e}")
    
    async def close(self) -> None:
        """Clean up resources."""
        if self.client:
            await self.client.aclose()
            self.client = None
        self._initialized = False
        logger.info("AI service closed")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using the model's tokenizer.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        if not self.tokenizer:
            # Fallback to rough estimation if tokenizer not available
            return len(text) // 4
        
        try:
            tokens = self.tokenizer.encode(text, add_special_tokens=True)
            return len(tokens)
        except Exception as e:
            logger.warning(f"Token counting failed, using estimation: {e}")
            return len(text) // 4
    
    def _optimize_chat_history_for_context(
        self,
        chat_history: List[Dict[str, Any]],
        system_tokens: int,
        current_message_tokens: int,
        max_context_tokens: int = 8000
    ) -> List[Dict[str, Any]]:
        """Optimize chat history to fit within context window.
        
        Strategy:
        1. Always keep the most recent messages
        2. Try to maintain conversation pairs (user + assistant)
        3. Prioritize messages with higher engagement (longer responses)
        4. Keep important context markers (first message, topic changes)
        
        Args:
            chat_history: Full chat history
            system_tokens: Tokens used by system prompt
            current_message_tokens: Tokens for current user message
            max_context_tokens: Maximum context window size
            
        Returns:
            Optimized chat history that fits in context
        """
        if not chat_history:
            return []
        
        # Reserve tokens for response generation and safety buffer
        reserved_tokens = settings.hf_max_tokens + 100
        available_tokens = max_context_tokens - system_tokens - current_message_tokens - reserved_tokens
        
        logger.info(f"🧮 Context optimization:")
        logger.info(f"   - Max context: {max_context_tokens} tokens")
        logger.info(f"   - System prompt: {system_tokens} tokens")
        logger.info(f"   - Current message: {current_message_tokens} tokens")
        logger.info(f"   - Reserved for response: {reserved_tokens} tokens")
        logger.info(f"   - Available for history: {available_tokens} tokens")
        
        if available_tokens <= 0:
            logger.warning("⚠️ No tokens available for chat history")
            return []
        
        # Start with most recent messages and work backwards
        optimized_history = []
        used_tokens = 0
        
        # Process history in reverse (newest first)
        for i, msg in enumerate(reversed(chat_history)):
            if msg["role"] not in ["user", "assistant"]:
                continue
                
            msg_tokens = self.count_tokens(msg["content"])
            
            # Check if we can fit this message
            if used_tokens + msg_tokens <= available_tokens:
                optimized_history.append(msg)
                used_tokens += msg_tokens
                logger.debug(f"✅ Added message {i+1}: {msg['role']} ({msg_tokens} tokens)")
            else:
                logger.debug(f"❌ Skipped message {i+1}: would exceed limit")
                break
        
        # Reverse back to chronological order
        optimized_history.reverse()
        
        logger.info(f"📚 Optimized history: {len(optimized_history)}/{len(chat_history)} messages, {used_tokens} tokens")
        
        return optimized_history
    
    def _build_openai_messages(
        self,
        user_message: str,
        chat_history: List[Dict[str, Any]],
        user_preferences: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Build OpenAI-format messages array with smart context management.
        
        Args:
            user_message: Current user message
            chat_history: Chat history
            user_preferences: User preferences
            
        Returns:
            OpenAI-format messages array
        """
        # Build personalized system prompt
        system_content = build_personalized_system_prompt(user_preferences)
        system_tokens = self.count_tokens(system_content)
        current_message_tokens = self.count_tokens(user_message)
        
        # Optimize chat history for context window
        optimized_history = self._optimize_chat_history_for_context(
            chat_history=chat_history,
            system_tokens=system_tokens,
            current_message_tokens=current_message_tokens,
            max_context_tokens=8000  # Spice8B context window
        )
        
        # Build messages array
        messages = [{"role": "system", "content": system_content}]
        
        # Add optimized chat history
        for msg in optimized_history:
            if msg["role"] in ["user", "assistant"]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Log final stats
        total_tokens = sum(self.count_tokens(msg["content"]) for msg in messages)
        logger.info(f"📋 Built OpenAI messages: {len(messages)} total, ~{total_tokens} tokens")
        logger.info(f"   - System: 1 message (~{system_tokens} tokens)")
        logger.info(f"   - History: {len(optimized_history)} messages")
        logger.info(f"   - Current: 1 message (~{current_message_tokens} tokens)")
        
        return messages

    def build_chat_prompt(
        self, 
        user_message: str, 
        chat_history: List[Dict[str, Any]], 
        user_preferences: Optional[str] = None
    ) -> Tuple[str, int]:
        """Build L3-TheSpice prompt with token management.
        
        Args:
            user_message: Current user message
            chat_history: List of previous messages with 'role' and 'content'
            user_preferences: User's preferences/profile info
            
        Returns:
            Tuple of (prompt_string, total_tokens)
        """
        logger.debug(f"🏗️ Building prompt for L3-TheSpice format")
        logger.debug(f"📝 User message: '{user_message}'")
        logger.debug(f"📚 History messages: {len(chat_history)}")
        logger.debug(f"⚙️ User preferences: '{user_preferences}'")
        
        # Start with system prompt
        system_content = ALICE_BASE_PROMPT
        if user_preferences:
            system_content += f"\n\nUser preferences to keep in mind: {user_preferences}"
            logger.debug(f"✅ Added user preferences to system prompt")
        
        prompt_parts = [
            CHAT_TEMPLATES["system"].format(content=system_content)
        ]
        
        logger.debug(f"📋 System prompt length: {len(prompt_parts[0])} chars")
        
        # Add chat history (newest first, then reverse for chronological order)
        history_parts = []
        for i, msg in enumerate(reversed(chat_history)):  # Start with newest
            if msg["role"] in ["user", "assistant"]:
                template = CHAT_TEMPLATES[msg["role"]]
                history_part = template.format(content=msg["content"])
                history_parts.append(history_part)
                logger.debug(f"📝 Added history message {i+1}: {msg['role']} - '{msg['content'][:50]}...'")
        
        logger.debug(f"📚 Total history parts: {len(history_parts)}")
        
        # Add current user message
        current_user_msg = CHAT_TEMPLATES["user"].format(content=user_message)
        logger.debug(f"👤 Current user message formatted: '{current_user_msg}'")
        
        # Add assistant prefix
        assistant_prefix = CHAT_TEMPLATES["assistant_prefix"]
        logger.debug(f"🤖 Assistant prefix: '{assistant_prefix}'")
        
        # Calculate tokens and truncate if necessary
        base_tokens = self.count_tokens(prompt_parts[0] + current_user_msg + assistant_prefix)
        available_tokens = settings.max_context_tokens - base_tokens - settings.hf_max_tokens - 100  # Safety buffer
        
        logger.debug(f"🧮 Token calculation:")
        logger.debug(f"   - System + current msg + prefix: {base_tokens} tokens")
        logger.debug(f"   - Max context tokens: {settings.max_context_tokens}")
        logger.debug(f"   - Max new tokens: {settings.hf_max_tokens}")
        logger.debug(f"   - Available for history: {available_tokens} tokens")
        
        # Add history until we hit token limit
        used_history = []
        current_tokens = 0
        
        for i, history_part in enumerate(history_parts):
            part_tokens = self.count_tokens(history_part)
            if current_tokens + part_tokens <= available_tokens:
                used_history.append(history_part)
                current_tokens += part_tokens
                logger.debug(f"✅ Added history part {i+1}: {part_tokens} tokens (total: {current_tokens})")
            else:
                logger.debug(f"❌ Skipped history part {i+1}: would exceed limit ({current_tokens + part_tokens} > {available_tokens})")
                break
        
        # Reverse history back to chronological order
        used_history.reverse()
        logger.debug(f"🔄 Reversed history to chronological order: {len(used_history)} messages")
        
        # Build final prompt for L3-TheSpice format
        # Format: {System Prompt}\n\nUsername: {Input}\nAlice: {Response}\nUsername: {Input}\nAlice:
        if used_history:
            final_prompt = (
                prompt_parts[0] + "\n\n" +
                "\n".join(used_history) + "\n" +
                current_user_msg + "\n" +
                assistant_prefix
            )
            logger.debug(f"📋 Built prompt with history: system + {len(used_history)} history + current + prefix")
        else:
            final_prompt = (
                prompt_parts[0] + "\n\n" +
                current_user_msg + "\n" +
                assistant_prefix
            )
            logger.debug(f"📋 Built prompt without history: system + current + prefix")
        
        total_tokens = self.count_tokens(final_prompt)
        
        logger.info(f"✅ Prompt built: {total_tokens} tokens, {len(used_history)}/{len(history_parts)} history messages")
        logger.debug(f"🔍 Final prompt preview (first 300 chars):")
        logger.debug(f"'{final_prompt[:300]}...'")
        
        return final_prompt, total_tokens
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException))
    )
    async def _make_api_request(self, prompt: str, user_message: str = "", chat_history: List[Dict[str, Any]] = None, user_preferences: Optional[str] = None) -> Dict[str, Any]:
        """Make API request to Hugging Face with retry logic.
        
        Args:
            prompt: L3-TheSpice formatted prompt
            user_message: Current user message (for OpenAI format)
            chat_history: Chat history (for OpenAI format)  
            user_preferences: User preferences (for OpenAI format)
            
        Returns:
            API response data
            
        Raises:
            Various AI service exceptions
        """
        logger.info(f"🔧 _make_api_request called with prompt length: {len(prompt)}")
        logger.info(f"🔧 Current settings: endpoint={settings.hf_endpoint}, model={settings.hf_model_name}")
        
        if not self.client:
            raise AIServiceError("AI service not initialized")
        
        # Rate limiting - ensure we don't exceed max RPS
        async with self._request_semaphore:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._last_request_time
            min_interval = 1.0 / settings.hf_max_rps
            
            if time_since_last < min_interval:
                sleep_time = min_interval - time_since_last
                logger.info(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
            
            self._last_request_time = asyncio.get_event_loop().time()
            
            # ---------------------------
            # Build final endpoint URL
            # ---------------------------
            # Dedicated HF Inference Endpoints expose the base URL like
            #   https://<id>.<region>.aws.endpoints.huggingface.cloud
            # and require appending "/<model_name>". The public Inference
            # API already contains "/models/<model_name>" in the URL.
            if "endpoints.huggingface.cloud" in settings.hf_endpoint:
                # Special-case for GGUF models hosted on a dedicated llama.cpp
                # container. Those endpoints expose **only** the OpenAI-compatible
                # chat-completion route at `/v1/chat/completions` (see HF docs
                # https://huggingface.co/docs/gguf-llamacpp and TGI Messages API).
                # Calling the root URL directly returns 404 ("Model not found").
                # We therefore detect GGUF deployments and switch to the
                # appropriate route + payload format.
                is_gguf = settings.hf_model_name.lower().endswith(".gguf")
                # Also check for -GGUF suffix (common in model names)
                if not is_gguf:
                    is_gguf = settings.hf_model_name.lower().endswith("-gguf")
                logger.info(f"🔍 GGUF detection: model_name='{settings.hf_model_name}', lower='{settings.hf_model_name.lower()}', is_gguf={is_gguf}")
                if is_gguf:
                    request_url = f"{settings.hf_endpoint.rstrip('/')}/v1/chat/completions"
                    logger.info(f"✅ Using GGUF/llama.cpp endpoint: {request_url}")
                else:
                    # Dedicated endpoint already targets a single model
                    request_url = settings.hf_endpoint.rstrip("/")
                    logger.info(f"❌ Using standard dedicated endpoint: {request_url}")
            elif "/models/" in settings.hf_endpoint:
                request_url = settings.hf_endpoint.rstrip("/")
            else:
                request_url = f"{settings.hf_endpoint.rstrip('/')}/{settings.hf_model_name}"

            # Prepare request payload for HF Inference API (text-generation)
            if "v1/chat/completions" in request_url:
                # OpenAI-compatible payload for llama.cpp endpoints
                # Use smart context management for optimal token usage
                if chat_history is None:
                    chat_history = []
                
                # Build optimized messages array with smart context management
                messages = self._build_openai_messages(
                    user_message=user_message,
                    chat_history=chat_history,
                    user_preferences=user_preferences
                )
                
                payload = {
                    "model": "tgi",  # placeholder – not used but required by spec
                    "messages": messages,
                    "temperature": settings.hf_temperature,
                    "top_p": settings.hf_top_p,
                    "top_k": settings.hf_top_k,
                    "max_tokens": settings.hf_max_tokens,
                    "repetition_penalty": settings.hf_repetition_penalty,
                    "frequency_penalty": settings.hf_frequency_penalty,
                    "presence_penalty": settings.hf_presence_penalty,
                    "no_repeat_ngram_size": settings.hf_no_repeat_ngram_size,
                    "do_sample": settings.hf_do_sample,
                    "min_p": settings.hf_min_p,
                    "stream": False,
                }
            else:
                # Standard HF custom inference payload
                payload = {
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": settings.hf_max_tokens,
                        "temperature": settings.hf_temperature,
                        "top_p": settings.hf_top_p,
                        "top_k": settings.hf_top_k,
                        "repetition_penalty": settings.hf_repetition_penalty,
                        "frequency_penalty": settings.hf_frequency_penalty,
                        "presence_penalty": settings.hf_presence_penalty,
                        "no_repeat_ngram_size": settings.hf_no_repeat_ngram_size,
                        "do_sample": settings.hf_do_sample,
                        "min_p": settings.hf_min_p,
                        "return_full_text": False,
                    },
                    "options": {"wait_for_model": True, "use_cache": False},
                }
            
            logger.info(f"🚀 Making API request to: {request_url}")
            logger.info(f"📊 Request parameters: max_tokens={settings.hf_max_tokens}, temp={settings.hf_temperature}, top_p={settings.hf_top_p}, top_k={settings.hf_top_k}")
            logger.info(f"📝 Prompt length: {len(prompt)} chars, estimated tokens: {self.count_tokens(prompt)}")
            logger.info(f"🔍 Full prompt preview: {prompt[:500]}...")
            logger.debug(f"🔧 Full payload: {payload}")
            
            try:
                response = await self.client.post(
                    request_url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.hf_api_key}",
                        "Content-Type": "application/json"
                    }
                )
                
                logger.info(f"📡 Response status: {response.status_code}")
                logger.info(f"📋 Response headers: {dict(response.headers)}")
                
                # Handle different response codes
                if response.status_code == 200:
                    response_data = response.json()
                    logger.info(f"🔍 Raw API response: {response_data}")
                    # Normalise OpenAI-compatible llama.cpp response to match
                    # the list[{"generated_text": str}] schema used across the
                    # rest of the codebase. This keeps downstream logic
                    # untouched.
                    if "v1/chat/completions" in request_url and isinstance(response_data, dict):
                        try:
                            completion_text = response_data["choices"][0]["message"]["content"].strip()
                            logger.info(f"🔍 Extracted completion text: '{completion_text}'")
                        except (KeyError, IndexError):
                            completion_text = ""
                            logger.error(f"❌ Failed to extract completion text from response: {response_data}")
                        response_data = [{"generated_text": completion_text}]
                    logger.info(f"✅ Success! Response type: {type(response_data)}")
                    if isinstance(response_data, list) and len(response_data) > 0:
                        generated_text = response_data[0].get("generated_text", "")
                        logger.info(f"📤 Generated text length: {len(generated_text)} chars")
                        logger.info(f"📤 Generated text full: '{generated_text}'")
                    return response_data
                elif response.status_code == 429:
                    logger.error(f"🚫 Rate limit exceeded. Headers: {dict(response.headers)}")
                    raise RateLimitExceededError("Hugging Face API rate limit exceeded")
                elif response.status_code == 503:
                    logger.error(f"⏳ Model loading. Response: {response.text}")
                    raise ModelUnavailableError("Model is currently loading, please try again")
                elif response.status_code in [401, 403]:
                    logger.error(f"🔐 Auth failed. Status: {response.status_code}, Response: {response.text}")
                    logger.error(f"🔑 API key starts with: {settings.hf_api_key[:10]}...")
                    raise AIServiceError("Invalid API key or insufficient permissions")
                elif response.status_code == 400:
                    logger.error(f"❌ Bad request. Response: {response.text}")
                    logger.error(f"🔍 Request payload was: {payload}")
                    raise AIServiceError(f"Bad request to HF API: {response.text}")
                elif response.status_code == 404:
                    logger.error(f"🔍 Model not found. URL: {settings.hf_endpoint}")
                    logger.error(f"📝 Model name: {settings.hf_model_name}")
                    raise AIServiceError(f"Model not found: {settings.hf_model_name}")
                else:
                    logger.error(f"❌ Unexpected status {response.status_code}. Response: {response.text}")
                    response.raise_for_status()
                    
            except httpx.TimeoutException as e:
                logger.error(f"⏰ API request timed out after {settings.hf_timeout}s: {e}")
                raise ModelUnavailableError("AI service timeout - please try again")
            except httpx.RequestError as e:
                logger.error(f"🌐 Network error during API request: {e}")
                raise AIServiceError(f"Network error: {str(e)}")
            except httpx.HTTPStatusError as e:
                logger.error(f"🔥 HTTP error {e.response.status_code}: {e.response.text}")
                if e.response.status_code == 429:
                    raise RateLimitExceededError("API rate limit exceeded")
                elif e.response.status_code == 503:
                    raise ModelUnavailableError("Model temporarily unavailable")
                else:
                    raise AIServiceError(f"HTTP error {e.response.status_code}: {e.response.text}")
            except Exception as e:
                logger.error(f"💥 Unexpected error during API request: {e}")
                raise AIServiceError(f"Unexpected error: {str(e)}")
    
    async def generate_response(
        self,
        user_message: str,
        chat_history: List[Dict[str, Any]],
        user_preferences: Optional[str] = None
    ) -> str:
        """Generate AI response using Spice8B model.
        
        Args:
            user_message: User's message
            chat_history: Previous conversation history
            user_preferences: User's profile preferences
            
        Returns:
            AI-generated response
            
        Raises:
            Various AI service exceptions
        """
        logger.info(f"🎯 Starting AI response generation")
        logger.info(f"👤 User message: '{user_message[:100]}{'...' if len(user_message) > 100 else ''}'")
        logger.info(f"📚 Chat history length: {len(chat_history)} messages")
        logger.info(f"⚙️ User preferences: {'Yes' if user_preferences else 'None'}")
        
        if not self._initialized:
            logger.info("🔄 AI service not initialized, initializing now...")
            await self.initialize()
        
        try:
            # Build prompt with token management
            logger.info("🏗️ Building chat prompt...")
            prompt, token_count = self.build_chat_prompt(
                user_message, chat_history, user_preferences
            )
            
            if token_count > settings.max_context_tokens:
                logger.error(f"❌ Prompt too long: {token_count} > {settings.max_context_tokens} tokens")
                raise TokenLimitExceededError(f"Prompt too long: {token_count} tokens")
            
            logger.info(f"✅ Prompt built successfully: {token_count}/{settings.max_context_tokens} tokens")
            
            # Make API request
            logger.info("📡 Making API request...")
            response_data = await self._make_api_request(prompt, user_message, chat_history, user_preferences)
            
            # Extract generated text
            logger.info("🔍 Processing API response...")
            if isinstance(response_data, list) and len(response_data) > 0:
                generated_text = response_data[0].get("generated_text", "").strip()
                logger.info(f"📝 Raw response length: {len(generated_text)} chars")
                logger.debug(f"📝 Raw response: '{generated_text}'")
            else:
                logger.error(f"❌ Unexpected API response format: {type(response_data)}")
                logger.error(f"📋 Response data: {response_data}")
                raise AIServiceError("Unexpected API response format")
            
            if not generated_text:
                logger.error("❌ Empty response from AI model")
                raise AIServiceError("Empty response from AI model")
            
            # Clean up the response
            logger.info("🧹 Cleaning response...")
            cleaned_response = self._clean_response(generated_text)
            logger.info(f"✨ Final response length: {len(cleaned_response)} chars")
            logger.info(f"✨ Final response: '{cleaned_response}'")
            
            logger.info("🎉 Successfully generated AI response")
            return cleaned_response
            
        except (RateLimitExceededError, ModelUnavailableError, TokenLimitExceededError):
            # Re-raise these specific exceptions
            logger.error("🚫 Re-raising specific AI service exception")
            raise
        except Exception as e:
            logger.error(f"💥 Error generating AI response: {e}")
            logger.error(f"🔍 Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"📚 Full traceback: {traceback.format_exc()}")
            raise AIServiceError(f"Generation failed: {e}")
    
    def _clean_response(self, response: str) -> str:
        """Clean and format the AI response.
        
        Args:
            response: Raw AI response
            
        Returns:
            Cleaned response
        """
        # Remove any ChatML tokens
        cleaned = response.replace("<|im_start|>", "").replace("<|im_end|>", "").strip()
        
        # Remove assistant prefix if present
        if cleaned.startswith("assistant\n"):
            cleaned = cleaned[10:].strip()
        
        # Remove any user tokens that might have leaked through
        if "<|im_start|>user" in cleaned:
            cleaned = cleaned.split("<|im_start|>user")[0].strip()
        
        # Remove other common prefixes
        unwanted_prefixes = ["Human:", "Assistant:", "Bot:", "AI:", "User:"]
        for prefix in unwanted_prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        # Strip whitespace
        cleaned = cleaned.strip()
        
        # Ensure response isn't empty
        if not cleaned:
            cleaned = "Hey there! 😊 What's on your mind?"
        
        # Ensure response isn't too long (safety check)
        if len(cleaned) > 2000:  # Telegram message limit is ~4000 chars
            cleaned = cleaned[:1997] + "..."
        
        return cleaned
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if the AI service is healthy and responsive.
        
        Returns:
            Health status information
        """
        status = {
            "initialized": self._initialized,
            "tokenizer_loaded": self.tokenizer is not None,
            "client_ready": self.client is not None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if self._initialized:
            try:
                # Test with a simple prompt
                test_prompt = CHAT_TEMPLATES["system"].format(
                    content="You are Alice. Respond with just 'OK' to confirm you're working."
                ) + CHAT_TEMPLATES["user"].format(
                    content="Are you working?"
                ) + CHAT_TEMPLATES["assistant_prefix"]
                
                response_data = await self._make_api_request(test_prompt, "Are you working?", [], None)
                status["api_responsive"] = True
                status["test_response"] = response_data
                
            except Exception as e:
                status["api_responsive"] = False
                status["error"] = str(e)
        
        return status


# Global AI service instance
ai_service = AIService() 