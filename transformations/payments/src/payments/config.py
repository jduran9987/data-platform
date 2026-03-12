"""Configuration models for the ingestion pipeline.

Defines validated runtime settings for API access, AWS configuration,
and S3 locations for accepted and quarantined raw data.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the ingestion pipeline.

    Controls API connectivity, extraction limits, and S3 destinations
    for accepted and quarantined raw data.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_base_url: str
    aws_region: str = "us-east-1"

    raw_accepted_bucket: str
    raw_quarantine_bucket: str

    raw_accepted_prefix: str
    raw_quarantine_prefix: str

    request_limit: int = 500
    since: str | None = None
    request_random_seed: int | None = None

    @property
    def accepted_s3_uri(self) -> str:
        """Return the S3A URI for accepted raw data."""
        return f"s3a://{self.raw_accepted_bucket}/{self.raw_accepted_prefix}"

    @property
    def quarantine_s3_uri(self) -> str:
        """Return the S3A URI for quarantined raw data."""
        return f"s3a://{self.raw_quarantine_bucket}/{self.raw_quarantine_prefix}"
