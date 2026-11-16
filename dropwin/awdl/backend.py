from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackendStatus:
    available: bool
    message: str


class AwdlBackend:
    """Interface for a future, validated Windows AWDL implementation."""

    def probe(self) -> BackendStatus:
        return BackendStatus(
            available=False,
            message=(
                "Nessun backend AWDL Windows validato. "
                "La presenza di una scheda Wi-Fi non implica compatibilità AirDrop."
            ),
        )
