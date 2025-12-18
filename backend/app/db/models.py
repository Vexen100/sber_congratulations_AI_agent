from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    position: Mapped[str | None] = mapped_column(String(200), nullable=True)
    segment: Mapped[str] = mapped_column(String(50), default="standard")  # vip|new|loyal|standard

    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    preferred_channel: Mapped[str] = mapped_column(
        String(20), default="email"
    )  # email|sms|messenger

    birth_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    last_interaction_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    events: Mapped[list["Event"]] = relationship(back_populates="client")
    greetings: Mapped[list["Greeting"]] = relationship(back_populates="client")


class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(200))
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    is_business_relevant: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("date", "title", name="uq_holiday_date_title"),)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)

    event_type: Mapped[str] = mapped_column(String(50))  # birthday|holiday|manual
    event_date: Mapped[dt.date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(250))
    # NOTE: "metadata" is a reserved attribute name in SQLAlchemy Declarative.
    # We keep the DB column name as "metadata" for semantics, but expose it as "details" in Python.
    details: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    client: Mapped[Client | None] = relationship(back_populates="events")
    greetings: Mapped[list["Greeting"]] = relationship(back_populates="event")

    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "event_type",
            "event_date",
            "title",
            name="uq_event_client_type_date_title",
        ),
    )


class Greeting(Base):
    __tablename__ = "greetings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)

    tone: Mapped[str] = mapped_column(String(50), default="official")
    subject: Mapped[str] = mapped_column(String(250))
    body: Mapped[str] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="generated")  # generated|sent|error

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    event: Mapped[Event] = relationship(back_populates="greetings")
    client: Mapped[Client | None] = relationship(back_populates="greetings")
    deliveries: Mapped[list["Delivery"]] = relationship(back_populates="greeting")


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    greeting_id: Mapped[int] = mapped_column(ForeignKey("greetings.id"))

    channel: Mapped[str] = mapped_column(String(20))  # email|sms|messenger|file
    recipient: Mapped[str] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(50), default="queued")  # queued|sent|error
    provider_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)

    greeting: Mapped[Greeting] = relationship(back_populates="deliveries")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    greeting_id: Mapped[int] = mapped_column(ForeignKey("greetings.id"))
    outcome: Mapped[str] = mapped_column(
        String(50), default="unknown"
    )  # opened|replied|ignored|unknown
    score: Mapped[int | None] = mapped_column(nullable=True)  # 1..5 (manager's rating)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
