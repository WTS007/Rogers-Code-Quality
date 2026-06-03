"""
Application Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~
Environment-aware configuration classes for the Nexus Demo API.
"""

import os


class Config:
    """Base configuration with sensible defaults."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "nexus-demo-secret-key-change-in-production")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "nexus_demo.db")
    TOKEN_EXPIRY_HOURS = int(os.environ.get("TOKEN_EXPIRY_HOURS", "24"))
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    """Development environment — verbose logging, debug mode."""

    DEBUG = True
    LOG_LEVEL = "DEBUG"
    DATABASE_PATH = "nexus_dev.db"


class ProductionConfig(Config):
    """Production environment — strict settings."""

    DEBUG = False
    LOG_LEVEL = "WARNING"
    SECRET_KEY = os.environ.get("SECRET_KEY")  # Must be set via env

    def __init__(self):
        if not self.SECRET_KEY:
            raise EnvironmentError(
                "SECRET_KEY environment variable is required in production"
            )


class TestConfig(Config):
    """Test environment — temporary database."""

    TESTING = True
    DATABASE_PATH = "nexus_test.db"
    LOG_LEVEL = "DEBUG"
    TOKEN_EXPIRY_HOURS = 1


def get_config(env: str = None) -> Config:
    """Factory function to retrieve environment-specific configuration.

    Args:
        env: One of 'development', 'production', 'testing'.
             Defaults to APP_ENV environment variable, then 'development'.

    Returns:
        Config instance for the requested environment.
    """
    env = env or os.environ.get("APP_ENV", "development")
    configs = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestConfig,
    }
    config_class = configs.get(env.lower(), DevelopmentConfig)
    return config_class()
