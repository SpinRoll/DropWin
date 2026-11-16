from __future__ import annotations

import struct

import pytest

from dropwin.platform.intel_ax201_transport import (
    IWL_TFH_MAX_FRAME_BYTES,
    IWL_TFH_MAX_TB_BYTES,
    IWL_TFH_NUM_TBS,
    IWL_TFH_TFD_BYTES,
    QUZ_MAX_PENDING_TFDS,
    TxBuffer,
    encode_gen2_tx_doorbell_value,
    encode_iwl_tfh_tfd,
    quz_tx_pending_count,
    quz_tx_queue_advance,
)


def test_tfh_tfd_is_256_bytes_and_little_endian() -> None:
    result = encode_iwl_tfh_tfd(
        [TxBuffer(dma_address=0x1122334455667788, length=0x123)]
    )

    assert len(result) == IWL_TFH_TFD_BYTES == 256
    assert result[:2] == b"\x01\x00"
    assert result[2:12] == struct.pack("<HQ", 0x123, 0x1122334455667788)
    assert result[12:-4] == bytes((IWL_TFH_NUM_TBS - 1) * 10)
    assert result[-4:] == b"\0" * 4


def test_tfh_tfd_supports_all_25_buffer_slots() -> None:
    buffers = [TxBuffer(dma_address=index, length=1) for index in range(25)]
    result = encode_iwl_tfh_tfd(buffers)

    assert len(result) == 256
    assert struct.unpack_from("<H", result)[0] == 25
    assert struct.unpack_from("<HQ", result, 2 + 24 * 10) == (1, 24)
    assert result[-4:] == b"\0" * 4


def test_tfh_tfd_rejects_empty_and_too_many_buffers() -> None:
    with pytest.raises(ValueError, match="at least one"):
        encode_iwl_tfh_tfd([])
    with pytest.raises(ValueError, match="at most 25"):
        encode_iwl_tfh_tfd([TxBuffer(index, 1) for index in range(26)])


@pytest.mark.parametrize("length", [0, -1, IWL_TFH_MAX_TB_BYTES + 1])
def test_tfh_tfd_rejects_invalid_segment_lengths(length: int) -> None:
    with pytest.raises(ValueError, match="length"):
        encode_iwl_tfh_tfd([TxBuffer(0, length)])


def test_tfh_tfd_rejects_frames_over_8kib() -> None:
    with pytest.raises(ValueError, match="combined TX frame"):
        encode_iwl_tfh_tfd(
            [
                TxBuffer(0x1000, IWL_TFH_MAX_TB_BYTES),
                TxBuffer(0x2000, IWL_TFH_MAX_TB_BYTES),
                TxBuffer(0x3000, 9),
            ]
        )


@pytest.mark.parametrize("address", [-1, 1 << 64])
def test_tfh_tfd_rejects_out_of_range_dma_address(address: int) -> None:
    with pytest.raises(ValueError, match="DMA address"):
        encode_iwl_tfh_tfd([TxBuffer(address, 1)])


def test_tfh_tfd_rejects_wrong_types_and_bool_as_integer() -> None:
    with pytest.raises(TypeError, match="TxBuffer"):
        encode_iwl_tfh_tfd([object()])  # type: ignore[list-item]
    with pytest.raises(TypeError, match="DMA address"):
        encode_iwl_tfh_tfd([TxBuffer(True, 1)])
    with pytest.raises(TypeError, match="length"):
        encode_iwl_tfh_tfd([TxBuffer(0, True)])


def test_quz_rx_buffer_descriptor_is_8_bytes_and_packs_12_bit_vid() -> None:
    result = encode_quz_rx_buffer_descriptor(
        rbid=0x123,
        dma_address=0x1122334455667000,
    )

    assert len(result) == 8
    assert result == struct.pack("<Q", 0x1122334455667123)
    assert int.from_bytes(result, "little") & 0xFFF == 0x123


@pytest.mark.parametrize(
    ("rbid", "address", "error"),
    [
        (-1, 0x1000, ValueError),
        (0x1000, 0x1000, ValueError),
        (0, 0x1000, ValueError),
        (True, 0x1000, TypeError),
        (1, -1, ValueError),
        (1, 1 << 64, ValueError),
        (1, 0x1001, ValueError),
        (1, False, TypeError),
    ],
)
def test_quz_rx_buffer_descriptor_rejects_invalid_fields(rbid, address, error) -> None:
    with pytest.raises(error):
        encode_quz_rx_buffer_descriptor(rbid=rbid, dma_address=address)


def test_quz_tx_counter_wraps_at_256() -> None:
    assert quz_tx_queue_advance(0) == 1
    assert quz_tx_queue_advance(254) == 255
    assert quz_tx_queue_advance(255) == 0


def test_quz_tx_pending_count_is_modular_and_leaves_one_slot_empty() -> None:
    assert quz_tx_pending_count(12, 12) == 0
    assert quz_tx_pending_count(12, 13) == 1
    assert quz_tx_pending_count(254, 1) == 3
    assert quz_tx_pending_count(0, 255) == QUZ_MAX_PENDING_TFDS == 255


@pytest.mark.parametrize("pointer", [-1, 256, True])
def test_quz_tx_pointer_rejects_invalid_values(pointer) -> None:
    with pytest.raises((TypeError, ValueError)):
        quz_tx_queue_advance(pointer)


def test_gen2_tx_doorbell_value_is_only_a_packed_integer() -> None:
    assert encode_gen2_tx_doorbell_value(queue_id=3, write_pointer=0xA5) == (
        (3 << 16) | 0xA5
    )


@pytest.mark.parametrize(
    ("queue_id", "write_pointer"),
    [(-1, 0), (64, 0), (0, -1), (0, 256), (True, 0)],
)
def test_gen2_tx_doorbell_rejects_invalid_fields(queue_id, write_pointer) -> None:
    with pytest.raises((TypeError, ValueError)):
        encode_gen2_tx_doorbell_value(
            queue_id=queue_id,
            write_pointer=write_pointer,
        )
