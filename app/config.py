"""Load environment variables and expose typed settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_mode: str = Field("research", validation_alias="APP_MODE")
    simple_mode: bool = Field(True, validation_alias="SIMPLE_MODE")
    live_trading_enabled: bool = Field(False, validation_alias="LIVE_TRADING_ENABLED")
    compliance_approved: bool = Field(False, validation_alias="COMPLIANCE_APPROVED")

    # Risk limits
    max_position_size_pct: float = Field(0.01, validation_alias="MAX_POSITION_SIZE_PCT")
    max_market_exposure_pct: float = Field(0.05, validation_alias="MAX_MARKET_EXPOSURE_PCT")
    max_sector_exposure_pct: float = Field(0.20, validation_alias="MAX_SECTOR_EXPOSURE_PCT")
    max_daily_loss_pct: float = Field(0.03, validation_alias="MAX_DAILY_LOSS_PCT")
    max_weekly_loss_pct: float = Field(0.07, validation_alias="MAX_WEEKLY_LOSS_PCT")
    max_open_positions: int = Field(20, validation_alias="MAX_OPEN_POSITIONS")
    min_edge: float = Field(0.07, validation_alias="MIN_EDGE")
    min_liquidity: float = Field(1000.0, validation_alias="MIN_LIQUIDITY")
    max_spread: float = Field(0.05, validation_alias="MAX_SPREAD")
    min_resolution_source_score: float = Field(0.40, validation_alias="MIN_RESOLUTION_SOURCE_SCORE")

    # External APIs
    binance_api_key: str = Field("", validation_alias="BINANCE_API_KEY")
    binance_api_secret: str = Field("", validation_alias="BINANCE_API_SECRET")
    coingecko_api_key: str = Field("", validation_alias="COINGECKO_API_KEY")
    cryptopanic_api_key: str = Field("", validation_alias="CRYPTOPANIC_API_KEY")
    openai_api_key: str = Field("", validation_alias="OPENAI_API_KEY")
    ai_scoring_enabled: bool = Field(True, validation_alias="AI_SCORING_ENABLED")

    # Logging
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    log_to_file: bool = Field(True, validation_alias="LOG_TO_FILE")
    log_file_path: str = Field("logs/bot.log", validation_alias="LOG_FILE_PATH")


settings = Settings()
