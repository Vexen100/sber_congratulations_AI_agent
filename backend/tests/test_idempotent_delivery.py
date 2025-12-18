from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db.models import Client, Delivery, Event, Greeting
from app.services.sender import send_greeting_file


async def test_file_sender_is_idempotent(db_session, tmp_path):
    c = Client(
        first_name="А",
        last_name="Б",
        segment="standard",
        email="ab@example.com",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    ev = Event(client_id=c.id, event_type="manual", event_date=dt.date.today(), title="Тест")
    db_session.add(ev)
    await db_session.commit()
    await db_session.refresh(ev)

    g = Greeting(
        event_id=ev.id,
        client_id=c.id,
        tone="warm",
        subject="Subj",
        body="Body",
        image_path=None,
        status="generated",
    )
    db_session.add(g)
    await db_session.commit()
    await db_session.refresh(g)

    outbox = tmp_path / "outbox"
    d1 = await send_greeting_file(db_session, greeting=g, recipient=c.email, outbox_dir=outbox)
    d2 = await send_greeting_file(db_session, greeting=g, recipient=c.email, outbox_dir=outbox)

    assert d1.id == d2.id
    assert d1.idempotency_key == d2.idempotency_key
    assert (await db_session.execute(select(Delivery))).scalars().all()
