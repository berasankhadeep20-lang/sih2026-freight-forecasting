"""
Protocol (structural typing) that ForecastingService depends on.

This is what makes the service unit-testable without a database: tests
hand it a small in-memory fake implementing this same shape, production
code hands it a real Postgres-backed repository. Neither the Protocol
nor the service needs to know which one it's talking to.
"""

from typing import Protocol

from domain.enums import VesselClass
from domain.models import RouteFreightRate


class RateRepositoryProtocol(Protocol):
    def get_historical_rates(
        self, route_id: str, vessel_class: VesselClass
    ) -> list[RouteFreightRate]:
        """Return the full historical series for one route/vessel-class
        pair, ordered by trade_date ascending. Empty list if none exist —
        callers (ForecastingService) are responsible for deciding whether
        that's an error, not this interface."""
        ...
