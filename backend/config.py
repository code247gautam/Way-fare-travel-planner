"""Wayfare AI Travel Planner – configuration loader."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings read from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM provider: "gemini" or "watsonx"
    llm_provider: str = "gemini"

    # Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"

    # IBM watsonx.ai (used when llm_provider=watsonx)
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    watsonx_api_key: str = ""
    watsonx_project_id: str = ""
    granite_model_id: str = "ibm/granite-3-8b-instruct"

    # IBM Cloudant
    cloudant_url: str = ""
    cloudant_api_key: str = ""

    # IBM COS
    cos_api_key: str = ""
    cos_instance_crn: str = ""
    cos_endpoint: str = ""
    cos_bucket: str = "wayfare-exports"

    # IBM App ID
    appid_tenant_id: str = ""
    appid_client_id: str = ""
    appid_secret: str = ""
    appid_region: str = "us-south"

    # Live provider flags
    use_live_railradar: bool = False
    use_live_weather: bool = False
    use_live_geoapify: bool = False
    use_live_fx: bool = False
    use_live_aviationstack: bool = False
    use_live_airbnb: bool = False

    # Third-party keys
    railradar_token: str = ""
    openweather_api_key: str = ""
    geoapify_api_key: str = ""
    exchange_rate_api_key: str = ""
    aviationstack_api_key: str = ""
    rapidapi_key: str = ""

    # App
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
