"""Spark session utilities.

Provides a helper for constructing a configured SparkSession
for the ingestion pipeline.
"""

from __future__ import annotations

from pyspark.sql import SparkSession


def build_spark(app_name: str) -> SparkSession:
    """Create and configure a SparkSession.

    Args:
        app_name: Name of the Spark application.

    Returns:
        A SparkSession configured with UTC timezone and WARN log level.
    """
    spark = (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    return spark
