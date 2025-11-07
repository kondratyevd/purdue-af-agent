import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Read from environment variables (docker-compose takes precedence)
    # Defaults are fallbacks if env vars not set
    openai_base_url: str = os.getenv(
        "OPENAI_BASE_URL", "https://genai.rcac.purdue.edu/api"
    )
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-oss:120b")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    timezone: str = os.getenv(
        "TIMEZONE", "US/Eastern"
    )  # Timezone for datetime operations
    max_tool_iterations: int = int(os.getenv("MAX_TOOL_ITERATIONS", "10"))

    class Config:
        env_file = ".env"
        case_sensitive = False
        # Allow reading from environment variables directly
        env_prefix = ""


settings = Settings()
