"""Webhook-specific settings configuration."""

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
        default="https://business.lava.top/api/v1",
        description="Lava.top API base URL"
    )
    
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