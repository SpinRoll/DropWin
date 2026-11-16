from __future__ import annotations

import pytest

from dropwin.platform.intel_ax201_lifecycle import QuzDmaQuiescenceGate


def test_dma_memory_release_requires_all_three_quiescence_conditions() -> None:
    gate = QuzDmaQuiescenceGate()

    with pytest.raises(RuntimeError, match="RX DMA idle"):
        gate.assert_release_safe()

    gate.record_rx_dma_idle()
    with pytest.raises(RuntimeError, match="bus mastering disabled"):
        gate.assert_release_safe()

    gate.record_bus_master_disabled()
    with pytest.raises(RuntimeError, match="NAPI/deferred work synchronized"):
        gate.assert_release_safe()

    gate.record_napi_synchronized()
    assert gate.can_release_dma_memory
    gate.assert_release_safe()


def test_rx_dma_idle_alone_does_not_allow_memory_release() -> None:
    gate = QuzDmaQuiescenceGate()
    gate.record_rx_dma_idle()

    assert not gate.can_release_dma_memory
    with pytest.raises(RuntimeError, match="bus mastering disabled"):
        gate.assert_release_safe()


def test_bus_master_stop_timeout_permanently_quarantines_memory() -> None:
    gate = QuzDmaQuiescenceGate()
    gate.record_rx_dma_idle()
    gate.record_napi_synchronized()
    gate.fail("PCIe bus-master stop timed out")

    assert not gate.can_release_dma_memory
    with pytest.raises(RuntimeError, match="must remain quarantined"):
        gate.assert_release_safe()
    with pytest.raises(RuntimeError, match="failed closed"):
        gate.record_bus_master_disabled()


def test_napi_synchronization_is_independent_of_dma_idle() -> None:
    gate = QuzDmaQuiescenceGate()
    gate.record_bus_master_disabled()
    gate.record_napi_synchronized()

    assert not gate.can_release_dma_memory
    with pytest.raises(RuntimeError, match="RX DMA idle"):
        gate.assert_release_safe()


@pytest.mark.parametrize("reason", ["", "   "])
def test_failure_reason_must_not_be_blank(reason: str) -> None:
    gate = QuzDmaQuiescenceGate()
    with pytest.raises(ValueError, match="must not be empty"):
        gate.fail(reason)


def test_failure_reason_must_be_text() -> None:
    gate = QuzDmaQuiescenceGate()
    with pytest.raises(TypeError, match="must be a string"):
        gate.fail(123)  # type: ignore[arg-type]
