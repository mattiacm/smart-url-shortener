from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator


class ShortenRequest(BaseModel):
    url: HttpUrl
    alias: Optional[str] = None          # custom short code, optional
    ttl_days: Optional[int] = None       # override default TTL

    @field_validator("alias")
    @classmethod
    def alias_alphanumeric(cls, v):
        if v and not v.isalnum():
            raise ValueError("alias must be alphanumeric")
        if v and len(v) > 20:
            raise ValueError("alias must be 20 chars or less")
        return v

    @field_validator("ttl_days")
    @classmethod
    def ttl_positive(cls, v):
        if v is not None and v < 1:
            raise ValueError("ttl_days must be at least 1")
        return v


class ShortenResponse(BaseModel):
    short_url: str
    original_url: str
    code: str
    expires_at: datetime
    created_at: datetime
