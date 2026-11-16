from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdamVacationsModel(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)


class AdamVacationsCustomer(AdamVacationsModel):
    name: str = ""
    email: str | None = None
    mobile: str | None = None
    country_code: str = "+91"
    preferred_language: str | None = None
    whatsapp_opt_in: bool | None = None
    email_opt_in: bool | None = None


class AdamVacationsCartLine(AdamVacationsModel):
    sku: str
    category: Literal["flight", "hotel", "package", "activity", "transfer", "insurance"]
    label: str
    qty: int = Field(default=1, ge=1)
    price: float = Field(ge=0)
    discount: float = Field(default=0, ge=0)
    start_date: str | None = None
    end_date: str | None = None
    details: dict[str, str | int | float | bool] = Field(default_factory=dict)


class AdamVacationsCartWebhook(AdamVacationsModel):
    cart_id: str
    session_id: str | None = None
    customer: AdamVacationsCustomer
    lines: list[AdamVacationsCartLine] = Field(default_factory=list)
    currency: str = "INR"
    discount_total: float = 0
    cart_value: float
    journey_status: Literal["initiated", "in_progress", "abandoned"] = "abandoned"
    payment_status: Literal["not_started", "initiated", "failed", "successful"] = "not_started"
    last_page: str | None = None
    deeplink_token: str | None = None
    created_at: str
    abandoned_at: str | None = None
    campaign: str | None = None
    is_test: bool = False


class AdamVacationsEventWebhook(AdamVacationsModel):
    event_id: str
    event: str
    cart_id: str
    booking_ref: str | None = None
    txn_id: str | None = None
    amount_paid: float | None = None
    currency: str | None = None
    occurred_at: str
