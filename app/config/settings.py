from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # Neo4j Aura Database
    neo4j_uri: str = Field(..., env="NEO4J_URI")
    neo4j_username: str = Field(..., env="NEO4J_USERNAME")
    neo4j_password: str = Field(..., env="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", env="NEO4J_DATABASE")

    # JWT
    secret_key: str = Field(..., env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="ALGORITHM")
    access_token_expire_minutes: Optional[int] = Field(default=None, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    access_token_expire_days: Optional[int] = Field(default=None, env="ACCESS_TOKEN_EXPIRE_DAYS")
    
    def get_token_expire_minutes(self) -> int:
        """Get token expiration in minutes, prioritizing days if set"""
        if self.access_token_expire_days:
            return self.access_token_expire_days * 24 * 60
        return self.access_token_expire_minutes or 30

    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    debug: bool = Field(default=True, env="DEBUG")

    # Payment
    payment_gateway_url: Optional[str] = Field(default=None, env="PAYMENT_GATEWAY_URL")
    payment_api_key: Optional[str] = Field(default=None, env="PAYMENT_API_KEY")

    # Location
    province_name: str = Field(default="Bongao Province", env="PROVINCE_NAME")
    default_currency: str = Field(default="PHP", env="DEFAULT_CURRENCY")

    # Frontend URL for CORS
    frontend_url: str = Field(default="http://localhost:3000", env="FRONTEND_URL")

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"
    }


settings = Settings()
