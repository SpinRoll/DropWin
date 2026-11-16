from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from enum import Enum

INTEL_VENDOR_ID = 0x8086
AX201_DEVICE_ID = 0xA0F0
IWL_TLV_MAGIC = 0x0A4C5749
IWL_TLV_HEADER_BYTES = 88
IWL_MAX_FIRMWARE_BYTES = 8 * 1024 * 1024
IWL_MAX_TLV_RECORDS = 4096
AX201_FIRMWARE_API = 77

# Linux iwlwifi maps PCI device 0xA0F0 to iwl_qu_long_latency_mac_cfg.
# The RF family is selected separately from the hardware RF-ID at runtime.
_PNP_ID_RE = re.compile(
    r"^PCI\\VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})"
    r"&SUBSYS_([0-9A-F]{8})&REV_([0-9A-F]{2})"
    r"(?:&[^\\]+)?(?:\\.*)?$",
    re.IGNORECASE,
)


class IntelRfVariant(str, Enum):
    """RF-ID family names as classified by Linux iwlwifi (not raw numeric IDs)."""

    JF1 = "JF1"
    JF2 = "JF2"
    HR1 = "HR1"
    HR2 = "HR2"


@dataclass(frozen=True)
class IntelRfIdentity:
    raw_value: int
    type_code: int
    step: int
    variant: IntelRfVariant


@dataclass(frozen=True)
class PciIdentity:
    vendor_id: int
    device_id: int
    subsystem_device_id: int
    subsystem_vendor_id: int
    revision: int

    @classmethod
    def from_windows_pnp_id(cls, value: str) -> PciIdentity | None:
        """Parse a Windows PCI PnP ID without querying or changing the device."""
        match = _PNP_ID_RE.fullmatch(value.strip())
        if match is None:
            return None

        vendor, device, subsystem, revision = (
            int(part, 16) for part in match.groups()
        )
        return cls(
            vendor_id=vendor,
            device_id=device,
            subsystem_device_id=(subsystem >> 16) & 0xFFFF,
            subsystem_vendor_id=subsystem & 0xFFFF,
            revision=revision,
        )


@dataclass(frozen=True)
class IntelRadioProfile:
    identity: PciIdentity
    mac_config: str
    device_family: int
    gen2_transport: bool
    integrated_radio: bool
    num_of_queues: int
    max_tfd_queue_size: int
    xtal_latency_us: int
    ltr_delay_us: int
    low_latency_xtal: bool
    firmware_api_min: int
    firmware_api_max: int
    exact_dropwin_test_target: bool


def identify_intel_radio(pnp_id: str) -> IntelRadioProfile | None:
    """Identify the AX201 QuZ MAC profile from a supplied PnP ID.

    This is a pure host-side classifier. It does not read PCI configuration
    space, query RF registers, load firmware, or access the radio.
    """
    identity = PciIdentity.from_windows_pnp_id(pnp_id)
    if identity is None:
        return None
    if identity.vendor_id != INTEL_VENDOR_ID or identity.device_id != AX201_DEVICE_ID:
        return None

    # Source: Linux iwlwifi pcie/drv.c + cfg/22000.c.
    # QuZ has device family 22000 and Gen2 transport. Its Linux base config
    # uses 512 queues and 256 TFD descriptors; AX210/SO has different base
    # queue parameters. These values do not identify the RF variant.
    exact_target = (
        identity.subsystem_device_id == 0x0074
        and identity.subsystem_vendor_id == INTEL_VENDOR_ID
        and identity.revision == 0x20
    )
    return IntelRadioProfile(
        identity=identity,
        mac_config="iwl_qu_long_latency_mac_cfg",
        device_family=22000,
        gen2_transport=True,
        integrated_radio=True,
        num_of_queues=512,
        max_tfd_queue_size=256,
        xtal_latency_us=12000,
        ltr_delay_us=2500,
        low_latency_xtal=True,
        firmware_api_min=AX201_FIRMWARE_API,
        firmware_api_max=AX201_FIRMWARE_API,
        exact_dropwin_test_target=exact_target,
    )


def identify_intel_rf(raw_rf_id: int) -> IntelRfIdentity | None:
    """Decode a supplied Intel CSR_HW_RFID value; does not read hardware.

    Bit fields follow Linux iwlwifi's CSR_HW_RFID_TYPE and
    CSR_HW_RFID_STEP macros. Unknown RF types remain unresolved.
    """
    if isinstance(raw_rf_id, bool) or not isinstance(raw_rf_id, int):
        raise TypeError("RF-ID must be an integer")
    if not 0 <= raw_rf_id <= 0xFFFFFFFF:
        raise ValueError("RF-ID must be an unsigned 32-bit value")

    type_code = (raw_rf_id & 0x0FFF000) >> 12
    step = (raw_rf_id & 0x0000F00) >> 8
    variant_by_code = {
        0x105: IntelRfVariant.JF2,
        0x108: IntelRfVariant.JF1,
        0x10A: IntelRfVariant.HR2,
        0x10C: IntelRfVariant.HR1,
    }
    variant = variant_by_code.get(type_code)
    if variant is None:
        return None
    return IntelRfIdentity(
        raw_value=raw_rf_id,
        type_code=type_code,
        step=step,
        variant=variant,
    )


