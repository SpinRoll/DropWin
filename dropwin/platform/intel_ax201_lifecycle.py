"""Host-only teardown safety model for the Intel QuZ RX DMA path.

This module does not stop DMA, inspect hardware, synchronize real NAPI/DPC
work, or free memory. It models the minimum evidence a future driver must
obtain before releasing memory that a device or deferred RX worker could
still access.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QuzDmaQuiescenceGate:
    """Synthetic fail-closed gate for DMA-backed memory release.

    All three independent conditions are required:
    - RX DMA has reported idle;
    - PCIe bus mastering has been confirmed disabled;
    - all RX deferred-processing contexts have been synchronized.

    A timeout or other failure permanently closes this gate. The model is
    deliberately monotonic: it cannot be reset or reopened after failure.
    """

    rx_dma_idle: bool = False
    bus_master_disabled: bool = False
    napi_synchronized: bool = False
    failed: bool = False
    failure_reason: str | None = None

    @property
    def can_release_dma_memory(self) -> bool:
        """Whether the synthetic evidence set satisfies every safety gate."""
        return (
            not self.failed
            and self.rx_dma_idle
            and self.bus_master_disabled
            and self.napi_synchronized
        )

    def record_rx_dma_idle(self) -> None:
        """Record a synthetic successful RX-DMA-idle observation."""
        self._require_open()
        self.rx_dma_idle = True

    def record_bus_master_disabled(self) -> None:
        """Record a synthetic successful PCIe bus-master-stop observation."""
        self._require_open()
        self.bus_master_disabled = True

    def record_napi_synchronized(self) -> None:
        """Record a synthetic successful synchronization of RX workers."""
        self._require_open()
        self.napi_synchronized = True

    def fail(self, reason: str) -> None:
        """Fail closed after a timeout or any uncertain hardware state."""
        if not isinstance(reason, str):
            raise TypeError("failure reason must be a string")
        if not reason.strip():
            raise ValueError("failure reason must not be empty")
        self.failed = True
        self.failure_reason = reason.strip()

    def assert_release_safe(self) -> None:
        """Raise unless the synthetic release prerequisites are all present.

        This method does not release memory; it only validates the model.
        """
        if self.failed:
            raise RuntimeError(
                f"DMA memory must remain quarantined: {self.failure_reason}"
            )

        missing = [
            name
            for name, present in (
                ("RX DMA idle", self.rx_dma_idle),
                ("PCIe bus mastering disabled", self.bus_master_disabled),
                ("RX NAPI/deferred work synchronized", self.napi_synchronized),
            )
            if not present
        ]
        if missing:
            raise RuntimeError(
                "DMA memory release is unsafe; missing: " + ", ".join(missing)
            )

    def _require_open(self) -> None:
        if self.failed:
            raise RuntimeError(
                f"quiescence gate is failed closed: {self.failure_reason}"
            )
