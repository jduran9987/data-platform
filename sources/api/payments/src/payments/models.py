"""SQLModel tables for event-style third-party payments payloads.

We store append-only events with JSONB payloads. This preserves:
- Missing fields (keys omitted)
- Nullable fields (keys present with null)
- Nested structures

These tables are ideal for dbt modeling:
stg_*_events -> int_*_latest (latest per object_id by source_event_ts_utc) -> marts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class AccountEvent(SQLModel, table=True):
    """Raw account payload event emitted by the simulated provider."""

    __tablename__ = "account_events"

    event_id: str = Field(primary_key=True)
    account_id: str = Field(index=True)

    source_event_ts_utc: datetime = Field(index=True)
    created_at_utc: datetime = Field(index=True)

    payload: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))


class ChargeEvent(SQLModel, table=True):
    """Raw charge payload event emitted by the simulated provider."""

    __tablename__ = "charge_events"

    event_id: str = Field(primary_key=True)
    charge_id: str = Field(index=True)

    source_event_ts_utc: datetime = Field(index=True)
    created_at_utc: datetime = Field(index=True)

    payload: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))


class RefundEvent(SQLModel, table=True):
    """Raw refund payload event emitted by the simulated provider."""

    __tablename__ = "refund_events"

    event_id: str = Field(primary_key=True)
    refund_id: str = Field(index=True)

    source_event_ts_utc: datetime = Field(index=True)
    created_at_utc: datetime = Field(index=True)

    payload: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
