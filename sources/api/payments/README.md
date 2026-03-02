# Payments API Generator (Third-Party Source Simulator)

This service simulates a **third-party payments processor API** (Stripe/Adyen-like) for data-platform ingestion.
It exposes **three endpoints** that return **three distinct payloads**:

- `GET /accounts`
- `GET /charges`
- `GET /refunds`

The payloads are intentionally “messy” in realistic ways:

- **Missing fields**: some keys are periodically **omitted** (not returned at all).
- **Nullable fields**: some keys may be present with value **`null`**.
- **Nested JSON**: several fields are objects with nested structure that varies by context.
- **Event time support**: every event row is stored with `source_event_ts_utc` in Postgres and can be pulled incrementally using `since=...`.
- **Cross-object references**:
  - charges reference accounts (`charge.account_id`)
  - refunds reference charges (`refund.charge_id`) and often accounts (`refund.account_id`)

> **DBT modeling-friendly design:** Each endpoint reads from an **append-only event table** in Postgres that stores the payload as `JSONB`.
> You can model:
> - **staging**: 1:1 with raw event tables
> - **intermediate**: “latest state per object” using `source_event_ts_utc`
> - **marts**: star schema facts/dimensions and semantic layer

---

## Run locally (Docker Compose)

```bash
docker compose up --build
```

Services:
- API: `http://localhost:8000`
- Postgres: `localhost:5432` (user/pass/db: `app/app/payments`)

Health check:
```bash
curl http://localhost:8000/healthz
```

---

## Endpoint usage

All three endpoints share the same query parameters:

- `new` (int, default `0`): Generate this many **new objects** (new IDs) before returning results.
- `updates` (int, default `0`): Emit this many **update events** for **existing objects** before returning results.
- `since` (UTC timestamp, optional): Incremental cursor. Return only events where the stored `source_event_ts_utc` is **greater than** this value.
- `limit` (int, default `500`): Maximum number of returned items.

### Notes on behavior

- If you call an endpoint with **no `new` and no `updates`**, it **does not write** anything—only returns existing stored events (or an empty list).
- “Updates” are modeled as **new events** for the same object ID (append-only). Nothing is overwritten.
- Refund generation has dependencies:
  - If not enough charges exist, the generator will create charges.
  - If not enough accounts exist for charges, it will create accounts.
  - This keeps `refund.charge_id` references valid.

---

## `GET /accounts`

Generate and/or list **account** payload events.

Examples:

Create 10 new accounts:
```bash
curl "http://localhost:8000/accounts?new=10"
```

Emit 5 updates for existing accounts:
```bash
curl "http://localhost:8000/accounts?updates=5"
```

Incremental pull (all account events after timestamp):
```bash
curl "http://localhost:8000/accounts?since=2026-03-01T00:00:00Z&limit=200"
```

---

## `GET /charges`

Generate and/or list **charge** payload events.

Examples:

Create 100 new charges (auto-seeds accounts if needed):
```bash
curl "http://localhost:8000/charges?new=100"
```

Emit 25 charge updates:
```bash
curl "http://localhost:8000/charges?updates=25"
```

Incremental:
```bash
curl "http://localhost:8000/charges?since=2026-03-01T00:00:00Z"
```

---

## `GET /refunds`

Generate and/or list **refund** payload events.

Examples:

Create 20 refunds (auto-seeds charges/accounts if needed):
```bash
curl "http://localhost:8000/refunds?new=20"
```

Emit 10 refund updates:
```bash
curl "http://localhost:8000/refunds?updates=10"
```

Incremental:
```bash
curl "http://localhost:8000/refunds?since=2026-03-01T00:00:00Z"
```

---

## Response format (all endpoints)

Each endpoint returns the same response envelope:

```json
{
  "requested_at_utc": "2026-03-01T03:12:10Z",
  "inserted": 10,
  "updated": 5,
  "count": 15,
  "data": [
    { "…payload object 1…" },
    { "…payload object 2…" }
  ]
}
```

- `requested_at_utc` is the request timestamp (UTC).
- `data` contains **payload objects** only. The event wrapper (`event_id`, `source_event_ts_utc`) is stored in Postgres for ingestion and is not returned.

---

# Payload Schemas

Because this simulates a third-party API, **some fields are not guaranteed** to be returned even when logically applicable.
For each payload schema below, “Guaranteed?” means:
- **Yes**: should appear on every payload emitted by this generator (barring future intentional changes).
- **No**: may be omitted entirely.
- **Conditional**: expected in some scenarios (e.g., only for card payments), but may still be omitted to simulate real-world variance.

