from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Neo4j 配置
    NEO4J_URI: str = "NEO4J_URI"
    NEO4J_USER: str = "NEO4J_USER"
    NEO4J_PASSWORD: str = "NEO4J_PASSWORD"

    # 阿里云百炼 API 配置
    OPENAI_API_KEY: str = "OPENAI_API_KEY"
    OPENAI_BASE_URL: str = "OPENAI_BASE_URL"
    

    # 应用配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False

settings = Settings()