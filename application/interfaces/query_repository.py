from typing import Protocol

from domain.enums import DurationType
from domain.models import QueryResult, QuerySummary


class QueryRepositoryProtocol(Protocol):
    def save_query_result(
        self, cargo_volume_tonnes: int, duration_type: DurationType, result: QueryResult
    ) -> int:
        """Persists the forecast, its points, timing windows, risk alerts,
        and the query itself. Returns the new query_id."""
        ...

    def get_query(self, query_id: int) -> QueryResult | None:
        """Reconstructs a previously-saved QueryResult, same shape as a
        freshly-computed one — so GET /queries/{id} can reuse the exact
        same response schema as POST /queries."""
        ...

    def list_queries(self, limit: int = 25, offset: int = 0) -> list[QuerySummary]:
        ...
