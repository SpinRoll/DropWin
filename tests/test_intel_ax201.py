from __future__ import annotations

import struct

import pytest

from dropwin.platform.intel_ax201 import (
    AX201_FIRMWARE_API,
    FirmwareFormatError,
    IntelRfVariant,
    PciIdentity,
    firmware_filename_for_rf_variant,
    identify_intel_radio,
    inspect_iwl_tlv_firmware,
)


AX201_PNP_ID = r"PCI\VEN_8086&DEV_A0F0&SUBSYS_00748086&REV_20"


def test_identifies_exact_lenovo_ax201_without_device_access() -> None:
    profile = identify_intel_radio(AX201_PNP_ID)

    assert profile is not None
    assert profile.identity == PciIdentity(
        vendor_id=0x8086,
        device_id=0xA0F0,
        subsystem_device_id=0x0074,
        subsystem_vendor_id=0x8086,
        revision=0x20,
    )
    assert profile.mac_config == "iwl_qu_long_latency_mac_cfg"
    assert profile.device_family == 22000
    assert profile.gen2_transport is True
    assert profile.integrated_radio is True
    assert profile.xtal_latency_us == 12_000
    assert profile.ltr_delay_us == 2_500
    assert profile.low_latency_xtal is True
    assert profile.firmware_api_min == AX201_FIRMWARE_API
    assert profile.firmware_api_max == AX201_FIRMWARE_API
    assert profile.exact_dropwin_test_target is True


@pytest.mark.parametrize(
    "pnp_id",
    [
        r"PCI\VEN_10EC&DEV_A0F0&SUBSYS_00748086&REV_20",
        r"PCI\VEN_8086&DEV_7A70&SUBSYS_00948086&REV_11",
        r"USB\VID_8086&PID_A0F0",
        r"PCI\VEN_8086&DEV_A0F0",
        "",
    ],
)
def test_rejects_unmatched_or_incomplete_pnp_ids(pnp_id: str) -> None:
    assert identify_intel_radio(pnp_id) is None


def test_accepts_full_pnp_instance_id_suffix() -> None:
    full_id = AX201_PNP_ID + r"\3&11583659&0&A0"
    profile = identify_intel_radio(full_id)
    assert profile is not None
    assert profile.exact_dropwin_test_target is True


def test_other_ax201_subsystem_is_classified_but_not_exact_target() -> None:
    profile = identify_intel_radio(
        r"PCI\VEN_8086&DEV_A0F0&SUBSYS_12348086&REV_21"
    )
    assert profile is not None
    assert profile.exact_dropwin_test_target is False


@pytest.mark.parametrize(
    ("variant", "filename"),
    [
        (IntelRfVariant.JF1, "iwlwifi-QuZ-a0-jf-b0-77.ucode"),
        ("JF2", "iwlwifi-QuZ-a0-jf-b0-77.ucode"),
        (IntelRfVariant.HR1, "iwlwifi-QuZ-a0-hr-b0-77.ucode"),
        ("HR2", "iwlwifi-QuZ-a0-hr-b0-77.ucode"),
    ],
)
def test_resolves_firmware_only_after_rf_variant_is_known(variant, filename) -> None:
    assert firmware_filename_for_rf_variant(variant) == filename


def test_rejects_unknown_rf_variant_and_unsupported_api() -> None:
    with pytest.raises(ValueError, match="unknown"):
        firmware_filename_for_rf_variant("UNKNOWN")
    with pytest.raises(ValueError, match="API"):
        firmware_filename_for_rf_variant("JF1", api=76)


def make_tlv_firmware(
    *,
    packed_version: int = 0x01024D03,
    build: int = 12345,
    records: tuple[tuple[int, bytes], ...] = ((19, b"abc"), (36, b"123456789012")),
) -> bytes:
    header = bytearray(88)
    struct.pack_into("<II", header, 0, 0, 0x0A4C5749)
    header[8:8 + len(b"synthetic test firmware")] = b"synthetic test firmware"
    struct.pack_into("<II", header, 72, packed_version, build)

    body = bytearray()
    for type_id, payload in records:
        body.extend(struct.pack("<II", type_id, len(payload)))
        body.extend(payload)
        body.extend(b"\0" * ((-len(payload)) % 4))
    return bytes(header + body)


def test_inspects_tlv_header_and_record_inventory() -> None:
    image = inspect_iwl_tlv_firmware(make_tlv_firmware())

    assert image.human_readable == "synthetic test firmware"
    assert image.version == "1.2.77.3"
    assert image.build == 12345
    assert image.file_bytes == 88 + 12 + 20
    assert [(item.type_id, item.length) for item in image.tlvs] == [(19, 3), (36, 12)]
    assert image.count_tlv_type(19) == 1
    assert image.count_tlv_type(99) == 0


def test_inspects_header_only_image() -> None:
    image = inspect_iwl_tlv_firmware(make_tlv_firmware(records=()))
    assert image.tlvs == ()


@pytest.mark.parametrize(
    ("image", "message"),
    [
        (b"", "truncated"),
        (bytes(88), "magic"),
        (bytes(87), "truncated"),
        (make_tlv_firmware()[:-1], "alignment padding"),
        (make_tlv_firmware()[:91], "extends beyond"),
        (b"x" * (8 * 1024 * 1024 + 1), "8 MiB"),
    ],
)
def test_rejects_malformed_firmware_containers(image: bytes, message: str) -> None:
    with pytest.raises(FirmwareFormatError, match=message):
        inspect_iwl_tlv_firmware(image)


def test_rejects_trailing_partial_tlv_header() -> None:
    image = make_tlv_firmware() + b"\x01\x02\x03"
    with pytest.raises(FirmwareFormatError, match="record header"):
        inspect_iwl_tlv_firmware(image)


def test_firmware_api_is_extracted_from_packed_version_byte() -> None:
    image = inspect_iwl_tlv_firmware(
        make_tlv_firmware(packed_version=0x0A03004D, records=())
    )
    assert image.major == 10
    assert image.minor == 3
    assert image.api == 0
    assert image.serial == 0x4D
