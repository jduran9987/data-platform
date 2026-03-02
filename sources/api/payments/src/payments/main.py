"""FastAPI app exposing three third-party payments endpoints.

Endpoints:
- GET /accounts
- GET /charges
- GET /refunds

Each endpoint can:
- create new objects (new=N)
- emit update events for existing objects (updates=N)
- return events since a timestamp (since=ISO datetime)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, Query
from sqlmodel import Session, select

from payments.db import create_db_and_tables, get_session
from payments.generator import (
    emit_account_events,
    emit_charge_events,
    emit_refund_events,
    now_utc,
)
from payments.models import AccountEvent, ChargeEvent, RefundEvent

app = FastAPI(title="Payments API Generator", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    """Create database tables on startup."""
    create_db_and_tables()


def _iso(ts: datetime) -> str:
    """Format timestamps as ISO-8601 Zulu."""
    return ts.isoformat().replace("+00:00", "Z")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/accounts")
def get_accounts(
    new: int = Query(0, ge=0, le=2000),
    updates: int = Query(0, ge=0, le=2000),
    since: datetime | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return account payload events (optionally generating new/updates first)."""
    ts = now_utc()
    inserted, updated = (
        emit_account_events(session, new=new, updates=updates, ts=ts)
        if (new or updates)
        else (0, 0)
    )

    stmt = select(AccountEvent)
    if since is not None:
        stmt = stmt.where(AccountEvent.source_event_ts_utc > since)
    stmt = stmt.order_by(AccountEvent.source_event_ts_utc, AccountEvent.event_id).limit(
        limit
    )
    rows = session.exec(stmt).all()

    return {
        "requested_at_utc": _iso(ts),
        "inserted": inserted,
        "updated": updated,
        "count": len(rows),
        "data": [r.payload for r in rows],
    }


@app.get("/charges")
def get_charges(
    new: int = Query(0, ge=0, le=5000),
    updates: int = Query(0, ge=0, le=5000),
    since: datetime | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return charge payload events (optionally generating new/updates first)."""
    ts = now_utc()
    inserted, updated = (
        emit_charge_events(session, new=new, updates=updates, ts=ts)
        if (new or updates)
        else (0, 0)
    )

    stmt = select(ChargeEvent)
    if since is not None:
        stmt = stmt.where(ChargeEvent.source_event_ts_utc > since)
    stmt = stmt.order_by(ChargeEvent.source_event_ts_utc, ChargeEvent.event_id).limit(
        limit
    )
    rows = session.exec(stmt).all()

    return {
        "requested_at_utc": _iso(ts),
        "inserted": inserted,
        "updated": updated,
        "count": len(rows),
        "data": [r.payload for r in rows],
    }


@app.get("/refunds")
def get_refunds(
    new: int = Query(0, ge=0, le=5000),
    updates: int = Query(0, ge=0, le=5000),
    since: datetime | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return refund payload events (optionally generating new/updates first)."""
    ts = now_utc()
    inserted, updated = (
        emit_refund_events(session, new=new, updates=updates, ts=ts)
        if (new or updates)
        else (0, 0)
    )

    stmt = select(RefundEvent)
    if since is not None:
        stmt = stmt.where(RefundEvent.source_event_ts_utc > since)
    stmt = stmt.order_by(RefundEvent.source_event_ts_utc, RefundEvent.event_id).limit(
        limit
    )
    rows = session.exec(stmt).all()

    return {
        "requested_at_utc": _iso(ts),
        "inserted": inserted,
        "updated": updated,
        "count": len(rows),
        "data": [r.payload for r in rows],
    }
