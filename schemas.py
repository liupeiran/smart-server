# schemas.py
from pydantic import BaseModel, HttpUrl, field_validator


class ShortenRequest(BaseModel):
    long_url: HttpUrl

    @field_validator("long_url", mode="before")
    @classmethod
    def trim_long_url(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ShortenResponse(BaseModel):
    short_url: str