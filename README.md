# adam-vacations-adapter

The Adam Vacations install of the PlaceholderWorks platform. This repo is the only code Adam's team owns: it turns Adam's webhooks into standard records and holds Adam's configuration and keys. Everything else comes from one dependency, `pw-sdk[llm,tools,channel]`: the core plus the brain, the tools and the channels (voice, WhatsApp, email, scheduler).

## What is in here

| Path | What it holds |
|---|---|
| `adam_vacations/payload.py` | the shape of Adam's cart and event webhooks |
| `adam_vacations/canonical.py` | Adam-specific mapping: page → journey stage, event names, flight and hotel attributes, resume links |
| `adam_vacations/adapter.py` | `AdamVacationsCartAdapter` (cart → `CustomerRecord`) and `AdamVacationsEventsAdapter` (payment/booking → `OutcomeEvent`) |
| `pw.toml` | providers, branding, message copy, intakes and the recovery journeys |
| `.env.example` | every key and secret, set on Adam's server only |
| `fixtures/` | sample payloads and expected output, checked with `pw-adapter check` |
| `knowledge/` | Adam's knowledge base for the agent |

## Run it

```bash
cp .env.example .env            # fill in keys
uv sync
uv run pw-adapter check fixtures/
uv run adam-vacations check     # validates pw.toml, adapters and journeys
uv run adam-vacations migrate   # creates tables and the two intakes
uv run adam-vacations llm       # brain on :8010
uv run adam-vacations channel   # intake API, webhooks, voice, dashboard on :8420
uv run adam-vacations worker    # journey scheduler
```

## Adam's endpoints

| Adam sends | To |
|---|---|
| abandoned carts | `POST /api/intake/adam_vacations_cart/records` with `Authorization: Bearer $ADAM_VACATIONS_CART_TOKEN` |
| payment and booking events | `POST /api/intake/adam_vacations_events/events` with `Authorization: Bearer $ADAM_VACATIONS_EVENTS_TOKEN` |

## The recovery journey (`pw.toml`)

1. WhatsApp resume link 5 minutes after the cart is abandoned.
2. No reply within 30 minutes → call (one retry after 15 minutes if unanswered).
3. Call not answered → email 2 hours later.

At any time: `booking.confirmed` or `payment.succeeded` stops everything; `payment.failed` starts the `payment_failed` journey; a WhatsApp reply cancels the call; a link click pauses the journey for 30 minutes; opt-out blocks that channel.

## Package sources

Local development uses path sources (`pyproject.toml`). For a release, replace `[tool.uv.sources]` with the block in `release-sources.toml` (git tags). Compiled wheels later only change those sources.