def firmware_filename_for_rf_id(
    raw_rf_id: int,
    api: int = AX201_FIRMWARE_API,
) -> str | None:
    """Resolve a QuZ filename from an independently obtained controller RF-ID."""
    identity = identify_intel_rf(raw_rf_id)
    if identity is None:
        return None
    return firmware_filename_for_rf_variant(identity.variant, api=api)


def firmware_filename_for_rf_variant(
    variant: IntelRfVariant | str,
    api: int = AX201_FIRMWARE_API,
) -> str:
    """Resolve a QuZ firmware filename only after RF-ID classification.

    The same PCI device ID can require a filename that depends on the RF
    family. Callers must supply a family classified from a trusted RF-ID
    readout; do not infer it from the Windows PnP ID alone.
    """
    if api != AX201_FIRMWARE_API:
        raise ValueError(f"AX201 QuZ firmware API must be {AX201_FIRMWARE_API}")

    try:
        rf_variant = IntelRfVariant(variant)
    except ValueError as error:
        raise ValueError(f"Unsupported or unknown Intel RF variant: {variant!r}") from error

    rf_family = "jf" if rf_variant in {IntelRfVariant.JF1, IntelRfVariant.JF2} else "hr"
    return f"iwlwifi-QuZ-a0-{rf_family}-b0-{api}.ucode"


class FirmwareFormatError(ValueError):
    """An Intel TLV firmware container is malformed or exceeds parser limits."""


@dataclass(frozen=True)
class FirmwareTlv:
    type_id: int
    length: int


@dataclass(frozen=True)
class FirmwareImageSummary:
    file_bytes: int
    human_readable: str
    header_version: int
    build: int
    firmware_version_tlv: tuple[int, int, int] | None
    tlvs: tuple[FirmwareTlv, ...]

    @property
    def version(self) -> str | None:
        if self.firmware_version_tlv is None:
            return None
        return ".".join(str(value) for value in self.firmware_version_tlv)

    def count_tlv_type(self, type_id: int) -> int:
        return sum(record.type_id == type_id for record in self.tlvs)


def inspect_iwl_tlv_firmware(data: bytes) -> FirmwareImageSummary:
    """Inspect an Intel TLV image in memory; never loads or executes firmware.

    The parser checks the common 88-byte TLV header, the generic version/build
    header fields, and aligned TLV record boundaries. If the FW_VERSION (36)
    TLV is present, its three 32-bit words are retained separately. It does not
    verify signatures, decode every TLV semantically, or establish device
    compatibility.
    """
    if not isinstance(data, bytes):
        raise TypeError("firmware data must be bytes")
    if len(data) < IWL_TLV_HEADER_BYTES:
        raise FirmwareFormatError("truncated Intel TLV firmware header")
    if len(data) > IWL_MAX_FIRMWARE_BYTES:
        raise FirmwareFormatError("firmware exceeds the 8 MiB inspection limit")

    zero, magic = struct.unpack_from("<II", data, 0)
    if zero != 0 or magic != IWL_TLV_MAGIC:
        raise FirmwareFormatError("invalid Intel TLV firmware magic/header")

    # In the modern TLV format, ver is not unconditionally the legacy
    # major/minor/API/serial bitfield; Linux documents it as a single major
    # version in the new format. Keep the raw value rather than mis-decoding it.
    header_version, build = struct.unpack_from("<II", data, 72)
    human_readable = data[8:72].split(b"\0", 1)[0].decode("ascii", errors="replace")

    records: list[FirmwareTlv] = []
    firmware_version_tlv: tuple[int, int, int] | None = None
    cursor = IWL_TLV_HEADER_BYTES
    while cursor < len(data):
        if len(records) >= IWL_MAX_TLV_RECORDS:
            raise FirmwareFormatError("firmware contains too many TLV records")
        if len(data) - cursor < 8:
            raise FirmwareFormatError("truncated Intel TLV record header")

        type_id, length = struct.unpack_from("<II", data, cursor)
        payload_start = cursor + 8
        if length > len(data) - payload_start:
            raise FirmwareFormatError("Intel TLV payload extends beyond the file")

        padded_length = (length + 3) & ~3
        if padded_length > len(data) - payload_start:
            raise FirmwareFormatError("truncated Intel TLV alignment padding")

        if type_id == 36:
            if length != 12:
                raise FirmwareFormatError("FW_VERSION TLV must contain exactly 12 bytes")
            if firmware_version_tlv is not None:
                raise FirmwareFormatError("duplicate FW_VERSION TLV")
            firmware_version_tlv = struct.unpack_from("<III", data, payload_start)

        records.append(FirmwareTlv(type_id=type_id, length=length))
        cursor = payload_start + padded_length

    return FirmwareImageSummary(
        file_bytes=len(data),
        human_readable=human_readable,
        header_version=header_version,
        build=build,
        firmware_version_tlv=firmware_version_tlv,
        tlvs=tuple(records),
    )
