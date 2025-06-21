"""Independent webhook settings configuration."""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WebhookSettings(BaseSettings):
    """Settings for webhook service only."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Database settings
    database_url: str = Field(
        description="PostgreSQL connection URL"
    )
    
    # Redis settings  
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    
    # Lava.top payment settings
    lava_api_key: str = Field(
        description="Lava.top API key"
    )
    
    lava_shop_id: str = Field(
        description="Lava.top shop ID"
    )
    
    lava_webhook_secret: str = Field(
        description="Lava.top webhook secret for signature verification"
    )
    
    lava_api_url: str = Field(
        default="https://gate.lava.top",
        description="Lava.top API base URL"
    )
    
    lava_webhook_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for Lava.top callbacks"
    )
    
    # Webhook security
    webhook_username: str = Field(
        default="lava_webhook_user",
        description="Basic Auth username for webhook security"
    )
    
    webhook_password: str = Field(
        default="secure_webhook_password_2024", 
        description="Basic Auth password for webhook security"
    )
    
    # Bot settings
    bot_name: str = Field(
        default="ai-girlfriend",
        description="Bot name for payment identification"
    )
    
    # Debug mode
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )


# Global webhook settings instance
webhook_settings = WebhookSettings()

def get_webhook_settings() -> WebhookSettings:
    """Get the global webhook settings instance."""
    return webhook_settings 