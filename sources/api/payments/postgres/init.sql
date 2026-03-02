CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS account_events (
  event_id text PRIMARY KEY,
  account_id text NOT NULL,
  source_event_ts_utc timestamptz NOT NULL,
  created_at_utc timestamptz NOT NULL,
  payload jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_account_events_account_id ON account_events(account_id);
CREATE INDEX IF NOT EXISTS idx_account_events_source_ts ON account_events(source_event_ts_utc);

CREATE TABLE IF NOT EXISTS charge_events (
  event_id text PRIMARY KEY,
  charge_id text NOT NULL,
  source_event_ts_utc timestamptz NOT NULL,
  created_at_utc timestamptz NOT NULL,
  payload jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_charge_events_charge_id ON charge_events(charge_id);
CREATE INDEX IF NOT EXISTS idx_charge_events_source_ts ON charge_events(source_event_ts_utc);

CREATE TABLE IF NOT EXISTS refund_events (
  event_id text PRIMARY KEY,
  refund_id text NOT NULL,
  source_event_ts_utc timestamptz NOT NULL,
  created_at_utc timestamptz NOT NULL,
  payload jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_refund_events_refund_id ON refund_events(refund_id);
CREATE INDEX IF NOT EXISTS idx_refund_events_source_ts ON refund_events(source_event_ts_utc);
