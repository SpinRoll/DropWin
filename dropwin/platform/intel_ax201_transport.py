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
QUZ_RX_QUEUE_SIZE_NON_HE = 512
QUZ_RX_QUEUE_SIZE_HE = 2048


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



def quz_rx_queue_size(*, he_enabled: bool) -> int:
    """Return the Linux-documented QuZ RX RBD count for the PHY mode.

    The QuZ family configuration uses 512 RBDs without HE and 2048 with HE.
    This is a family-level reference, not proof of the active firmware's
    negotiated mode or the Lenovo module's RF-specific configuration.
    """
    if not isinstance(he_enabled, bool):
        raise TypeError("HE-enabled flag must be a bool")
    return QUZ_RX_QUEUE_SIZE_HE if he_enabled else QUZ_RX_QUEUE_SIZE_NON_HE


def quz_rx_queue_advance(pointer: int, *, queue_size: int) -> int:
    """Advance an RX ring index using a validated power-of-two ring size."""
    if isinstance(queue_size, bool) or not isinstance(queue_size, int):
        raise TypeError("RX queue size must be an integer")
    if queue_size not in (QUZ_RX_QUEUE_SIZE_NON_HE, QUZ_RX_QUEUE_SIZE_HE):
        raise ValueError("QuZ RX queue size must be 512 or 2048 entries")
    _require_uint(pointer, bits=16, field="QuZ RX queue pointer")
    if pointer >= queue_size:
        raise ValueError("QuZ RX queue pointer must be smaller than queue size")
    return (pointer + 1) & (queue_size - 1)


def quz_rx_queue_space(read_pointer: int, write_pointer: int, *, queue_size: int) -> int:
    """Return available RX free-ring slots, keeping one slot empty.

    Follows Linux iwl_rxq_space(): (read - write - 1) & (queue_size - 1).
    Pointers and queue size are indices/counts only; this does not post RBDs.
    """
    if isinstance(queue_size, bool) or not isinstance(queue_size, int):
        raise TypeError("RX queue size must be an integer")
    if queue_size not in (QUZ_RX_QUEUE_SIZE_NON_HE, QUZ_RX_QUEUE_SIZE_HE):
        raise ValueError("QuZ RX queue size must be 512 or 2048 entries")
    for name, pointer in (("read", read_pointer), ("write", write_pointer)):
        _require_uint(pointer, bits=16, field=f"QuZ RX {name} pointer")
        if pointer >= queue_size:
            raise ValueError(f"QuZ RX {name} pointer must be smaller than queue size")
    return (read_pointer - write_pointer - 1) & (queue_size - 1)


def validate_quz_rx_vid(*, vid: int, pool_size: int) -> int:
    """Validate a decoded VID in the inclusive range 1..pool_size."""
    if isinstance(pool_size, bool) or not isinstance(pool_size, int):
        raise TypeError("RX pool size must be an integer")
    if not 1 <= pool_size <= QUZ_RX_QUEUE_SIZE_HE:
        raise ValueError("QuZ RX pool size must be between 1 and 2048")
    _require_uint(vid, bits=12, field="QuZ RX buffer ID")
    if not 1 <= vid <= pool_size:
        raise ValueError("QuZ RX buffer ID is outside the selected pool")
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


class QuzRxBufferLedger:
    """Synthetic ownership ledger for pre-AX210 multi-queue RX buffer IDs.

    This models only the logical VID ownership transitions. It does not model
    allocator batching, per-queue completion rings, page allocation, DMA
    mapping, descriptor posting, interrupts, or hardware teardown.
    """

    FREE = "free"
    POSTED = "posted"
    COMPLETED = "completed"
    USED = "used"
    ALLOCATOR_EMPTY = "allocator_empty"
    ALLOCATOR_ALLOCATED = "allocator_allocated"

    def __init__(self, *, pool_size: int) -> None:
        if isinstance(pool_size, bool) or not isinstance(pool_size, int):
            raise TypeError("RX pool size must be an integer")
        if not 2 <= pool_size <= QUZ_RX_QUEUE_SIZE_HE:
            raise ValueError("RX pool size must be between 2 and 2048")
        self.pool_size = pool_size
        # VID zero is reserved; Linux's global_table is indexed by VID - 1.
        self._states = {vid: self.FREE for vid in range(1, pool_size + 1)}

    def _require_vid(self, vid: int) -> None:
        if isinstance(vid, bool) or not isinstance(vid, int):
            raise TypeError("RX buffer ID must be an integer")
        if not 1 <= vid <= self.pool_size:
            raise ValueError("RX buffer ID is outside the ledger pool")

    def _transition(self, vid: int, expected: str, target: str) -> None:
        self._require_vid(vid)
        current = self._states[vid]
        if current != expected:
            raise ValueError(
                f"RX buffer {vid} is {current}, expected {expected}"
            )
        self._states[vid] = target

    def state(self, vid: int) -> str:
        """Return one VID's synthetic ownership state."""
        self._require_vid(vid)
        return self._states[vid]

    def counts(self) -> dict[str, int]:
        """Return counts by state; intended for deterministic tests."""
        return {
            state: sum(current == state for current in self._states.values())
            for state in (
                self.FREE, self.POSTED, self.COMPLETED, self.USED,
                self.ALLOCATOR_EMPTY, self.ALLOCATOR_ALLOCATED,
            )
        }

    def post(self, vid: int) -> None:
        self._transition(vid, self.FREE, self.POSTED)

    def complete(self, vid: int) -> None:
        """Accept a completion only for a currently posted VID."""
        self._transition(vid, self.POSTED, self.COMPLETED)

    def recycle_unstolen(self, vid: int) -> None:
        """Return a completed buffer whose page remains host-owned."""
        self._transition(vid, self.COMPLETED, self.FREE)

    def mark_page_stolen(self, vid: int) -> None:
        """Record that upper layers took the page; replacement is required."""
        self._transition(vid, self.COMPLETED, self.USED)

    def release_to_allocator(self, vid: int) -> None:
        self._transition(vid, self.USED, self.ALLOCATOR_EMPTY)

    def mark_allocator_page_ready(self, vid: int) -> None:
        """Model allocator completion without allocating or mapping a page."""
        self._transition(
            vid, self.ALLOCATOR_EMPTY, self.ALLOCATOR_ALLOCATED
        )

    def publish_replacement(self, vid: int) -> None:
        """Return a synthetic replacement buffer to the free-list state."""
        self._transition(
            vid, self.ALLOCATOR_ALLOCATED, self.FREE
        )
