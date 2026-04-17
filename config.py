"""
Application configuration.

Values can be overridden by environment variables.
"""
import os


class Config:
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    MAX_CONTENT_LENGTH: int = int(os.environ.get("MAX_UPLOAD_MB", "32")) * 1024 * 1024
    REPO_PATH: str = os.environ.get("REPO_PATH", ".")
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "0") == "1"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


_config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(env: str = "default"):
    return _config_map.get(env, DevelopmentConfig)
