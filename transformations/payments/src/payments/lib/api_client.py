"""HTTP client utilities for fetching account data from the upstream API.

Provides a helper for constructing and executing a parameterized
GET request to the /accounts endpoint.
"""

from __future__ import annotations

from typing import Any

import requests


def fetch_accounts(
    base_url: str,
    *,
    new: int,
    updates: int,
    limit: int,
    since: str | None = None,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Fetch account records from the upstream API.

    Args:
        base_url: Base URL of the API (e.g., https://api.example.com).
        new: Number of new records to request.
        updates: Number of updated records to request.
        limit: Maximum number of records to return.
        since: Optional lower-bound timestamp filter.
        timeout_seconds: Request timeout in seconds.

    Returns:
        Parsed JSON response from the API as a dictionary.

    Raises:
       frequests.HTTPError: If the response status indicates failure.
    """
    params: dict[str, int | str] = {
        "new": new,
        "updates": updates,
        "limit": limit,
    }

    if since:
        params["since"] = since

    response = requests.get(
        f"{base_url.rstrip('/')}/accounts",
        params=params,
        timeout=timeout_seconds,
    )

    response.raise_for_status()

    return response.json()
