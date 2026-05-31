from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_", env_file=".env", extra="ignore")
    HOST: str
    PORT: int
    USER: str
    PASSWORD: str
    NAME: str

    @property
    def DATABASE_URL(self):
        url = f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.NAME}"
        return url


@lru_cache
def get_settings():
    return Settings()  # pyright: ignore


settings = get_settings()
