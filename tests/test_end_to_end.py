import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"


@pytest.fixture(scope="module")
def platform(tmp_path_factory):
    pgserver = pytest.importorskip("pgserver")
    import psycopg

    server = pgserver.get_server(str(tmp_path_factory.mktemp("pg")), cleanup_mode="stop")
    with psycopg.connect(server.get_uri(), autocommit=True) as conn:
        conn.execute("DROP DATABASE IF EXISTS adam_e2e")
        conn.execute("CREATE DATABASE adam_e2e")
    os.environ.update({
        "DATABASE_URL": server.get_uri().replace("/postgres?", "/adam_e2e?"),
        "USE_DB": "false",
        "DASHBOARD_API_ENCRYPTION": "off",
        "ADAM_VACATIONS_CART_TOKEN": "cart-token",
        "ADAM_VACATIONS_EVENTS_TOKEN": "events-token",
        "MAX_CONTACTS_PER_DAY": "0",
    })
    from pw_channel.runner import _load

    _load(str(ROOT / "pw.toml"), None)
    from pw_channel.bootstrap import prepare

    prepare()
    from pw_channel.db.core import init_database
    from pw_channel.intake import intakes
    from pw_sdk import config

    init_database()
    intakes.sync_from_config(config.current().intakes)
    yield
    server.cleanup()


class Recorder:
    def __init__(self, name, waiting=True):
        self.name = name
        self.waiting = waiting
        self.tasks = []

    def supports(self, action):
        return True

    async def execute(self, task):
        from pw_channel.core.channel import ChannelResult
        from pw_sdk.contracts.outcomes import TaskOutcome

        self.tasks.append(task)
        ref = f"{self.name}-{task.task_id}-{len(self.tasks)}"
        return ChannelResult.waiting(ref, outcome=None if self.name == "voice" else TaskOutcome.SENT)

    async def startup(self):
        return None

    async def shutdown(self):
        return None

    def routes(self):
        return []


def statuses(journey_id):
    from pw_channel.db.core import connection

    with connection() as conn:
        rows = conn.execute("SELECT key, status, outcome FROM journey_tasks WHERE journey_id = %s", (journey_id,)).fetchall()
        journey = conn.execute("SELECT status FROM journeys WHERE id = %s", (journey_id,)).fetchone()["status"]
    return journey, {row["key"]: (row["status"], row["outcome"]) for row in rows}


def test_adam_cart_recovery_end_to_end(platform):
    from fastapi.testclient import TestClient

    from pw_channel.app import create_app
    from pw_channel.core import registry
    from pw_channel.orchestrator import service
    from pw_channel.orchestrator.worker import Worker

    registry.reset()
    channels = {name: Recorder(name) for name in ("voice", "whatsapp", "email")}
    for channel in channels.values():
        registry.register(channel)
    client = TestClient(create_app())

    cart = json.loads((FIXTURES / "adam_vacations.cart" / "cart_abandoned.json").read_text())
    response = client.post("/api/intake/adam_vacations_cart/records", json=cart, headers={"Authorization": "Bearer cart-token"})
    assert response.status_code == 202, response.text
    result = response.json()["results"][0]
    journey_id = result["journey_id"]
    start = datetime.fromisoformat(result["scheduled_for"])

    worker = Worker(poll_secs=0.01)
    day = start.replace(hour=6, minute=0) if start.astimezone(timezone(timedelta(hours=5, minutes=30))).hour < 9 else start
    asyncio.run(worker.tick(day))
    journey, state = statuses(journey_id)
    assert state["whatsapp_reminder"] == ("waiting", "sent")
    assert channels["whatsapp"].tasks[0].record.journey.resume_url.startswith("https://www.adamvacations.example/resume/")

    asyncio.run(worker.tick(day + timedelta(minutes=31)))
    journey, state = statuses(journey_id)
    assert state["whatsapp_reminder"][1] == "no_response" and state["recovery_call"][0] == "waiting"
    assert channels["voice"].tasks[0].record.customer.phone == "+919812345678"

    events = json.loads((FIXTURES / "adam_vacations.events" / "events.json").read_text())
    response = client.post("/api/intake/adam_vacations_events/events", json=events, headers={"Authorization": "Bearer events-token"})
    assert response.status_code == 202, response.text
    assert [r["status"] for r in response.json()["results"]] == ["scheduled", "scheduled", "rejected"]
    service.process_events()
    journey, state = statuses(journey_id)
    assert journey == "converted"
    assert state["recovery_call"][0] == "cancelled" and state["email_followup"][0] == "cancelled"