Also listed:
- **Nullable?**: whether the field may explicitly be `null` when present.
- **Constraints**: enums, lengths, formats, and notes.

---

## Account payload schema

**Represents** a merchant account (connected account / sub-merchant).

### Top-level fields

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `account_id` | string | Yes | No | prefix `acct_` | Provider account identifier. |
| `merchant_name` | string | Yes | No | non-empty | Merchant display name. |
| `country` | string | Yes | No | ISO 3166-1 alpha-2, length=2 | Merchant country. |
| `default_currency` | string | Yes | No | ISO 4217, length=3 | Default currency for charges/payouts. |
| `is_active` | boolean | Yes | No |  | Whether the account is active. |
| `payout_schedule` | object | Yes | No |  | Payout cadence information. |
| `support_contact` | object | No | N/A |  | Support contact details. Sometimes omitted. |

### `payout_schedule` (nested)

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `interval` | string | Yes | No | enum: `daily`, `weekly` | Payout interval. |
| `delay_days` | integer | Yes | No | small positive int | Delay between charge capture and payout. |
| `weekly_anchor` | string | No | No | enum: `monday`, `wednesday`, `friday` | Only relevant for weekly schedules; may be omitted. |

### `support_contact` (nested)

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `email` | string | Conditional | No | email-like string | Support email. |
| `phone` | string | Conditional | Yes | phone-like string | Support phone; often `null`. |

> **Missing-field behavior:** `support_contact` may be omitted entirely.

---

## Charge payload schema

**Represents** a payment attempt / capture event.

Charges **reference accounts** via `account_id`.

### Top-level fields

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `charge_id` | string | Yes | No | prefix `ch_` | Provider charge identifier. |
| `account_id` | string | Yes | No | prefix `acct_` | Reference to the account/merchant. |
| `external_order_id` | string | Yes | No |  | Merchant order reference. |
| `customer_reference` | string | No | Yes |  | Optional customer id; may be missing or `null`. |
| `amount` | integer | Yes | No | >0 | Amount in **minor units** (e.g., cents). |
| `currency` | string | Yes | No | ISO 4217, length=3 | Charge currency. |
| `status` | string | Yes | No | enum: `succeeded`, `pending`, `failed` | Current charge status. |
| `captured` | boolean | Yes | No |  | Whether the payment was captured. |
| `paid` | boolean | Yes | No |  | Whether payment is considered paid. |
| `refunded` | boolean | Yes | No |  | Whether the charge has been refunded (may lag). |
| `created_at_utc` | string | Yes | No | date-time (ISO-8601 Z) | Creation timestamp in UTC. |
| `captured_at_utc` | string | No | Yes | date-time (ISO-8601 Z) | Capture time; may be missing or `null`. |
| `statement_descriptor` | string | No | Yes | typically <= 18 chars | Descriptor shown on bank statement; may be missing or `null`. |
| `payment_method_details` | object | Yes | No |  | Nested details; schema varies by type. |
| `billing_details` | object | No | No/Yes |  | Nested billing data; may be missing. Nested fields may be nullable/missing. |
| `outcome` | object | No | No |  | Authorization/network outcome; may be missing. |
| `metadata` | object | No | No |  | Free-form metadata; may be missing. |

### `payment_method_details` (nested, polymorphic)

`payment_method_details.type` determines which nested object exists.

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `type` | string | Yes | No | enum: `card`, `bank_transfer`, `wallet` | Payment method type. |
| `card` | object | Conditional | No | present when type=`card` | Card details. |
| `bank_transfer` | object | Conditional | No | present when type=`bank_transfer` | Bank transfer details. |
| `wallet` | object | Conditional | No | present when type=`wallet` | Wallet details. |

#### `card` (nested)

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `brand` | string | Conditional | No | enum-like: visa/mastercard/amex/discover | Card brand. |
| `funding` | string | Conditional | No | enum: credit/debit | Funding type. |
| `last4` | string | Conditional | No | length=4 digits | Last four digits. |
| `exp_month` | integer | Conditional | No | 1-12 | Expiration month. |
| `exp_year` | integer | Conditional | No | future year | Expiration year. |
| `checks` | object | No | No |  | CVC/postal checks; sometimes omitted. |

#### `checks` (nested)

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `cvc_check` | string | Conditional | No | enum: pass/fail/unavailable | CVC check result. |
| `postal_code_check` | string | Conditional | No | enum: pass/fail/unavailable | Postal check result. |

#### `bank_transfer` (nested)

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `bank_name` | string | Conditional | No |  | Bank name. |
| `account_type` | string | No | No | enum: checking/savings | May be omitted. |
| `last4` | string | Conditional | No | length=4 digits | Bank account last 4. |

