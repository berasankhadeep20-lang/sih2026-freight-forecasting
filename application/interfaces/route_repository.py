from typing import Protocol

from domain.models import Route


class RouteRepositoryProtocol(Protocol):
    def get_route(
        self, origin_port_id: str, destination_port_id: str
    ) -> Route | None:
        """Returns the Route for this origin/destination pair, or None if
        it's not a route the system covers — callers (QueryOrchestrator)
        turn None into RouteNotFoundError (FR-1.2)."""
        ...
