from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Body):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize(cls, v):
        return v.lower()


class Registration(Login):
    name: str = Field(min_length=2, max_length=80)

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Name must contain at least two nonspace characters")
        return value.strip()


class Email(Body):
    email: EmailStr


class Token(Body):
    token: str = Field(min_length=32, max_length=128)


class Reset(Token):
    password: str = Field(min_length=12, max_length=128)


class Profile(Body):
    name: str = Field(min_length=2, max_length=80)

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Name must contain at least two nonspace characters")
        return value.strip()


class Ticket(Body):
    symbol: str
    exchange: Literal["NSE", "BSE"]
    product: Literal["Intraday", "Delivery"]
    side: Literal["BUY", "SELL"]
    quantity: int = Field(strict=True, ge=1, le=1000)
    type: Literal["MARKET", "LIMIT"]
    price: Decimal = Field(ge=0, le=10000000, max_digits=12, decimal_places=2)


class StrategyConfig(Body):
    name: str = Field(min_length=1, max_length=80)
    symbol: str
    quantity: int = Field(strict=True, ge=1, le=1000)
    loss: Decimal = Field(gt=0, le=10000000, max_digits=12, decimal_places=2)
    signal: Literal["EMA crossover", "Opening range", "RSI reversal"]


class Transition(Body):
    status: Literal["Validated", "Tested", "Active", "Paused", "Stopped"]


class UserStatus(Body):
    enabled: bool
