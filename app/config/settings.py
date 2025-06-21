"""Application settings using Pydantic BaseSettings."""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings."""
    
    # Telegram Bot Configuration
    telegram_token: str = Field(..., description="Telegram Bot API token")
    
    # Hugging Face Configuration
    hf_endpoint: str = Field(..., description="Hugging Face inference endpoint URL")
    hf_api_key: str = Field(..., description="Hugging Face API key")
    hf_model_name: str = Field(default="bartowski/L3-TheSpice-8b-v0.8.3-GGUF", description="Hugging Face model name")
    
    # AI Generation Parameters - Aggressive Anti-Repetition & High Creativity
    hf_max_tokens: int = Field(default=512, description="Max tokens to generate")
    hf_temperature: float = Field(default=1.2, description="High temperature for maximum creativity (0.1-2.0)")
    hf_top_p: float = Field(default=0.75, description="Lower top-p to force more diverse choices (0.1-1.0)")
    hf_top_k: int = Field(default=80, description="Higher top-k for maximum vocabulary diversity")
    hf_repetition_penalty: float = Field(default=1.25, description="Strong repetition penalty to prevent loops (1.0-2.0)")
    hf_frequency_penalty: float = Field(default=0.6, description="High frequency penalty - heavily penalize repeated tokens (0.0-2.0)")
    hf_presence_penalty: float = Field(default=0.4, description="High presence penalty - force new topics (0.0-2.0)")
    hf_no_repeat_ngram_size: int = Field(default=4, description="Prevent 4-gram repetition for phrase diversity (0=off, 2-5=optimal)")
    hf_do_sample: bool = Field(default=True, description="Enable sampling for creativity")
    hf_min_p: float = Field(default=0.02, description="Lower min_p for more token diversity (0.0-1.0)")
    
    # API Configuration
    hf_timeout: int = Field(default=30, description="API request timeout in seconds")
    hf_max_retries: int = Field(default=3, description="Max API retry attempts")
    hf_retry_delay: float = Field(default=1.0, description="Delay between retries in seconds")
    
    # Database Configuration
    database_url: str = Field(..., description="PostgreSQL database URL")
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    
    # Bot Configuration
    schedule_timezone: str = Field(default="Europe/Kyiv", description="Timezone for scheduling")
    free_daily_loans: int = Field(default=10, description="Free loans given daily")
    rate_limit_per_user_sec: int = Field(default=3, description="Rate limit per user in seconds")
    hf_max_rps: int = Field(default=5, description="Max requests per second to Hugging Face")
    
    # Token and Context Management
    max_context_tokens: int = Field(default=8000, description="Maximum context tokens for Spice8B")
    
    # Development Settings
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Webhook Configuration
    webhook_host: str = Field(default="0.0.0.0", description="Webhook host")
    webhook_port: int = Field(default=8000, description="Webhook port")
    webhook_path: str = Field(default="/webhook", description="Webhook path")
    webhook_url: Optional[str] = Field(default=None, description="External webhook URL")
    
    # Security
    webhook_secret: Optional[str] = Field(default=None, description="Webhook secret token")
    
    # Lava.top Payment Configuration
    lava_api_key: Optional[str] = Field(default=None, description="Lava.top API key")
    lava_shop_id: Optional[str] = Field(default=None, description="Lava.top shop ID")
    lava_api_url: str = Field(default="https://gate.lava.top", description="Lava.top API base URL")
    lava_webhook_secret: Optional[str] = Field(default=None, description="Lava.top webhook secret for signature verification")
    lava_webhook_url: Optional[str] = Field(default=None, description="Webhook URL for payment notifications")
    bot_name: str = Field(default="ai-girlfriend", description="Bot name for payment tracking")
    
    # Payment Packages Configuration
    payment_packages: dict = Field(
        default={
            "100": {"tokens": 100, "eur": 5.00, "usd": 6.00, "rub": 500.00},
            "200": {"tokens": 200, "eur": 8.00, "usd": 9.00, "rub": 800.00},
            "300": {"tokens": 300, "eur": 12.00, "usd": 13.00, "rub": 1000.00}
        },
        description="Available payment packages with pricing"
    )
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings 