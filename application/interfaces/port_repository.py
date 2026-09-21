from typing import Protocol

from domain.models import Port


class PortRepositoryProtocol(Protocol):
    def get_port(self, port_id: str) -> Port | None:
        ...
