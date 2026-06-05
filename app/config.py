"""Load environment variables and expose typed settings."""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_mode: str = Field("research", env="APP_MODE")
    simple_mode: bool = Field(True, env="SIMPLE_MODE")
    live_trading_enabled: bool = Field(False, env="LIVE_TRADING_ENABLED")
    compliance_approved: bool = Field(False, env="COMPLIANCE_APPROVED")

    # Risk limits
    max_position_size_pct: float = Field(0.01, env="MAX_POSITION_SIZE_PCT")
    max_market_exposure_pct: float = Field(0.05, env="MAX_MARKET_EXPOSURE_PCT")
    max_sector_exposure_pct: float = Field(0.20, env="MAX_SECTOR_EXPOSURE_PCT")
    max_daily_loss_pct: float = Field(0.03, env="MAX_DAILY_LOSS_PCT")
    max_weekly_loss_pct: float = Field(0.07, env="MAX_WEEKLY_LOSS_PCT")
    max_open_positions: int = Field(20, env="MAX_OPEN_POSITIONS")
    min_edge: float = Field(0.07, env="MIN_EDGE")
    min_liquidity: float = Field(1000.0, env="MIN_LIQUIDITY")
    max_spread: float = Field(0.05, env="MAX_SPREAD")
    min_resolution_source_score: float = Field(0.40, env="MIN_RESOLUTION_SOURCE_SCORE")

    # External APIs
    binance_api_key: str = Field("", env="BINANCE_API_KEY")
    binance_api_secret: str = Field("", env="BINANCE_API_SECRET")
    coingecko_api_key: str = Field("", env="COINGECKO_API_KEY")
    cryptopanic_api_key: str = Field("", env="CRYPTOPANIC_API_KEY")
    openai_api_key: str = Field("", env="OPENAI_API_KEY")
    ai_scoring_enabled: bool = Field(True, env="AI_SCORING_ENABLED")

    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_to_file: bool = Field(True, env="LOG_TO_FILE")
    log_file_path: str = Field("logs/bot.log", env="LOG_FILE_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
