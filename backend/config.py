import os
import logging
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger(__name__)

_INSECURE_JWT_SECRETS = {
    "change-this-secret-in-production",
    "your_jwt_secret_key_change_this_in_production",
}
_INSECURE_ADMIN_PASSWORDS = {
    "change-this-admin-password",
    "change-this-analyst-password",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(_BACKEND_DIR, ".env"),
        env_file_encoding="utf-8",
    )

    app_name: str = "AI Commerce Intelligence Platform"
    app_version: str = "1.7.0"
    debug: bool = False

    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "ai_commerce_intelligence_platform"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 3600

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    redis_enabled: bool = False

    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    admin_username: str = "admin"
    admin_password: str = ""
    analyst_username: str = "analyst"
    analyst_password: str = ""

    cors_origins: list[str] = Field(default_factory=lambda: [
        "http://localhost:8501",
        "http://localhost:8502",
        "http://localhost:8505",
        "http://localhost:8000",
    ])
    trust_proxy_headers: bool = False

    default_page_size: int = 20
    max_page_size: int = 100

    cache_ttl_seconds: int = 300

    def model_post_init(self, __context) -> None:
        if not self.jwt_secret:
            if self.debug:
                self.jwt_secret = "dev-only-insecure-secret-do-not-use-in-production"
                logger.warning("⚠️ JWT_SECRET 未设置，使用开发模式默认密钥，请勿用于生产环境！")
            else:
                raise ValueError("生产环境必须设置 JWT_SECRET 环境变量！")
        if not self.admin_password:
            if self.debug:
                self.admin_password = "admin123"
                logger.warning("开发模式未设置 ADMIN_PASSWORD，使用本地默认密码")
            else:
                raise ValueError("生产环境必须设置 ADMIN_PASSWORD 环境变量！")
        if not self.debug:
            if self.jwt_secret in _INSECURE_JWT_SECRETS or len(self.jwt_secret) < 32:
                raise ValueError("生产环境 JWT_SECRET 至少需要 32 位且不能使用示例值！")
            if (
                self.admin_password in _INSECURE_ADMIN_PASSWORDS
                or len(self.admin_password) < 12
            ):
                raise ValueError("生产环境 ADMIN_PASSWORD 至少需要 12 位且不能使用示例值！")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

    @property
    def async_database_url(self) -> str:
        return (
            f"mysql+aiomysql://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