#### `wallet` (nested)

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `provider` | string | Conditional | No | enum: apple_pay/google_pay | Wallet provider. |

### `billing_details` (nested)

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `name` | string | Conditional | No |  | Customer name. |
| `email` | string | Conditional | No | email-like | Customer email. |
| `phone` | string | No | Yes |  | Phone; may be missing or `null`. |
| `address` | object | Conditional | No |  | Address object. |

#### `address` (nested)

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `line1` | string | Conditional | No |  | Street line 1. |
| `line2` | string | No | Yes |  | Street line 2; may be missing or `null`. |
| `city` | string | Conditional | No |  | City. |
| `state` | string | No | Yes | US states or missing | May be missing or `null` (esp. non-US). |
| `postal_code` | string | Conditional | No |  | Postal code. |
| `country` | string | Conditional | No | ISO 3166-1 alpha-2 | Country code. |

### `outcome` (nested)

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `network_status` | string | Conditional | No | approved_by_network/not_sent_to_network/declined_by_network | Network status. |
| `risk_level` | string | No | No | normal/elevated/highest | May be omitted (especially for pending). |

### `metadata` (nested)

Free-form object. Common keys emitted:
- `channel` (string, enum-ish: `web`, `mobile`, `marketplace_api`) — **not guaranteed**
- `promo_code` (string) — **not guaranteed**
- `backfill_tag` (string) on some updates — **not guaranteed**

---

## Refund payload schema

**Represents** a refund event. Refunds **reference charges** via `charge_id`.
`account_id` is often present but may be omitted to simulate inconsistent APIs.

### Top-level fields

| Field | Type | Guaranteed? | Nullable? | Constraints | Description |
|---|---|---:|---:|---|---|
| `refund_id` | string | Yes | No | prefix `re_` | Provider refund identifier. |
| `charge_id` | string | Yes | No | prefix `ch_` | Reference to the refunded charge. |
| `account_id` | string | No | No | prefix `acct_` | Often present; may be missing. |
| `amount` | integer | Yes | No | >0 | Amount in minor units. |
| `currency` | string | Yes | No | ISO 4217, length=3 | Refund currency. |
| `reason` | string | Yes | No | enum-ish list below | Reason for refund. |
| `status` | string | Yes | No | enum: `pending`, `succeeded`, `failed` | Refund status. |
| `created_at_utc` | string | Yes | No | date-time (ISO-8601 Z) | Creation timestamp in UTC. |
| `processed_at_utc` | string | No | Yes | date-time (ISO-8601 Z) | Settlement time; may be missing or `null`. |
| `metadata` | object | No | No |  | Free-form metadata; may be missing. |

### `reason` enum values (generator)

- `requested_by_customer`
- `duplicate`
- `fraudulent`
- `expired_uncaptured_charge`

### `metadata` (nested)

Common keys emitted:
- `ticket_id` (string like `cs_######`) — not guaranteed
- `initiated_by` (enum-ish: `customer`, `support_agent`, `system`) — not guaranteed

---

# Event time and incremental ingestion

Although the API response returns only payload objects, each payload is stored in Postgres as an event row with:

- `source_event_ts_utc` (UTC, event time used for incremental pulls)
- `created_at_utc` (UTC, insert time; equal to event time in this generator)
- `payload` (JSONB)

You can pull incrementally using:

```bash
curl "http://localhost:8000/charges?since=2026-03-01T00:00:00Z"
```

In your ingestion job, treat `since` as your cursor and advance it to the max `source_event_ts_utc` processed.

---

# DBT modeling guidance (suggested)

A typical dbt approach:

1. **staging (1:1):**
   - `stg_account_events`
   - `stg_charge_events`
   - `stg_refund_events`

2. **intermediate: latest state per object**
   - `int_accounts_latest` (partition by `account_id`, order by `source_event_ts_utc desc`)
   - `int_charges_latest` (partition by `charge_id`, order by `source_event_ts_utc desc`)
   - `int_refunds_latest` (partition by `refund_id`, order by `source_event_ts_utc desc`)

3. **marts**
   - `dim_accounts` from `int_accounts_latest`
   - `fct_charges` from `int_charges_latest`
   - `fct_refunds` from `int_refunds_latest`

Because payloads are JSON, you’ll naturally handle:
- missing key -> NULL
- type casting / TRY_CAST patterns
- schema drift over time
- partial update events (some updates include only a few keys)

---

# Troubleshooting

## Connection refused to Postgres
- If running API in Docker Compose, ensure the API uses `@postgres:5432` (service name), not `@localhost`.
- If running API locally, ensure Postgres is reachable on your host port (default `5432`).
