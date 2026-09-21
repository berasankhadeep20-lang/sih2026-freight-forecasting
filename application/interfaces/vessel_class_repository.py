from typing import Protocol

from domain.models import VesselClassSpec


class VesselClassRepositoryProtocol(Protocol):
    def list_vessel_classes(self) -> list[VesselClassSpec]:
        ...
