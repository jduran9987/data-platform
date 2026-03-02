"""Generate third-party payments payload events.

We emit JSON payloads where:
- Some keys are missing (not returned)
- Some keys exist but are null (nullable fields)
- Nested JSON varies by payment method type
- Updates are represented as new events for the same object id
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from faker import Faker
from sqlmodel import Session, select

from payments.models import AccountEvent, ChargeEvent, RefundEvent

fake = Faker()

COUNTRIES: list[str] = ["US", "CA", "GB", "DE", "FR", "BR", "AU"]
CURRENCIES_BY_COUNTRY: dict[str, str] = {
    "AU": "AUD",
    "BR": "BRL",
    "CA": "CAD",
    "DE": "EUR",
    "FR": "EUR",
    "GB": "GBP",
    "US": "USD",
}

CHARGE_STATUSES: list[str] = ["succeeded", "pending", "failed"]
REFUND_REASONS: list[str] = [
    "requested_by_customer",
    "duplicate",
    "fraudulent",
    "expired_uncaptured_charge",
]
REFUND_STATUSES: list[str] = ["pending", "succeeded", "failed"]


def now_utc() -> datetime:
    """Return the current timestamp in UTC."""
    return datetime.now(timezone.utc)


def _iso(ts: datetime) -> str:
    """Format a UTC timestamp as ISO-8601 Zulu."""
    return ts.isoformat().replace("+00:00", "Z")


def _evt_id() -> str:
    """Generate an event id."""
    return f"evt_{uuid4().hex[:18]}"


def _acct_id() -> str:
    """Generate an account id."""
    return f"acct_{uuid4().hex[:14]}"


def _ch_id() -> str:
    """Generate a charge id."""
    return f"ch_{uuid4().hex[:16]}"


def _re_id() -> str:
    """Generate a refund id."""
    return f"re_{uuid4().hex[:16]}"


def _maybe_drop(payload: dict[str, Any], *, key: str, p: float) -> None:
    """Possibly remove a key entirely from the payload."""
    if key in payload and fake.pyfloat(min_value=0, max_value=1) < p:
        payload.pop(key, None)


def _payout_schedule() -> dict[str, Any]:
    """Create a nested payout schedule payload."""
    schedule: dict[str, Any] = {
        "interval": fake.random_element(["daily", "weekly"]),
        "delay_days": fake.random_element([1, 2, 3, 5]),
        "weekly_anchor": fake.random_element(["monday", "wednesday", "friday"]),
    }
    _maybe_drop(schedule, key="weekly_anchor", p=0.6)
    return schedule


def build_account_payload(*, account_id: str) -> dict[str, Any]:
    """Build an account payload where some fields may be missing."""
    country = fake.random_element(COUNTRIES)
    payload: dict[str, Any] = {
        "account_id": account_id,
        "merchant_name": fake.company(),
        "country": country,
        "default_currency": CURRENCIES_BY_COUNTRY[country],
        "is_active": fake.pyfloat(min_value=0, max_value=1) < 0.95,
        "payout_schedule": _payout_schedule(),
        "support_contact": {
            "email": f"support@{fake.domain_name()}",
            "phone": None if fake.pyfloat(min_value=0, max_value=1) < 0.6 else fake.phone_number(),
        },
    }

    _maybe_drop(payload, key="support_contact", p=0.25)
    return payload


def _payment_method_details() -> dict[str, Any]:
    """Create a nested payment method payload with schema variation."""
    r = fake.pyfloat(min_value=0, max_value=1)
    if r < 0.75:
        card: dict[str, Any] = {
            "brand": fake.random_element(["visa", "mastercard", "amex", "discover"]),
            "funding": fake.random_element(["credit", "debit"]),
            "last4": fake.random_element(["4242", "4444", "1881", "0005", "9995"]),
            "exp_month": fake.random_int(min=1, max=12),
            "exp_year": fake.random_int(min=datetime.now().year + 1, max=datetime.now().year + 6),
            "checks": {
                "cvc_check": fake.random_element(["pass", "fail", "unavailable"]),
                "postal_code_check": fake.random_element(["pass", "fail", "unavailable"]),
            },
        }
        if fake.pyfloat(min_value=0, max_value=1) < 0.2:
            card.pop("checks", None)
        return {"type": "card", "card": card}

    if r < 0.9:
        bank_transfer: dict[str, Any] = {
            "bank_name": fake.random_element(["Chase", "Bank of America", "Wells Fargo", "HSBC"]),
            "account_type": fake.random_element(["checking", "savings"]),
            "last4": str(fake.random_int(min=1000, max=9999)),
        }
        _maybe_drop(bank_transfer, key="account_type", p=0.4)
        return {"type": "bank_transfer", "bank_transfer": bank_transfer}

    return {"type": "wallet", "wallet": {"provider": fake.random_element(["apple_pay", "google_pay"])}}


def _billing_details(country: str) -> dict[str, Any]:
    """Create nested billing details with missing and nullable fields."""
    address: dict[str, Any] = {
        "line1": fake.street_address(),
        "line2": None if fake.pyfloat(min_value=0, max_value=1) < 0.7 else fake.secondary_address(),
        "city": fake.city(),
        "state": fake.state_abbr() if country == "US" else None,
        "postal_code": fake.postcode(),
        "country": country,
    }
    _maybe_drop(address, key="line2", p=0.5)
    _maybe_drop(address, key="state", p=0.4)

    payload: dict[str, Any] = {
        "name": fake.name(),
        "email": fake.email(),
        "phone": None if fake.pyfloat(min_value=0, max_value=1) < 0.6 else fake.phone_number(),
        "address": address,
    }
    _maybe_drop(payload, key="phone", p=0.35)
    return payload


def _outcome(status: str) -> dict[str, Any]:
    """Create an outcome object which may be omitted by the API sometimes."""
    if status == "succeeded":
        return {"network_status": "approved_by_network", "risk_level": fake.random_element(["normal", "elevated"])}
    if status == "pending":
        return {"network_status": "not_sent_to_network"}
    return {"network_status": "declined_by_network", "risk_level": fake.random_element(["elevated", "highest"])}


def build_charge_payload(*, charge_id: str, account_id: str, ts: datetime) -> dict[str, Any]:
    """Build a charge payload referencing an account id."""
    status = fake.random_choices(elements=CHARGE_STATUSES, length=1)[0]
    captured = status == "succeeded"
    paid = status == "succeeded"

    country = fake.random_element(COUNTRIES)
    currency = CURRENCIES_BY_COUNTRY[country]

    payload: dict[str, Any] = {
        "charge_id": charge_id,
        "account_id": account_id,
        "external_order_id": f"ord_{fake.random_int(min=10_000_000, max=99_999_999)}",
        "customer_reference": None if fake.pyfloat(min_value=0, max_value=1) < 0.35 else f"cus_{uuid4().hex[:8]}",
        "amount": fake.random_int(min=250, max=25_000),
        "currency": currency,
        "status": status,
        "captured": captured,
        "paid": paid,
        "refunded": False,
        "created_at_utc": _iso(ts),
        "captured_at_utc": _iso(ts) if captured else None,
        "statement_descriptor": None if fake.pyfloat(min_value=0, max_value=1) < 0.25 else fake.pystr(min_chars=10, max_chars=18).upper(),
        "payment_method_details": _payment_method_details(),
        "billing_details": _billing_details(country),
        "outcome": _outcome(status),
        "metadata": {"channel": fake.random_element(["web", "mobile", "marketplace_api"])},
    }

    if "metadata" in payload and fake.pyfloat(min_value=0, max_value=1) < 0.25:
        payload["metadata"]["promo_code"] = fake.random_element(["WELCOME10", "WINTER15", "FREESHIP"])

    # Missing fields (not returned)
    _maybe_drop(payload, key="customer_reference", p=0.25)
    _maybe_drop(payload, key="statement_descriptor", p=0.20)
    _maybe_drop(payload, key="captured_at_utc", p=0.40)
    _maybe_drop(payload, key="billing_details", p=0.10)
    _maybe_drop(payload, key="outcome", p=0.12)
    _maybe_drop(payload, key="metadata", p=0.30)

    return payload


def build_charge_update_payload(*, charge_id: str, ts: datetime) -> dict[str, Any]:
    """Build a partial update payload for an existing charge."""
    status = fake.random_element(["pending", "succeeded", "failed"])
    payload: dict[str, Any] = {
        "charge_id": charge_id,
        "status": status,
        "updated_at_utc": _iso(ts),
        "outcome": _outcome(status),
        "metadata": {"backfill_tag": fake.random_element(["late_enrichment", "support_fix"])},
    }

    _maybe_drop(payload, key="outcome", p=0.20)
    _maybe_drop(payload, key="metadata", p=0.30)
    return payload


def build_refund_payload(
    *,
    refund_id: str,
    charge_id: str,
    account_id: str,
    amount: int,
    currency: str,
    ts: datetime,
) -> dict[str, Any]:
    """Build a refund payload referencing a charge id (and often an account id)."""
    status = fake.random_element(REFUND_STATUSES)
    payload: dict[str, Any] = {
        "refund_id": refund_id,
        "charge_id": charge_id,
        "account_id": account_id,
        "amount": amount,
        "currency": currency,
        "reason": fake.random_element(REFUND_REASONS),
        "status": status,
        "created_at_utc": _iso(ts),
        "processed_at_utc": _iso(ts) if status == "succeeded" else None,
        "metadata": {
            "ticket_id": f"cs_{fake.random_int(min=100000, max=999999)}",
            "initiated_by": fake.random_element(["customer", "support_agent", "system"]),
        },
    }

    # Missing fields
    _maybe_drop(payload, key="account_id", p=0.20)
    _maybe_drop(payload, key="metadata", p=0.25)
    _maybe_drop(payload, key="processed_at_utc", p=0.45)

    return payload


def _random_existing_ids(session: Session, stmt) -> list[str]:
    """Fetch ids from the database and return unique values."""
    values = session.exec(stmt).all()
    return sorted(set(values))


def emit_account_events(session: Session, *, new: int, updates: int, ts: datetime) -> tuple[int, int]:
    """Insert new and update account events."""
    inserted = 0
    updated = 0

    for _ in range(new):
        account_id = _acct_id()
        payload = build_account_payload(account_id=account_id)
        session.add(
            AccountEvent(
                event_id=_evt_id(),
                account_id=account_id,
                source_event_ts_utc=ts,
                created_at_utc=ts,
                payload=payload,
            )
        )
        inserted += 1

    existing_ids = _random_existing_ids(session, select(AccountEvent.account_id))
    if updates and existing_ids:
        chosen = fake.random_elements(existing_ids, length=min(updates, len(existing_ids)), unique=True)
        for account_id in chosen:
            payload = build_account_payload(account_id=account_id)
            session.add(
                AccountEvent(
                    event_id=_evt_id(),
                    account_id=account_id,
                    source_event_ts_utc=ts,
                    created_at_utc=ts,
                    payload=payload,
                )
            )
            updated += 1

    session.commit()
    return inserted, updated


def emit_charge_events(session: Session, *, new: int, updates: int, ts: datetime) -> tuple[int, int]:
    """Insert new and update charge events (requires accounts)."""
    inserted = 0
    updated = 0

    account_ids = _random_existing_ids(session, select(AccountEvent.account_id))
    if len(account_ids) < 10:
        need = 10 - len(account_ids)
        emit_account_events(session, new=need, updates=0, ts=ts)
        account_ids = _random_existing_ids(session, select(AccountEvent.account_id))

    for _ in range(new):
        account_id = fake.random_element(account_ids)
        charge_id = _ch_id()
        payload = build_charge_payload(charge_id=charge_id, account_id=account_id, ts=ts)
        session.add(
            ChargeEvent(
                event_id=_evt_id(),
                charge_id=charge_id,
                source_event_ts_utc=ts,
                created_at_utc=ts,
                payload=payload,
            )
        )
        inserted += 1

    charge_ids = _random_existing_ids(session, select(ChargeEvent.charge_id))
    if updates and charge_ids:
        chosen = fake.random_elements(charge_ids, length=min(updates, len(charge_ids)), unique=True)
        for charge_id in chosen:
            payload = build_charge_update_payload(charge_id=charge_id, ts=ts)
            session.add(
                ChargeEvent(
                    event_id=_evt_id(),
                    charge_id=charge_id,
                    source_event_ts_utc=ts,
                    created_at_utc=ts,
                    payload=payload,
                )
            )
            updated += 1

    session.commit()
    return inserted, updated


def emit_refund_events(session: Session, *, new: int, updates: int, ts: datetime) -> tuple[int, int]:
    """Insert new and update refund events (requires charges)."""
    inserted = 0
    updated = 0

    # Ensure we have charges to reference
    charge_ids = _random_existing_ids(session, select(ChargeEvent.charge_id))
    if len(charge_ids) < 25:
        need = 25 - len(charge_ids)
        emit_charge_events(session, new=need, updates=0, ts=ts)
        charge_ids = _random_existing_ids(session, select(ChargeEvent.charge_id))

    # Build a small lookup from existing charge events (best-effort)
    charge_rows = session.exec(select(ChargeEvent).order_by(ChargeEvent.source_event_ts_utc.desc())).all()
    latest_by_charge: dict[str, dict[str, Any]] = {}
    for row in charge_rows:
        if row.charge_id not in latest_by_charge:
            latest_by_charge[row.charge_id] = row.payload

    for _ in range(new):
        charge_id = fake.random_element(charge_ids)
        ch_payload = latest_by_charge.get(charge_id, {})
        account_id = str(ch_payload.get("account_id", "acct_unknown"))
        amount = int(ch_payload.get("amount", fake.random_int(min=250, max=25_000)))
        currency = str(ch_payload.get("currency", "USD"))

        refund_id = _re_id()
        payload = build_refund_payload(
            refund_id=refund_id,
            charge_id=charge_id,
            account_id=account_id,
            amount=amount,
            currency=currency,
            ts=ts,
        )
        session.add(
            RefundEvent(
                event_id=_evt_id(),
                refund_id=refund_id,
                source_event_ts_utc=ts,
                created_at_utc=ts,
                payload=payload,
            )
        )
        inserted += 1

    # Updates for refunds = emit partial events for existing refund_ids
    refund_ids = _random_existing_ids(session, select(RefundEvent.refund_id))
    if updates and refund_ids:
        chosen = fake.random_elements(refund_ids, length=min(updates, len(refund_ids)), unique=True)
        for refund_id in chosen:
            payload: dict[str, Any] = {
                "refund_id": refund_id,
                "status": fake.random_element(["pending", "succeeded", "failed"]),
                "updated_at_utc": _iso(ts),
            }
            _maybe_drop(payload, key="updated_at_utc", p=0.15)
            session.add(
                RefundEvent(
                    event_id=_evt_id(),
                    refund_id=refund_id,
                    source_event_ts_utc=ts,
                    created_at_utc=ts,
                    payload=payload,
                )
            )
            updated += 1

    session.commit()
    return inserted, updated
