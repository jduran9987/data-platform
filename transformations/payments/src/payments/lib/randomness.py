"""Request planning utilities.

Provides a probabilistic request generator that simulates realistic
API traffic patterns (mostly small, mostly new records).
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestPlan:
    """Immutable request plan.

    Attributes:
        new: Number of new records to create.
        updates: Number of existing records to update.
        limit: API request limit parameter.
    """

    new: int
    updates: int
    limit: int


class RequestRandomizer:
    """Request randomizer.

    Builds randomized request plans with skew toward new records and mostly
    small batch sizes.
    """

    def __init__(self, seed: int | None = None) -> None:
        """Initialize the randomizer.

        Args:
            seed: Optional random seed for reproducible results.
        """
        self._rng = random.Random(seed)

    def _sample_total_count(self) -> int:
        """Sample a total request size using a skewed distribution.

        Returns:
            An integer representing the total number of records
            to include in the request.
        """
        roll = self._rng.random()

        if roll < 0.78:
            return self._rng.randint(1, 25)
        if roll < 0.95:
            return self._rng.randint(26, 50)
        if roll < 0.99:
            return self._rng.randint(51, 150)
        return self._rng.randint(151, 300)

    def build_plan(self, default_limit: int = 500) -> RequestPlan:
        """Generate a randomized request plan.

        Args:
            default_limit: Default API limit to use unless the sampled
                total exceeds it.

        Returns:
            A RequestPlan describing the number of new records,
            updates, and the request limit.
        """
        total = self._sample_total_count()
        mix_roll = self._rng.random()

        if mix_roll < 0.70:
            new = total
            updates = 0
        elif mix_roll < 0.92:
            updates = max(1, round(total * self._rng.uniform(0.1, 0.35)))
            new = max(0, total - updates)
        else:
            updates = total
            new = 0

        return RequestPlan(
            new=new,
            updates=updates,
            limit=max(default_limit, total),
        )
