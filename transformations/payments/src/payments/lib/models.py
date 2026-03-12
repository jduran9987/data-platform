"""Pydantic models and validation helpers for the payments API response.

Defines the expected shape of the account response envelope and individual
account records, and provides functions to validate each against those schemas.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class SupportContact(BaseModel):
    """Optional merchant support contact details."""

    model_config = ConfigDict(extra="allow")

    email: str | None = None
    phone: str | None = None


class PayoutSchedule(BaseModel):
    """Payout schedule configuration for a merchant account."""

    model_config = ConfigDict(extra="allow")

    interval: Literal["daily", "weekly"]
    delay_days: int = Field(gt=0)
    weekly_anchor: Literal["monday", "wednesday", "friday"] | None = None


class AccountPayload(BaseModel):
    """Expected fields for a single account record from the API."""

    model_config = ConfigDict(extra="allow")

    account_id: str
    merchant_name: str = Field(min_length=1)
    country: str = Field(min_length=2, max_length=2)
    default_currency: str = Field(min_length=3, max_length=3)
    is_active: bool
    payout_schedule: PayoutSchedule
    support_contact: SupportContact | None = None

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, value: str) -> str:
        """Validate that account_id starts with the expected prefix."""
        if not value.startswith("acct_"):
            raise ValueError("must start with `acct_'")
        return value


class AccountResponseEnvelope(BaseModel):
    """Top-level envelope returned by the /accounts API endpoint."""

    model_config = ConfigDict(extra="allow")

    requested_at_utc: str
    inserted: int
    updated: int
    count: int
    data: list[dict[str, Any]]


class EnvelopeValidationResult(BaseModel):
    """Result of validating the API response envelope."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]


class AccountValidationResult(BaseModel):
    """Result of validating a single account record."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    parsed: AccountPayload | None = None


def summarize_pydantic_error(exc: ValidationError, prefix: str) -> list[str]:
    """Flatten a Pydantic ValidationError into a list of human-readable strings.

    Args:
        exc (ValidationError): The Pydantic validation error to summarize.
        prefix (str): A prefix to prepend to each field path (e.g. "envelope").

    Returns:
        list[str]: Error messages in the format "<prefix>.<field>: <message>".
    """
    messages: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"])
        msg = err["msg"]
        messages.append(f"{prefix}.{loc}: {msg}")
    return messages


def validate_envelope(payload: dict[str, Any]) -> EnvelopeValidationResult:
    """Validate the top-level API response envelope.

    Args:
        payload (dict[str, Any]): The raw API response dictionary.

    Returns:
        EnvelopeValidationResult: Validation outcome with any errors and warnings.
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        parsed = AccountResponseEnvelope.model_validate(payload)
    except ValidationError as exc:
        return EnvelopeValidationResult(
            is_valid=False,
            errors=summarize_pydantic_error(exc, "envelope"),
            warnings=[],
        )

    expected_fields = set(AccountResponseEnvelope.model_fields.keys())
    extra_fields = sorted(set(payload.keys()) - expected_fields)
    warnings.extend([f"envelope.{field}: unexpected field" for field in extra_fields])

    if parsed.count != len(parsed.data):
        errors.append(
            f"envelope.count: expected {len(parsed.data)} based on retuend data length, got {parsed.count}"
        )

    return EnvelopeValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def validate_account(payload: dict[str, Any], index: int) -> AccountValidationResult:
    """Validate a single account record from the API response.

    Args:
        payload (dict[str, Any]): The raw account dictionary to validate.
        index (int): Position of the record in the response data list, used in error messages.

    Returns:
        AccountValidationResult: Validation outcome with any errors, warnings, and parsed model.
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        parsed = AccountPayload.model_validate(payload)
    except ValidationError as exc:
        return AccountValidationResult(
            is_valid=False,
            errors=summarize_pydantic_error(exc, f"account[{index}]"),
            warnings=[],
            parsed=None,
        )

    expected_top_level = set(AccountPayload.model_fields.keys())
    extra_top_level = sorted(set(payload.keys()) - expected_top_level)
    warnings.extend([
        f"account[{index}].{field}: unexpected field" for field in extra_top_level
    ])

    payout_payload = payload.get("payout_schedule")
    if isinstance(payout_payload, dict):
        expected_nested = set(PayoutSchedule.model_fields.keys())
        extra_nested = sorted(set(payout_payload.keys()) - expected_nested)
        warnings.extend([
            f"account[{index}].support_contact.{field}: unexpected field"
            for field in extra_nested
        ])

    return AccountValidationResult(
        is_valid=True,
        errors=errors,
        warnings=warnings,
        parsed=parsed,
    )
