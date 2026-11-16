from adam_vacations.canonical import (
    ADAM_VACATIONS_EVENT_MAP,
    adam_vacations_attributes,
    adam_vacations_resume_url,
    adam_vacations_stage,
    adam_vacations_summary,
)
from adam_vacations.payload import AdamVacationsCartWebhook, AdamVacationsEventWebhook
from pw_sdk.utils.phone import to_e164
from pw_sdk import Adapter, AdapterContext, CustomerRecord, OutcomeEvent, RejectItem, SkipItem, map_batch


class AdamVacationsCartAdapter(Adapter):
    name = "adam_vacations.cart"
    version = "0.1.0"

    def transform_records(self, payload, ctx: AdapterContext):
        base_url = ctx.config.get("resume_base_url", "")

        def build(raw, index):
            cart = AdamVacationsCartWebhook.model_validate(raw)
            if cart.is_test:
                raise SkipItem("test cart")
            if cart.payment_status == "successful":
                raise SkipItem("already paid")
            customer = cart.customer
            phone = None
            if customer.mobile:
                phone = to_e164(customer.mobile if customer.mobile.startswith("+") else f"{customer.country_code}{customer.mobile}")
                if phone is None:
                    raise RejectItem(f"mobile {customer.mobile!r} is not a valid number", "customer.mobile")
            return CustomerRecord.model_validate({
                "ref": {
                    "reference_id": cart.cart_id,
                    "occurred_at": self.parse_time(cart.created_at, ctx.timezone),
                    "campaign_id": cart.campaign,
                },
                "customer": {
                    "external_id": cart.session_id,
                    "name": customer.name,
                    "phone": phone,
                    "email": customer.email,
                    "language": customer.preferred_language,
                    "consent": {"whatsapp": customer.whatsapp_opt_in, "email": customer.email_opt_in},
                },
                "journey": {
                    "stage": adam_vacations_stage(cart),
                    "abandoned_at": self.parse_time(cart.abandoned_at, ctx.timezone),
                    "resume_url": adam_vacations_resume_url(base_url, cart),
                },
                "cart": {
                    "currency": cart.currency,
                    "total": cart.cart_value,
                    "discount": cart.discount_total,
                    "items": [
                        {
                            "item_id": line.sku,
                            "type": line.category,
                            "title": line.label,
                            "quantity": line.qty,
                            "unit_price": line.price,
                            "total": max(line.price * line.qty - line.discount, 0),
                            "starts_at": self.parse_time(line.start_date, ctx.timezone),
                            "ends_at": self.parse_time(line.end_date, ctx.timezone),
                            "attributes": adam_vacations_attributes(line),
                        }
                        for line in cart.lines
                    ],
                },
                "summary": adam_vacations_summary(cart),
                "facts": [
                    {"key": "payment_status", "label": "Payment status", "value": cart.payment_status.replace("_", " ")},
                    {"key": "last_page", "label": "Left on page", "value": cart.last_page or "unknown", "speakable": False},
                ],
            })

        return map_batch(payload, build)


class AdamVacationsEventsAdapter(Adapter):
    name = "adam_vacations.events"
    version = "0.1.0"

    def transform_events(self, payload, ctx: AdapterContext):
        def build(raw, index):
            event = AdamVacationsEventWebhook.model_validate(raw)
            kind = ADAM_VACATIONS_EVENT_MAP.get(event.event)
            if kind is None:
                raise RejectItem(f"unknown event {event.event!r}", "event")
            return OutcomeEvent(
                event_id=event.event_id,
                reference_id=event.cart_id,
                kind=kind,
                occurred_at=self.parse_time(event.occurred_at, ctx.timezone),
                booking_id=event.booking_ref,
                transaction_id=event.txn_id,
                amount=event.amount_paid,
                currency=event.currency,
            )

        return map_batch(payload, build)
