# Windows 11 + Intel AX201 radio backend: engineering plan

**Status:** research/design only. No AX201 driver, firmware or radio session has been built or installed.

## Non-negotiable target

DropWin is being developed for this exact configuration:

- Lenovo Yoga Slim 7 14ITL05, machine type 82A3.
- Intel Wi-Fi 6 AX201 160 MHz.
- Hardware ID reported by Windows: `PCI\VEN_8086&DEV_A0F0&SUBSYS_00748086&REV_20`.
- Windows 11 Home x64, build 26200.
- Intel stock driver 24.80.0.2; reported firmware D4.79.
- Secure Boot enabled; Kernel DMA Protection enabled.

The end-user requirement is that the PC appears in the iPhone's **native AirDrop recipient sheet**, with no iPhone app, no external radio, no adapter replacement and no Linux boot. These constraints are project requirements, not optional workarounds.

Until a separate review and a safe, compatible signing/deployment route exist, do not replace the Intel driver, install a custom driver, enter Test Mode, change Secure Boot/BCD, disable Kernel DMA Protection, start firmware, perform DMA, reset the radio or transmit raw frames on the user's laptop.

## Evidence gathered

### 1. AX201-class hardware has a Linux AirDrop result

The project [omdrop-owl](https://github.com/esslm/airdrop-on-windows) lists Intel AX201 as tested with `iwlwifi` in **exclusive** mode on Ubuntu 24.04 / kernel 6.8 and CachyOS / kernel 7.2.9. It reports a 2.4 MB photo transfer from iPhone to PC in about 17 seconds and the reverse direction in about 10.5 seconds. In exclusive mode the Intel radio is taken away from normal Wi-Fi while AWDL is active.

This is strong evidence that AX201 silicon/firmware can participate in AirDrop under a suitable Linux radio stack. The public hardware table does not disclose the full PCI subsystem and revision for those AX201 test machines, so it does not yet prove the Lenovo's exact board variant.

Reference: https://github.com/esslm/airdrop-on-windows#supported-hardware

### 2. AX201 is not the AX211 radio platform used by the Windows prototype

Upstream Linux `iwlwifi/pcie/drv.c` maps PCI device `0xA0F0` to `iwl_qu_long_latency_mac_cfg`. It maps `0x7A70`, the tested AX211 in [21Suspect/AirDrop-for-Windows](https://github.com/21Suspect/AirDrop-for-Windows), to `iwl_so_long_latency_imr_mac_cfg`.

The Linux firmware-name generator distinguishes MAC and RF families. For the AX201's expected QuZ/JF identity, the corresponding public firmware family is `iwlwifi-QuZ-a0-jf-b0-<API>.ucode`; the public linux-firmware tree contains a `-77` image. The AX211 Windows prototype instead pins `iwx-so-a0-gf-a0-77` plus its SO/GF PNVM. Matching the firmware API number does **not** make those device-family images interchangeable. The physical radio revision and firmware selection still need to be confirmed from the actual AX201 before choosing an image.

References:
- Linux PCI match table: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/drv.c (search for `0xA0F0` and `0x7A70`).
- Linux firmware-name selection: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/iwl-drv.c
- Public firmware inventory: https://kernel.googlesource.com/pub/scm/linux/kernel/git/firmware/linux-firmware/+/refs/heads/main/intel/iwlwifi/
- AX211 prototype's pinned SO/GF firmware and parser: https://github.com/21Suspect/AirDrop-for-Windows/blob/main/native/awdl/src/ax211.rs and https://github.com/21Suspect/AirDrop-for-Windows/blob/main/native/intel/iwl_firmware.h

### 3. The stock Windows Wi-Fi interface does not expose the needed path

The user's read-only report after driver 24.80.0.2 still says:

- Network Monitor: not supported.
- Promiscuous mode: not supported.
- Action frames: supported.
- Simultaneous channel count: 0.

Microsoft's Native 802.11 documentation describes raw MPDU/management-frame filters and the Network Monitor/Extensible AP operating modes. Those are capabilities provided by the Wi-Fi miniport; setting an NDIS filter above a miniport does not create raw-radio receive or transmit support that the miniport does not expose.

References:
- https://learn.microsoft.com/en-us/windows-hardware/drivers/network/oid-gen-current-packet-filter
- https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wifiattributes/ns-wifiattributes-ndis_miniport_adapter_native_802_11_attributes

This rules out treating a normal NDIS lightweight-filter driver or a user-mode API toggle as the solution. A custom radio/firmware path, or a documented Intel-specific interface not yet found, would be needed.

## What can be reused

| Component | Reuse assessment |
|---|---|
| DropWin GUI and file-consent/receive logic | Reusable; independent of radio silicon |
| AirDrop protocol/discovery/TLS/archive handling | Reusable, subject to interoperability tests |
| OWL AWDL scheduling/peer logic | Candidate for reuse; retain its licence and isolate radio adapter differences |
| Wintun/IPv6 bridging | Candidate for reuse after the radio exposes an AWDL interface |
| AX211 SO/GF PCI startup, firmware boot, NVM/PNVM, IRQ, DMA and radio-command implementation | **Do not reuse as-is** for AX201 QuZ/JF |
| AX211 firmware and PNVM binaries | **Not interchangeable** with AX201 firmware |
| Linux `iwlwifi` QuZ/JF implementation | Primary technical reference for AX201's MAC/firmware family; not directly loadable as a Windows driver |

## Proposed engineering sequence

### Gate A — establish the exact QuZ/JF target from public source

Map the AX201's PCI ID, MAC/RF identity, firmware naming and supported firmware API to upstream Linux/OpenBSD references. Compare the QuZ command and RX/TX descriptor paths with the SO/GF paths in the Windows prototype. Record source provenance and licensing before deriving code.

No local device interaction is required for this stage.

### Gate B — build host-only, non-hardware tests

Create parsers and unit tests for the candidate QuZ firmware container, command layouts, RX/TX descriptor decoding and bounds. Any firmware used for format tests must be an unmodified, appropriately licensed public binary with pinned provenance and hashes. Parsing a firmware file must never execute it or touch the Wi-Fi device.

The existing AX211 firmware parser pins API 77; confirm its format and constraints on the QuZ/JF candidate before reusing it. Do not assume the SO/GF PNVM flow applies to QuZ/JF.

### Gate C — design a separate AX201 Windows radio backend

Create a new AX201/QuZ implementation boundary rather than adding `A0F0` to the AX211 INF. It must have explicit stages for PnP resources, interrupts, firmware/NVM initialization, RX-only capture, bounded TX, AWDL IBSS/ACK operation and teardown. Each stage needs timeouts, a stop path and verified DMA quiescence before any buffer is released.

No register writes, firmware start, DMA or packet transmission is allowed until the hardware-specific sequence is independently reviewed and a safe signed-driver path exists.

### Gate D — resolve Windows driver trust before laptop testing

The existing AX211 preview is not suitable for this laptop: it only accepts one exact AX211 hardware ID and its current deployment requires Test Mode with Secure Boot off. That deployment is incompatible with the project's current laptop constraints.

Before installing any replacement driver, establish a Microsoft-supported production/attestation signing and deployment route that works on Windows 11 Home with Secure Boot left enabled, or stop. A locally test-signed driver and a forced INF are not acceptable substitutes.

### Gate E — staged validation on the exact Lenovo

Only after Gates A–D pass: confirm stock-driver backup and recovery design, install a correctly signed AX201-specific driver with explicit user approval, first validate safe startup/shutdown and RX-only behavior, then isolated TX, then AWDL discovery, then small-file transfer. Every stage must restore the original Intel driver and verify the radio is back in its normal Windows state.

## Current conclusion

The best current path is **a purpose-built Windows QuZ/JF radio backend for the existing AX201**, reusing DropWin's AirDrop protocol/application layers and studying Linux `iwlwifi`/OWL for AX201 behavior. This is substantially more promising than the earlier assumption that the AX201 hardware itself was unsuitable. It is still a driver-porting project, not a ready-made download or a guaranteed result.

The immediate next engineering task is Gate A: produce a source-backed QuZ/JF hardware/firmware/command map. Do not change anything on the user's laptop while doing so.
