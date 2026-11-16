from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterable

# Intel iwlwifi QuZ / device family 22000 constants, cross-checked against
# drivers/net/wireless/intel/iwlwifi/iwl-fh.h and cfg/22000.c.
QUZ_TFD_QUEUE_SIZE = 256
QUZ_MAX_PENDING_TFDS = QUZ_TFD_QUEUE_SIZE - 1
IWL_TFH_NUM_TBS = 25
IWL_TFH_TFD_BYTES = 256
IWL_TFH_MAX_TB_BYTES = 4 * 1024 - 4
IWL_TFH_MAX_FRAME_BYTES = 8 * 1024
QUZ_NUM_OF_QUEUES = 512
QUZ_TX_DMA_ADDRESS_BITS = 36


@dataclass(frozen=True)
class TxBuffer:
    """One host-memory segment represented by a Gen2 TX buffer descriptor.

    `dma_address` is only serialized as an unsigned 64-bit field. This class
    does not allocate, map, validate, or access DMA memory.
    """

    dma_address: int
    length: int


def _require_uint(value: int, *, bits: int, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    if not 0 <= value < (1 << bits):
        raise ValueError(f"{field} must fit in an unsigned {bits}-bit field")


def encode_iwl_tfh_tfd(buffers: Iterable[TxBuffer]) -> bytes:
    """Serialize one Gen2/TFH TX frame descriptor into exactly 256 bytes.

    This is an in-memory format encoder only. It does not allocate DMA memory,
    create a TX ring, prepare a TX command/byte-count entry, or notify hardware.
    """
    entries = tuple(buffers)
    if not entries:
        raise ValueError("a TX frame descriptor must contain at least one buffer")
    if len(entries) > IWL_TFH_NUM_TBS:
        raise ValueError(f"a TFH TFD supports at most {IWL_TFH_NUM_TBS} buffers")

    total_bytes = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, TxBuffer):
            raise TypeError(f"buffer {index} must be a TxBuffer")
        _require_uint(entry.dma_address, bits=QUZ_TX_DMA_ADDRESS_BITS, field=f"buffer {index} DMA address")
        if isinstance(entry.length, bool) or not isinstance(entry.length, int):
            raise TypeError(f"buffer {index} length must be an integer")
        if not 1 <= entry.length <= IWL_TFH_MAX_TB_BYTES:
            raise ValueError(
                f"buffer {index} length must be between 1 and "
                f"{IWL_TFH_MAX_TB_BYTES} bytes"
            )
        total_bytes += entry.length

    if total_bytes > IWL_TFH_MAX_FRAME_BYTES:
        raise ValueError(
            f"combined TX frame exceeds {IWL_TFH_MAX_FRAME_BYTES} bytes"
        )

    # struct iwl_tfh_tfd: le16 num_tbs, 25 packed {le16 len, le64 addr}
    # entries, then a zeroed le32 pad. All unused entries remain zero.
    encoded = bytearray(struct.pack("<H", len(entries)))
    for entry in entries:
        encoded.extend(struct.pack("<HQ", entry.length, entry.dma_address))
    encoded.extend(b"\0" * ((IWL_TFH_NUM_TBS - len(entries)) * 10))
    encoded.extend(struct.pack("<I", 0))

    if len(encoded) != IWL_TFH_TFD_BYTES:
        raise AssertionError("internal TFH TFD size calculation is inconsistent")
    return bytes(encoded)


def encode_quz_rx_buffer_descriptor(*, rbid: int, dma_address: int) -> bytes:
    """Serialize the QuZ multi-queue 8-byte RX buffer descriptor.

    Linux's pre-AX210 path packs the 12-bit virtual buffer ID into the low
    12 bits of the 64-bit DMA address. Therefore the address must be
    4-KiB-aligned and the ID must be in 1..4095. This is an offline encoder:
    it does not allocate/map DMA, assign a real buffer ID, or post an RBD.
    """
    _require_uint(rbid, bits=12, field="QuZ RX buffer ID")
    if rbid == 0:
        raise ValueError("QuZ RX buffer ID must be nonzero")
    _require_uint(dma_address, bits=64, field="QuZ RX DMA address")
    if dma_address & 0xFFF:
        raise ValueError("QuZ RX DMA address must be 4-KiB aligned")
    return struct.pack("<Q", dma_address | rbid)



