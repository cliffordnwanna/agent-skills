"""Explicit judge and price settings; no embedded keys or assumed model prices."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Price(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_usd_per_million: Decimal = Field(ge=0, allow_inf_nan=False)
    output_usd_per_million: Decimal = Field(ge=0, allow_inf_nan=False)
    source_url: str
    checked_on: date

    @field_validator("source_url")
    @classmethod
    def validate_source(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("Price source must be an HTTPS reference")
        return value

    @field_validator("checked_on")
    @classmethod
    def validate_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Price verification date cannot be in the future")
        return value

    def cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        return (
            input_tokens * self.input_usd_per_million + output_tokens * self.output_usd_per_million
        ) / Decimal(1_000_000)


class JudgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1, max_length=150, pattern=r"^[A-Za-z0-9._:-]+$")
    price: Price
    input_token_cap: int = Field(default=20000, ge=1024, le=100000)
    max_output_tokens: int = Field(default=1024, ge=128, le=8192)
    max_calls: int = Field(default=100, ge=1, le=1000)
    timeout_seconds: float = Field(default=30, ge=1, le=120, allow_inf_nan=False)

    @classmethod
    def from_path(cls, path: Path) -> "JudgeConfig":
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
