"""PySpark job for ingesting raw account data from the payments API.

Fetches account records, validates each against the envelope and account
schemas, and writes good/bad partitioned Parquet datasets to S3.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from pyspark.sql import Row
from pyspark.sql import functions as F

from payments.config import Settings
from payments.lib.api_client import fetch_accounts
from payments.lib.models import (
    AccountValidationResult,
    EnvelopeValidationResult,
    validate_account,
    validate_envelope,
)
from payments.lib.randomness import RequestRandomizer
from payments.lib.spark import build_spark

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string without microseconds.
 
    Returns:
        str: A ISO 8601 string.
    """
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_dumps(value: Any) -> str:
    """Serialize a value to a compact, deterministic JSON string.

    Args:
        value (Any): The dict value to serialize into a string.

    Returns:
        str: JSON string.
    """
    return json.dumps(value, seperators=(",", ":"), sort_keys=True)


def main() -> None:
    """Run the raw accounts ingestion job.

    Fetches accounts from the API, validates each record, builds a Spark
    DataFrame, and writes partitioned Parquet output to the good and bad
    S3 URIs defined in settings.
    """
    settings = Settings()
    spark = build_spark("payments-raw-accounts")

    randomizer = RequestRandomizer(seed=settings.request_random_seed)
    plan = randomizer.build_plan(default_limit=settings.request_limit)

    run_id = str(uuid.uuid4())
    job_started_at_utc = utc_now_iso()

    response = fetch_accounts(
        settings.api_base_url,
        new=plan.new,
        updates=plan.updates,
        limit=plan.limit,
        since=settings.since,
    )

    envelope_validation: EnvelopeValidationResult = validate_envelope(response)

    requested_at_utc = response.get("requested_at_utc")
    count = response.get("count")
    data = response.get("data", [])

    rows: list[Row] = []

    for idx, account in enumerate(data):
        payload_json = json_dumps(account)
        payload_sha256 = sha256(payload_json.encode("utf-8")).hexdigest()

        account_validation: AccountValidationResult = validate_account(account, idx)

        all_errors = envelope_validation.errors + account_validation.errors
        all_warnings = envelope_validation.warnings + account_validation.warnings

        validation_passed = len(all_errors) == 0
        data_quality_status = "good" if validation_passed else "bad"

        rows.append(
            Row(
                run_id=run_id,
                source_system="payments_api",
                endpoint_name="accounts",
                object_name="accounts",
                ingestion_job_name="raw_accounts",
                ingested_at_utc=job_started_at_utc,
                api_requested_at_utc=requested_at_utc,
                api_since=settings.since,
                api_count=count,
                account_id=account.get("account_id"),
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                validation_passed=validation_passed,
                validation_errors=json_dumps(all_errors),
                validation_warnings=json_dumps(all_warnings),
                data_quality_status=data_quality_status,
                partition_date=job_started_at_utc[:10],
            )
        )

    if not rows:
        logger.info(json.dumps(
            {"run_id": run_id, "message": "No rows returned from API. Nothing written."}
        ))
        spark.stop()
        return

    df = spark.createDataFrame(rows)

    df = (
        df.withColumn("record_loaded_at", F.current_timestamp())
        .withColumn(
            "validation_error_count",
            F.size(F.from_json("validation_errors", "array<string>"))
        )
        .withColumn(
            "validation_warning_count",
            F.size(F.from_json("validation_warnings", "array<string>"))
        )
    )

    good_df = df.filter(F.col("data_quality_status") == F.lit("good"))
    bad_df = df.filter(F.col("data_quality_status") == F.lit("bad"))

    (
        good_df.write.mode("append")
        .partitinBy("partition_date")
        .parquet(settings.raw_good_s3_uri)
    )

    (
        bad_df.write.mode("append")
        .partitinBy("partition_date")
        .parquet(settings.raw_bad_s3_uri)
    )

    summary = {
        "run_id": run_id,
        "raw_good_s3_uri": settings.raw_good_s3_uri,
        "raw_bad_s3_uri": settings.raw_bad_s3_uri,
        "rows_returned": len(rows),
        "good_rows": good_df.count(),
        "bad_rows": bad_df.count(),
    }

    logger.info(json.dumps(summary))
    spark.stop()


if __name__ == "__main__":
    main()