def extract_quz_rx_completion_vid(completion_word: int) -> int:
    """Extract the pre-AX210 QuZ RX completion's 12-bit virtual buffer ID.

    Linux reads the older-family completion ring as little-endian u32 entries
    and masks the low 12 bits. VID zero is invalid. The caller must additionally
    check the returned ID against its own RX pool size and ownership state.
    """
    _require_uint(completion_word, bits=32, field="QuZ RX completion word")
    vid = completion_word & 0x0FFF
    if vid == 0:
        raise ValueError("QuZ RX completion contains the invalid zero VID")
    return vid


def quz_tx_queue_advance(write_pointer: int) -> int:
    """Advance the QuZ TX write counter using max_tfd_queue_size=256."""
    _require_uint(write_pointer, bits=8, field="QuZ TX write pointer")
    return (write_pointer + 1) & (QUZ_TFD_QUEUE_SIZE - 1)


def quz_tx_pending_count(read_pointer: int, write_pointer: int) -> int:
    """Return the modular distance between QuZ TX read and write counters.

    The value is unambiguous for the supported queue discipline, which keeps
    one slot empty; a full 256-entry queue is not a valid pending state.
    """
    _require_uint(read_pointer, bits=8, field="QuZ TX read pointer")
    _require_uint(write_pointer, bits=8, field="QuZ TX write pointer")
    return (write_pointer - read_pointer) & (QUZ_TFD_QUEUE_SIZE - 1)



def encode_quz_tx_byte_count_entry(*, byte_count: int, num_tbs: int) -> bytes:
    """Serialize the pre-AX210 QuZ TX byte-count table entry.

    Linux's 22000/QuZ path stores the TX byte count in dwords in the low
    12 bits, and the number of additional 64-byte TFD fetch chunks in the
    upper bits. The fetch count comes from the populated TFD prefix
    (2-byte header + 10 bytes per active TB). This only encodes the 16-bit
    table value; it does not allocate or write the scheduler byte-count table.
    """
    if isinstance(byte_count, bool) or not isinstance(byte_count, int):
        raise TypeError("TX byte count must be an integer")
    if byte_count <= 0:
        raise ValueError("TX byte count must be positive")
    dword_count = (byte_count + 3) // 4
    if dword_count > 0x0FFF:
        raise ValueError("QuZ TX byte count exceeds the 12-bit dword field")

    if isinstance(num_tbs, bool) or not isinstance(num_tbs, int):
        raise TypeError("TFD buffer count must be an integer")
    if not 1 <= num_tbs <= IWL_TFH_NUM_TBS:
        raise ValueError(f"TFD buffer count must be between 1 and {IWL_TFH_NUM_TBS}")

    populated_tfd_bytes = 2 + (num_tbs * 10)
    fetch_chunks = ((populated_tfd_bytes + 63) // 64) - 1
    if not 0 <= fetch_chunks <= 0xF:
        raise AssertionError("internal TFD fetch chunk calculation is out of range")

    entry = dword_count | (fetch_chunks << 12)
    return struct.pack("<H", entry)


def encode_gen2_tx_doorbell_value(*, queue_id: int, write_pointer: int) -> int:
    """Build the Gen2 HBUS_TARG_WRPTR value; this does not write the register."""
    if isinstance(queue_id, bool) or not isinstance(queue_id, int):
        raise TypeError("Gen2 TX queue ID must be an integer")
    if not 0 <= queue_id < QUZ_NUM_OF_QUEUES:
        raise ValueError(
            f"QuZ TX queue ID must be between 0 and {QUZ_NUM_OF_QUEUES - 1}"
        )
    _require_uint(write_pointer, bits=8, field="Gen2 TX write pointer")
    return (queue_id << 16) | write_pointer
