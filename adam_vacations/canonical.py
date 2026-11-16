from pydantic import BaseModel

from adam_vacations.payload import AdamVacationsCartLine, AdamVacationsCartWebhook
from pw_sdk import EventKind, Stage

ADAM_VACATIONS_PAGE_STAGE = {
    "search": Stage.BROWSE,
    "listing": Stage.BROWSE,
    "details": Stage.PRODUCT_VIEW,
    "cart": Stage.CART,
    "traveller_details": Stage.CHECKOUT,
    "review": Stage.CHECKOUT,
    "payment": Stage.PAYMENT_PENDING,
}

ADAM_VACATIONS_EVENT_MAP = {
    "journey_initiated": EventKind.JOURNEY_INITIATED,
    "journey_in_progress": EventKind.JOURNEY_IN_PROGRESS,
    "journey_abandoned": EventKind.JOURNEY_ABANDONED,
    "payment_initiated": EventKind.PAYMENT_INITIATED,
    "payment_success": EventKind.PAYMENT_SUCCEEDED,
    "payment_failed": EventKind.PAYMENT_FAILED,
    "booking_confirmed": EventKind.BOOKING_CONFIRMED,
}


class AdamVacationsFlightAttributes(BaseModel):
    origin: str
    destination: str
    airline: str | None = None
    cabin: str | None = None
    passengers: int | None = None
    trip_type: str | None = None


class AdamVacationsHotelAttributes(BaseModel):
    city: str
    hotel: str | None = None
    rooms: int | None = None
    nights: int | None = None
    guests: int | None = None


ADAM_VACATIONS_ATTRIBUTES = {"flight": AdamVacationsFlightAttributes, "hotel": AdamVacationsHotelAttributes}


def adam_vacations_stage(cart: AdamVacationsCartWebhook) -> Stage:
    if cart.payment_status == "failed":
        return Stage.PAYMENT_FAILED
    if cart.payment_status == "initiated":
        return Stage.PAYMENT_PENDING
    return ADAM_VACATIONS_PAGE_STAGE.get((cart.last_page or "").lower(), Stage.CART)


def adam_vacations_attributes(line: AdamVacationsCartLine) -> dict:
    model = ADAM_VACATIONS_ATTRIBUTES.get(line.category)
    if model is None:
        return dict(line.details)
    return model.model_validate(line.details).model_dump(exclude_none=True)


def adam_vacations_summary(cart: AdamVacationsCartWebhook) -> str:
    titles = [line.label for line in cart.lines[:2]]
    if len(cart.lines) > 2:
        titles.append(f"{len(cart.lines) - 2} more item(s)")
    return ", ".join(titles)


def adam_vacations_resume_url(base_url: str, cart: AdamVacationsCartWebhook) -> str | None:
    if not base_url:
        return None
    token = cart.deeplink_token or cart.cart_id
    return f"{base_url.rstrip('/')}/{token}?utm_source=pw&utm_medium=recovery"
