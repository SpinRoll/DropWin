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

The Linux PCI table maps device ID `0xA0F0` to `iwl_qu_long_latency_mac_cfg`, which selects the QuZ MAC configuration (device family 22000, Gen2 transport, integrated radio, 12 ms XTAL latency and 2.5 ms LTR delay). The RF family is determined separately from the controller RF-ID: Linux's firmware-name resolver distinguishes JF1/JF2 from HR1/HR2 and constructs a different firmware name for each. The common QuZ/JF candidate is `iwlwifi-QuZ-a0-jf-b0-77.ucode`; a QuZ/HR identity would select `iwlwifi-QuZ-a0-hr-b0-77.ucode`. Both families have API 77 in the cited Linux sources.

The Windows PnP string `REV_20` is not the controller's CSR hardware-revision register, and neither it nor the existing `netsh` report exposes the RF-ID. Therefore **the Lenovo's QuZ MAC mapping is confirmed by PCI device ID, but JF versus HR is still unconfirmed for this physical card**. The user's Windows-reported firmware string `D4.79` is not the Linux uCode version string and cannot be used to select or validate a `.ucode` image. The AX211 Windows prototype instead pins `iwx-so-a0-gf-a0-77` plus its SO/GF PNVM. Matching the API number does **not** make those device-family images interchangeable.

Linux's `22000.c` marks QuZ as device family 22000 and `gen2=true`; `ax210.c` also marks SO as `gen2=true`, but as device family AX210. So the distinction should not be simplified to "Gen2 versus Gen3": the device-family configuration, MAC/RF identity, firmware, NVM/PNVM path, and hardware command/descriptor behavior must each be compared. Linux's JF RF config declares extended NVM (`IWL_NVM_EXT`) and NVM version 0x0a1d; do not assume the AX211 SO/GF PNVM workflow is the right AX201 initialization path.

References:
- Linux PCI match table: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/drv.c (search for `0xA0F0` and `0x7A70`).
- Linux QuZ family parameters: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/22000.c
- Linux AX210/SO family parameters: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/ax210.c
- Linux RF-ID bit masks and type codes: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/iwl-csr.h and https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/iwl-config.h
- Linux JF NVM configuration: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/rf-jf.c
- A0F0/QuZ/JF RF-ID decoding example: https://www.mail-archive.com/bugs%40openbsd.org/msg22610.html
- Linux firmware-name selection: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/iwl-drv.c
- Public firmware inventory: https://kernel.googlesource.com/pub/scm/linux/kernel/git/firmware/linux-firmware/+/refs/heads/main/intel/iwlwifi/
- AX211 prototype's pinned SO/GF firmware and parser: https://github.com/21Suspect/AirDrop-for-Windows/blob/main/native/awdl/src/ax211.rs and https://github.com/21Suspect/AirDrop-for-Windows/blob/main/native/intel/iwl_firmware.h

### QuZ firmware selection has an independent OpenBSD reference

OpenBSD's `if_iwxvar.h` lists the QuZ-A0 firmware names separately for HR and JF:
- `iwx-QuZ-a0-hr-b0-77`
- `iwx-QuZ-a0-jf-b0-77`

Its `if_iwx.c` device-information table selects the QuZ/JF configuration based on the decoded MAC/RF type, independently confirming that PCI device ID alone does not settle JF versus HR. OpenBSD's QuZ entries use a `iwx_9560_quz_a0_jf_b0_cfg` / corresponding HR config rather than the SO/GF AX211 config.

The current Linux `cfg/22000.c` likewise declares QuZ HR/JF `.ucode` firmware names through API 77, but does not declare a QuZ PNVM companion in the way `cfg/ax210.c` declares SO/GF PNVM images. OpenBSD's firmware constants also list PNVM companions for selected SO/GF and Ty/GF families, but not QuZ. This is strong source evidence that the AX211 prototype's SO/GF PNVM staging should **not** be copied into the AX201 QuZ path. The actual QuZ NVM initialization sequence still needs to be mapped and implemented from the QuZ-specific source before any firmware execution.

Sources:
- OpenBSD QuZ/JF/HR hardware selection: https://github.com/openbsd/src/blob/master/sys/dev/pci/if_iwx.c
- OpenBSD firmware names and device configurations: https://github.com/openbsd/src/blob/master/sys/dev/pci/if_iwxvar.h
- OpenBSD QuZ MAC/RF register identifiers: https://github.com/openbsd/src/blob/master/sys/dev/pci/if_iwxreg.h
- Linux QuZ MAC-family firmware declarations: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/22000.c

### 3. QuZ queue parameters are not the AX211/SO queue parameters

Linux `cfg/22000.c` sets the QuZ base `max_tfd_queue_size` to **256**. Linux `cfg/ax210.c`, used for the SO/AX211 family, sets it to **65,536**. Linux `pcie/tx-gen2.c` uses this value as a power-of-two wrap mask in queue-space accounting, so it affects real queue-counter behavior and cannot be treated as a cosmetic constant. The AX201 host profile now records the QuZ value of 256.

There is an additional porting point to resolve: the AX211 Windows prototype declares a 256-entry software TX buffer (`IWL_TX_COUNT`) and separately documents 16-bit hardware pointer wrap. A software slot count is not the same thing as the hardware queue-counter modulus. Before reusing any of its queue code, map the QuZ hardware write/read pointer, TFD ring size, queue-context fields, RX free/used rings and completion sequence independently against Linux's 22000 implementation. Do not copy the SO/GF queue arithmetic or infer it from a constant named `TX_COUNT`.

Sources:
- Linux QuZ queue base: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/22000.c
- Linux AX210/SO queue base: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/ax210.c
- Linux queue wrap accounting: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/tx-gen2.c
- Windows AX211 prototype queue context: https://github.com/21Suspect/AirDrop-for-Windows/blob/main/native/intel/iwl_gen3.h and https://github.com/21Suspect/AirDrop-for-Windows/blob/main/native/intel/iwl_gen3.c

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

**Partial completion:** a host-only module `dropwin/platform/intel_ax201.py` now parses the Lenovo's Windows PnP identifier, maps PCI device `A0F0` to the QuZ MAC profile, records the Linux-sourced timing/transport and queue parameters, and decodes a supplied Intel `CSR_HW_RFID` value using Linux's published type/step masks. It resolves QuZ firmware filenames only when the RF type decodes to JF1/JF2 or HR1/HR2. A documented RF-ID value `0x108110` decodes to JF1; this is a source example from a different A0F0 subsystem, **not a measurement from the Lenovo**. The module deliberately does not infer the RF variant from the Lenovo's PnP revision or the `D4.79` Windows firmware string.

The module also has a bounded, read-only parser for the 88-byte Intel TLV container header and aligned TLV record inventory. It preserves the modern header version as a raw field and, when present, reads the three 32-bit words of the separate `FW_VERSION` TLV (type 36). It does not misinterpret the new-format header version as a legacy major/minor/API/serial bitfield. Tests use synthetic byte fixtures; the parser has not yet been validated against an authentic QuZ image and does not verify signatures, all TLV semantics, or device suitability.

DropWin's Wi-Fi diagnostic now collects the read-only Windows adapter `PnPDeviceID` and reports the QuZ MAC profile and 256-entry TFD queue reference for the exact AX201. It explicitly states that the RF family remains unknown until a real CSR RF-ID is safely obtained. This inventory uses Windows' `MSFT_NetAdapter.PNPDeviceID` property and does not access PCI registers or the radio.

Remaining Gate A work: confirm the RF-ID masks/classification from authoritative source, map the exact AX201 QuZ/JF or QuZ/HR command and RX/TX descriptor differences, and record provenance/licensing before deriving code. No register access, firmware execution, DMA or radio I/O is part of this gate.

### Gate B — build host-only, non-hardware tests

Create parsers and unit tests for the candidate QuZ firmware container, command layouts, RX/TX descriptor decoding and bounds. Any firmware used for format tests must be an unmodified, appropriately licensed public binary with pinned provenance and hashes. Parsing a firmware file must never execute it or touch the Wi-Fi device.

The existing AX211 firmware parser pins API 77; confirm its format and constraints on the QuZ/JF candidate before reusing it. Do not assume the SO/GF PNVM flow applies to QuZ/JF.

### Gate C — design a separate AX201 Windows radio backend

Create a new AX201/QuZ implementation boundary rather than adding `A0F0` to the AX211 INF. It must have explicit stages for PnP resources, interrupts, firmware/NVM initialization, RX-only capture, bounded TX, AWDL IBSS/ACK operation and teardown. Each stage needs timeouts, a stop path and verified DMA quiescence before any buffer is released.

No register writes, firmware start, DMA or packet transmission is allowed until the hardware-specific sequence is independently reviewed and a safe signed-driver path exists.

### Gate D — resolve Windows driver trust before laptop testing

The existing AX211 preview is not suitable for this laptop: it only accepts one exact AX211 hardware ID and its current deployment requires Test Mode with Secure Boot off. That deployment is incompatible with the project's current laptop constraints.

Before installing any replacement driver, establish a Microsoft-supported signing and deployment route that works on Windows 11 Home with Secure Boot left enabled, or stop. One candidate is Microsoft **attestation signing**: Microsoft documents support for Windows 10 Desktop and later, including kernel-mode drivers, for testing scenarios; it requires Hardware Developer Program registration and an EV code-signing certificate, and it is not WHQL certification or a retail Windows Update channel. Its exact installability on this Windows 11 Home device and this custom AX201 driver package must be verified before any test. References: https://learn.microsoft.com/en-us/windows-hardware/drivers/dashboard/code-signing-attestation and https://learn.microsoft.com/en-us/windows-hardware/drivers/dashboard/driver-signing-offerings. A local test signature is not acceptable. Microsoft's separate **preproduction Secure Boot** route provisions test keys and, per its documented process, temporarily disables Secure Boot and clears/replaces Secure Boot keys; that route conflicts with the user's "leave Secure Boot unchanged" requirement and is excluded. Reference: https://learn.microsoft.com/en-us/windows-hardware/drivers/install/preproduction-driver-signing-and-install. A forced INF is never an acceptable substitute.

### Gate E — staged validation on the exact Lenovo

Only after Gates A–D pass: confirm stock-driver backup and recovery design, install a correctly signed AX201-specific driver with explicit user approval, first validate safe startup/shutdown and RX-only behavior, then isolated TX, then AWDL discovery, then small-file transfer. Every stage must restore the original Intel driver and verify the radio is back in its normal Windows state.

## Current conclusion

The best current path is **a purpose-built Windows QuZ/JF radio backend for the existing AX201**, reusing DropWin's AirDrop protocol/application layers and studying Linux `iwlwifi`/OWL for AX201 behavior. This is substantially more promising than the earlier assumption that the AX201 hardware itself was unsuitable. It is still a driver-porting project, not a ready-made download or a guaranteed result.

The immediate next engineering task is Gate A: produce a source-backed QuZ/JF hardware/firmware/command map. Do not change anything on the user's laptop while doing so.


## Confirmed Lenovo Windows capability report — 2026-11-16

DropWin's read-only diagnostics were run on the target Lenovo Yoga Slim 7 14ITL05 with the exact AX201 PnP identifier:

`PCI\\VEN_8086&DEV_A0F0&SUBSYS_00748086&REV_20`

The report confirms the existing host-side classifier identifies the adapter as Intel QuZ / device family 22000. It reports the following from the installed Intel driver 24.80.0.2 (INF `oem227.inf`) and Windows WLAN capability query:

| Windows-reported capability | Observed result |
|---|---|
| Network Monitor mode | Not supported |
| Promiscuous mode | Not supported |
| IBSS | Not supported |
| Action frames | Supported |
| Wi-Fi Direct device / P2P discovery | Supported |
| Simultaneous channels | 0 |
| Firmware string reported by Windows | D4.79 |
| WDI (Windows / IHV) | 0.1.1.13 / 0.1.1.12 |
| WiFiCx | Not supported |

The report also returns antenna count, maximum simultaneous channel count at the system level, and coexistence information as unavailable/unknown. Those missing values must be treated as **not reported**, not as proof that the physical adapter has zero antennas or no radio.

This real-device report strengthens the existing conclusion about the stock Windows miniport: it does not advertise Network Monitor, promiscuous, or IBSS operation, and reports no simultaneous-channel capability. The positive Action-frame and Wi-Fi Direct results do not establish arbitrary raw 802.11 MPDU access, AWDL, or AirDrop interoperability. In particular, Wi-Fi Direct discovery is not AWDL peer discovery.

The output is consistent with the documented Linux AX201 QuZ mapping and the host-only parser. It does not identify the controller RF-ID, so JF versus HR remains unresolved. The Windows firmware label `D4.79` is recorded as an observation only; it must not be translated into an Intel Linux uCode filename or used to infer the RF family.

**Engineering consequence:** do not spend effort trying to enable AWDL through a Windows WLAN setting or by toggling an NDIS filter over this stock miniport. Continue the offline, source-based QuZ hardware/firmware/descriptor map. Any future custom radio path is a separate driver-development effort and remains gated on an independently reviewed design and a viable signed deployment route. The user's stock Intel driver, Secure Boot, and Kernel DMA Protection remain unchanged.


## Static TX/RX descriptor comparison — 2026-11-16

A source-level comparison of Linux iwlwifi's QuZ path with the public AX211 Windows prototype identifies some reusable *wire layouts*, but also a queue-counter difference that makes copying the AX211 session logic unsafe.

### TX descriptor: common Gen2 TFD layout is a reuse candidate

Linux maps the A0F0 QuZ device to `iwl_qu_long_latency_mac_cfg`; the QuZ MAC configuration sets `.gen2 = true`. Linux's Gen2 path therefore selects `struct iwl_tfh_tfd`, not the legacy `struct iwl_tfd`.

The Gen2 TFD layout in `iwl-fh.h` is:
- 16-bit little-endian number of active transfer buffers;
- 25 packed `iwl_tfh_tb` entries;
- each TB has a 16-bit little-endian byte length and a 64-bit little-endian DMA address (10 bytes);
- 32-bit padding.

Its size is 2 + (25 × 10) + 4 = **256 bytes**. Linux's source comments also describe a physical circular TFD ring of **256 descriptors** per TX queue for 22000-and-later hardware, with 256 bytes per descriptor for the 22000 layout.

The AX211 Windows reference's packet builder also reserves a 256-byte TFD buffer and writes the same broad Gen2-style fields (active TB count, 16-bit lengths, 64-bit DMA addresses). This makes the descriptor's basic serialization a plausible reuse candidate. It does **not** establish that the AX211 command payload, queue configuration, doorbell, status/completion, firmware API sub-versions or TX policy can be reused for QuZ. The AX211 builder is pinned to its own TX command version 10 and TX notification version 7; those versions need an independent QuZ/API-77 source check.

### Queue-size terminology: physical ring slots are not the logical counter modulus

Two Linux values must not be conflated:

- QuZ `iwl_22000_base.max_tfd_queue_size = 256`.
- AX210/SO `iwl_ax210_base.max_tfd_queue_size = 65536`.

The physical TX TFD circular buffer is documented separately in `iwl-fh.h` as 256 descriptor entries. In `pcie/tx-gen2.c`, `max_tfd_queue_size` is used by `iwl_txq_space()` to calculate the modular outstanding distance from `write_ptr - read_ptr`, and to prevent the full/empty ambiguity. Separately, `pcie/internal.h` maps a logical index to a physical descriptor slot using `index & (q->n_window - 1)`. Therefore the 256-versus-65536 configuration difference is **not** a statement that the physical ring contains 256 versus 65,536 TFD allocations. It changes the queue-accounting/counter-wrap model; the actual slot count is represented by `q->n_window`.

This corrects a possible ambiguity in the earlier shorthand “maximum TFD queue size”: do not describe 65,536 as the AX211 physical descriptor-ring allocation size.

The wrap behavior is explicit in the Linux source: `iwl_txq_inc_wrap()` returns `(++index) & (max_tfd_queue_size - 1)`. For QuZ this constrains the logical `write_ptr`/read-pointer sequence to a 256-value cycle. The Gen2 doorbell helper writes `write_ptr | (txq_id << 16)` to `HBUS_TARG_WRPTR`; queue selection is encoded separately from the low write index. The AX211 Windows reference instead keeps a 16-bit logical TX index, maps the physical TFD slot with `index & 255`, and writes `(index + 1) & 65535` in the low doorbell field. These are materially different logical-counter assumptions. The AX211 doorbell/index sequence must **not** be copied to QuZ by changing only the PCI ID or TFD ring constant. A QuZ port must follow the QuZ wrap rule and separately verify pointer initialization, completion/read-pointer updates and queue selection in source before any implementation.

### RX transfer descriptor: layout matches, queue policy still needs proof

Linux's `pcie/internal.h` defines the AX210-and-later RX transfer descriptor as a packed 16-byte structure:
- 16-bit little-endian RB ID;
- three reserved 16-bit words;
- 64-bit little-endian DMA address.

The AX211 Windows reference's `IWL_RX_TRANSFER` has the same field order and total size (16 bytes). This supports reuse of a small, explicitly little-endian descriptor serializer/parser. It does **not** prove that QuZ uses the AX211 ring depth, buffer size, status ring layout, completion processing or buffer-ownership lifecycle. The AX211 prototype currently chooses 512 RX descriptors and 4 KiB buffers; those are reference implementation parameters, not yet a QuZ port specification.

Linux's RX comments describe a shared host/firmware buffer lifecycle with read/write indexes, replenishment and ownership transitions. The Windows implementation must account for this lifecycle and device-quiescence rules rather than merely matching the descriptor's C structure.

### Current reuse matrix

| Area | Finding | Decision |
|---|---|---|
| Gen2 TX TFD field layout | 256-byte packed TFD, 25 possible TB entries; common layout is plausible | Reuse only a tested serializer/layout definition |
| Physical TX TFD ring | 256 slots documented for 22000+ hardware | Candidate baseline; verify QuZ queue configuration |
| Logical TX counter | QuZ modulus 256; AX211 reference uses a 16-bit sequence/doorbell | **Do not reuse AX211 counter/doorbell logic** |
| RX free-buffer descriptor | QuZ pre-AX210 uses 8-byte address/VID word; AX210+ uses 16-byte transfer descriptor | QuZ-specific 8-byte encoder added; AX210 format explicitly excluded |
| RX ring depth | Linux QuZ config documents 512 RBDs without HE and 2048 with HE | Pure mode-dependent size helper added; active Lenovo RF/firmware mode still unverified |
| RX queue ownership/refill | Free/used rings, completion processing and buffer allocator lifecycle | Not implemented; requires separate state-machine mapping |
| TX command/notification API | AX211 reference pins command v10 / notification v7 | Verify against QuZ firmware/API before reuse |
| Firmware boot, NVM, DMA and IRQ sequence | Hardware-family-specific | No reuse without QuZ-specific source map and review |

### Primary source references

- Linux QuZ MAC configuration and queue parameters: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/22000.c
- Linux AX210/SO queue parameters: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/ax210.c
- Linux Gen2 TFD definition and physical-ring description: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/iwl-fh.h
- Linux Gen2 TX queue-space arithmetic and doorbell write: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/tx-gen2.c
- Linux TX pointer wrap and physical-slot mapping: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/internal.h
- Linux logical-to-physical TX slot mapping: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/internal.h
- Linux AX210+ RX transfer descriptor: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/internal.h
- AX211 reference descriptor/context layout: https://github.com/21Suspect/AirDrop-for-Windows/blob/main/native/intel/iwl_gen3.h and https://github.com/21Suspect/AirDrop-for-Windows/blob/main/native/intel/iwl_gen3.c
- AX211 reference TX packet builder: https://github.com/21Suspect/AirDrop-for-Windows/blob/main/native/intel/iwl_packet.c
- AX211 reference TX index/doorbell path: https://github.com/21Suspect/AirDrop-for-Windows/blob/main/native/intel/ax211_session.inc
- AX211 reference RX ring and ownership path: https://github.com/21Suspect/AirDrop-for-Windows/blob/main/native/intel/ax211_boot.inc

**Next static Gate A task:** trace the QuZ-specific command queue initialization, read/write pointer and doorbell updates, RX default queue setup, and completion/interrupt path. Build table-driven unit tests for descriptor sizes, endianness, index wrap and invalid lengths. These tests must operate on synthetic memory only. Do not add PCI register writes, DMA allocations, firmware start, RF operations or a laptop driver in this phase.

## Host-only TX/RX descriptor primitives — 2026-11-16

**Implementation milestone:** `dropwin/platform/intel_ax201_transport.py` now contains pure in-memory serializers for the QuZ-relevant Gen2/TFH TX TFD and QuZ multi-queue RX buffer descriptor, plus isolated TX queue-counter arithmetic.

- A TFH TFD is serialized to exactly 256 bytes: a little-endian 16-bit buffer count, 25 packed 10-byte entries (`u16 length + u64 address`), and a zeroed 32-bit pad. The serializer checks 1–25 segments, each no larger than 4 KiB minus 4 bytes, a combined frame limit of 8 KiB, and the QuZ TX DMA mask of 36 bits (the descriptor's address field is 64 bits wide, but that is not the hardware DMA aperture).
- **Correction to the initial RX prototype:** QuZ is device family 22000, which is earlier than AX210 in Linux's device-family ordering. Linux's PCIe RX code therefore uses the legacy 8-byte `u64` RBD for QuZ, packing the 12-bit virtual buffer ID into the low address bits (`page_dma | vid`); the 16-byte `iwl_rx_transfer_desc` applies to AX210 and later, not QuZ. The earlier 16-byte AX210-shaped serializer has been removed. The QuZ encoder now requires a nonzero 12-bit buffer ID and a 4-KiB-aligned 64-bit DMA address.

- The QuZ RX ring count is mode-dependent in Linux's family configuration: 512 RBDs for non-HE and 2048 for HE. DropWin now models this as an explicit caller-supplied boolean, rather than guessing the Lenovo's active firmware/RF mode. The RX ring arithmetic helper follows Linux's one-empty-slot rule, `(read - write - 1) & (size - 1)`. VID validation uses Linux's inclusive valid range `1..RX_POOL_SIZE(num_rx_bufs)`; the host helper expresses this as `1..pool_size`, not `1..pool_size-1`. Later sections document the additional synthetic ownership and completion-cursor models.
- QuZ has multi-queue RX enabled. For pre-AX210 families, Linux stores each RX free-buffer descriptor as an 8-byte address/VID word and reads each used/completion entry as a 32-bit word whose low 12 bits are the VID. The code has a bounded extractor for that VID and a separate inclusive pool-bound validator. A synthetic ownership ledger models a narrow subset of the VID lifecycle, and host-only helpers model completion cursor distance and 8-entry restock pointer alignment. These models do not implement the actual completion/status memory, allocator batching, refill, interrupts or teardown. QuZ's active queue depth and RF/firmware configuration remain unresolved for the Lenovo while its JF/HR RF identity is unknown.
- The QuZ TX write counter advances with a 256-entry power-of-two mask. A helper reports the modular read/write distance, with the documented one-slot-empty discipline (at most 255 pending descriptors).
- A pure helper encodes QuZ's pre-AX210 scheduler byte-count table entry: TX byte count rounded up to 32-bit words in the low 12 bits, plus the TFD fetch-chunk count derived from the populated TFD prefix in the upper bits. It returns two bytes only; it never writes the scheduler table.
- A separate helper constructs the Gen2 `HBUS_TARG_WRPTR` value from a queue ID and write pointer. It returns an integer only; it never writes a register.

The layout is cross-referenced against Linux `iwl-fh.h` (TFH TFD/TB and 22000 ring constants), `pcie/tx-gen2.c` (write-pointer doorbell), `pcie/rx.c` (QuZ/AX210 RBD-format split and 12-bit VID), and `iwl-config.h` (family ordering). QuZ RX completion VID extraction, RX ring sizes and free-slot arithmetic follow `pcie/rx.c` and the QuZ family configuration in `cfg/22000.c`. See:
- https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/iwl-fh.h
- https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/tx-gen2.c (TFD pointer wrap and doorbell)
- https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/queue/tx.c (pre-AX210 byte-count table entry construction)
- https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/rx.c
- https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/22000.c
- https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/iwl-config.h

**Strict boundary:** these serializers operate only on caller-supplied integers and Python objects. They do not allocate/map DMA, choose a DMA mask, create queue memory, populate the TX byte-count table, configure interrupt handling, post descriptors, write a doorbell, or start firmware. The full QuZ RX ring/completion/status lifecycle and its parameters remain unimplemented. AX211 queue/session code is not copied. Synthetic tests verify byte layout and bounds only; no physical adapter validation or AWDL capability is claimed.


## Synthetic QuZ RX buffer-ownership ledger — 2026-11-16

A pure-Python `QuzRxBufferLedger` now models the VID ownership transitions documented by Linux's pre-AX210 multi-queue RX path:

- `FREE -> POSTED -> COMPLETED` for a buffer placed in a queue and returned by a completion.
- If the page was not taken by an upper layer: `COMPLETED -> FREE`, representing reuse of the same page.
- If the page was taken: `COMPLETED -> USED -> ALLOCATOR_EMPTY -> ALLOCATOR_ALLOCATED -> FREE`, representing the need for a replacement page before the VID can be reposted.

The ledger rejects out-of-pool VIDs, completion of a VID that is not currently posted, duplicate completion, and invalid ownership transitions. It exposes state counts for invariant-oriented synthetic tests.

**Scope limitation:** this is an ownership *model*, not a Linux RX implementation. It intentionally does not model the per-queue RX completion/status rings, multi-queue batching thresholds, allocator request accounting, emergency path, memory/page allocation, DMA mapping, queue restock, interrupts, or stop/teardown synchronization. In particular, returning a replacement to `FREE` is a logical state transition only; it does not imply that a page exists or that any DMA mapping is valid. The Linux reference describes these additional mechanisms and the need to stop/synchronize RX before freeing resources. No hardware access or laptop changes were made.

Source basis: Linux `pcie/rx.c` documents the VID lookup/invalid flag, completion handling, reused-page versus stolen-page paths, allocator movement, and RX DMA stop path: https://linux.googlesource.com/linux/kernel/git/torvalds/linux/+/cdb3033e191fd03da2d7da23b9cd448dfa180a8e/drivers/net/wireless/intel/iwlwifi/pcie/rx.c (notably the RBD lifecycle comments, `iwl_pcie_get_rxb`, `iwl_pcie_rx_handle_rb`, and `iwl_pcie_rx_stop`).


## QuZ MQ RX completion and restock pointer arithmetic — 2026-11-16

Two additional host-only helpers capture details specific to the QuZ multi-queue RX path:

- `quz_rx_completed_count(host_read, firmware_read, queue_size)` computes the number of completion entries between the host cursor and the firmware's exclusive status cursor, including wrap-around. The Linux handler processes entries until its cursor equals the firmware status index.
- `quz_rx_restock_doorbell_pointer(write_pointer, queue_size)` rounds the host write index down to an eight-entry boundary. Linux records `write_actual = round_down(write, 8)` and, for this pre-BZ multi-queue family, updates the RFH per-queue free-buffer write-index register. The helper returns only the aligned integer; it does not select a register, write it, or access hardware.

These arithmetic helpers do not establish the active Lenovo queue count, RF configuration, completion interrupt mapping, or firmware initialization sequence. The completion cursor is not a free-running hardware counter model; it is a bounded ring index as used by the cited RX handler.

Source: Linux `pcie/rx.c` describes the QuZ 32-bit used-buffer completion entry (low 12-bit VID), completion processing, queue-index wrap, 8-entry restock alignment, and pre-BZ RFH queue write-index update: https://linux.googlesource.com/linux/kernel/git/torvalds/linux/+/cdb3033e191fd03da2d7da23b9cd448dfa180a8e/drivers/net/wireless/intel/iwlwifi/pcie/rx.c (see `iwl_pcie_rxq_inc_wr_ptr`, `iwl_pcie_rxmq_restock`, `iwl_pcie_get_rxb`, and `iwl_pcie_rx_handle`).


## QuZ multi-queue RX source map — 2026-11-16

The Linux reference makes the following QuZ-specific distinctions explicit:

| Object | QuZ / pre-AX210 representation | Meaning |
|---|---|---|
| Free RBD ring entry | 64-bit little-endian (`__le64`) | `page_dma | VID` |
| Used/completion ring entry | 32-bit little-endian (`__le32`) | low 12 bits carry VID |
| RX status block | `struct iwl_rb_status` | firmware-published closed-RB cursor/status |
| RX ring depth | `trans->cfg->num_rbds` | selected RF configuration's RBD count |
| VID lookup table | `RX_POOL_SIZE(trans_pcie->num_rx_bufs)` entries | global buffer pool; VID indexes `global_table[vid - 1]` |

The RX ring depth and VID pool size are separate quantities in the driver and must not be treated as interchangeable. The public configuration header defines `IWL_NUM_RBDS_NON_HE` as 512 and `IWL_NUM_RBDS_HE` as 2048 (and an EHT constant of 4096 for newer configurations); the active value is carried in the RF configuration's `num_rbds` field. The existing host helper models the two documented QuZ modes only and does not infer which value the Lenovo uses.

For each pre-AX210 multi-queue completion, Linux extracts the 12-bit VID, rejects zero and values above the VID pool bound, resolves `global_table[vid - 1]`, rejects an already-invalid buffer, and marks the buffer invalid before processing. When a free buffer is restocked, Linux clears that invalid flag, writes the 64-bit `page_dma | vid` entry, advances the queue write index, rounds the published index down to a multiple of eight, and updates the per-queue RFH free-buffer write-index register. The QuZ-family RX stop path disables RFH RX DMA and polls the RXF DMA idle bit with a bounded timeout; this is a hardware operation and is deliberately not implemented by DropWin.

The source also confirms that the QuZ MAC config enables multi-queue RX and uses device family 22000. The dynamic firmware-name builder selects `jf` or `hr` from the RF type read from hardware; the current QuZ firmware declarations in `cfg/22000.c` list the QuZ HR API-77 image. This does **not** allow the Lenovo's JF/HR identity to be inferred from its PCI PnP ID or Windows firmware label. RF-ID remains an explicit unresolved hardware fact.

Primary sources:
- `pcie/rx.c`: https://linux.googlesource.com/linux/kernel/git/torvalds/linux/+/cdb3033e191fd03da2d7da23b9cd448dfa180a8e/drivers/net/wireless/intel/iwlwifi/pcie/rx.c
- `iwl-config.h`: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/iwl-config.h
- `cfg/22000.c`: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/22000.c
- `iwl-drv.c` RF-type firmware-name selection: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/iwl-drv.c

This source map is documentation only. It does not implement completion-ring allocation, shared status memory, global VID table allocation, DMA, RFH programming, firmware boot, interrupt delivery, or teardown.


## QuZ firmware/NVM, RX lifecycle, interrupts and Windows driver design — 2026-11-16

This section records a first source-level reconstruction against upstream Linux `iwlwifi`. It is a design map, not a port of the Linux driver. No device I/O or hardware validation is implied.

### 1. Firmware identity and initialization boundary

The A0F0 PCI match selects the QuZ MAC configuration. The firmware prefix is not selected from the PCI ID alone: `iwl_drv_get_fwname_pre()` combines the MAC revision family with the controller RF-ID type. For QuZ it fixes the MAC portion to `QuZ-a0`; RF types JF1/JF2 select `jf-b0`, and HR1/HR2 select `hr-b0`. The QuZ family base in `cfg/22000.c` constrains the firmware API to 77, so the candidate names are:

- `iwlwifi-QuZ-a0-jf-b0-77.ucode`
- `iwlwifi-QuZ-a0-hr-b0-77.ucode`

The effective API interval is calculated from the MAC-family and RF configuration ranges; do not infer it from the filename or from Windows' `D4.79` label. The Linux request path computes the firmware prefix only after it has a hardware RF-ID and chooses an API within the intersected supported range. The firmware is a TLV container; the parser inventories sections and the driver then follows its init/runtime firmware lifecycle. DropWin's current TLV parser is only a bounded offline container inventory: it does not verify signatures, validate every section semantic, or establish that a binary is suitable for this Lenovo.

**NVM is a later firmware-command stage, not a substitute for RF-ID.** The Linux MVM NVM path reads NVM sections through `NVM_ACCESS_CMD` after firmware command transport is available. It requests section/offset/length chunks, checks response length, status and returned offset, and accumulates the sections used by the driver (hardware, software, calibration, production, PHY SKU and regulatory data where present). The JF RF configuration declares extended NVM, version `0x0a1d`, and API 77. The QuZ HR filename is also declared by the QuZ MAC family; its effective API must be resolved through the MAC/RF range intersection, not by copying the newer BZ/SC HR API-100 configuration. No QuZ PNVM companion is declared alongside the QuZ firmware in the cited Linux/OpenBSD inventories; do not stage the AX211 SO/GF PNVM flow on this path.

**Still open for Gate A/B:** pin the exact QuZ API-77 init/runtime section requirements and command/notification version table; map the complete QuZ startup order from PCI ownership/interrupt setup through firmware ALIVE, NVM read, runtime configuration and RF bring-up; verify the TLV parser against a lawfully sourced, hash-pinned QuZ/JF or QuZ/HR image without executing it. The NVM command source is generic MVM code; the precise QuZ command-version compatibility must be cross-checked against API 77 before any implementation.

Sources:
- Linux QuZ MAC/API 77 and JF/HR firmware prefixes: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/22000.c
- Linux JF API 77, NVM version 0x0a1d and extended-NVM declaration: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/rf-jf.c
- Linux RF-ID-dependent firmware prefix and MAC/RF API intersection: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/iwl-drv.c
- Linux RF-ID type codes: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/iwl-config.h
- Linux NVM_ACCESS read/chunk validation and section collection: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/mvm/nvm.c
- Linux CSR RF-ID masks: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/iwl-csr.h

### 2. QuZ multi-queue RX: source-derived lifecycle

The Linux source separates five things that must not be collapsed into one “RX ring”:

1. **Free RBD ring per RX queue:** QuZ is pre-AX210, so each free descriptor is an 8-byte little-endian `page_dma | VID` word. The low 12 bits carry a nonzero virtual buffer ID; the DMA address must leave those low bits available.
2. **Used/completion ring per RX queue:** firmware returns completion entries containing the VID. The host validates the VID against the separately sized buffer pool and resolves it through `global_table[vid - 1]`.
3. **RX status memory:** per-queue status/write-pointer state tells the host where firmware has completed work. Linux allocates a contiguous coherent status area for all configured RX queues.
4. **VID pool and global table:** the buffer pool size is derived from the configured number of RX buffers plus allocator reserve; it is not the same quantity as the free-ring depth. VID zero is reserved.
5. **Allocator/refill lists:** Linux keeps buffers in queue free/used lists and allocator empty/allocated lists. Page reuse and page replacement are distinct paths; replacement may be batched and performed asynchronously.

The initialization path allocates per-queue DMA rings and the contiguous status area, creates the RX pool and VID lookup table, zeros host cursors/status, initializes NAPI for each RX queue, assigns VIDs, and partitions buffers between the default queue and allocator reserve. For multi-queue devices, the RFH setup then supplies each queue's free-ring base, used-ring base and status address, resets the hardware indices, configures buffer size and enables the relevant RX queues. The initial host restock publishes free descriptors and advances the write pointer in groups of eight.

The receive path reads the firmware status cursor, executes a DMA read barrier before consuming completion descriptors and packet buffers, then processes entries up to that cursor and within the NAPI budget. The VID lookup/ownership checks prevent accepting unknown or already-invalid buffers. The NAPI poll path reenables or clears the corresponding interrupt after polling completes; the MSI-X path maps a queue to its vector, with a special shared-vector case.

The teardown source exposes two separate quiescence conditions:

- For QuZ multi-queue RX, `iwl_pcie_rx_stop()` disables `RFH_RXF_DMA_CFG` and polls `RXF_DMA_IDLE` with a 1000-unit timeout.
- The Gen2 PCIe stop path separately requests bus-master stop through `CSR_RESET` for pre-BZ devices and polls `MASTER_DISABLED` (100 microseconds in the Linux helper). Linux warns if that bus-master stop poll times out. A Windows implementation must be stricter: a timeout is a hard failure, DMA-backed memory must remain quarantined, and teardown must not free pages/rings while the device may still access them.
- NAPI synchronization is explicit (`napi_synchronize` for every RX queue) before the associated processing context is retired; coherent status and per-queue DMA memory, pool tables and pages are freed in the later cleanup path.

The source map is now sufficient to specify the objects and ordering constraints, but not to implement them safely. In particular, DropWin still has no allocator, DMA mapping, status memory, used-ring memory, interrupt/DPC path, hardware quiescence, or teardown implementation. Its `QuzRxBufferLedger` remains a synthetic model, not a faithful allocator or concurrency model.

Sources:
- QuZ RX allocation, initialization, completion handling, NAPI synchronization, stop and free: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/rx.c
- QuZ RX ring sizes and MAC/RX configuration: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/cfg/22000.c
- QuZ Gen2 bus-master stop and reset path: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/trans-gen2.c
- PCIe interrupt handling and vector setup: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/trans.c
- QuZ RX structures and DMA ring fields: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/intel/iwlwifi/pcie/internal.h

### 3. TX, interrupts and DMA: current boundary

The TX research currently establishes the 256-byte Gen2 TFD serialization, the QuZ 36-bit DMA aperture, the byte-count table encoding, and the QuZ 256-value logical queue-counter wrap. It does not yet reconstruct TX queue-context allocation, scheduler setup, command-specific API-77 payloads, completion/read-pointer updates, interrupt-to-completion association, timeout recovery or queue teardown. RX and TX both depend on DMA ordering, but the RX `dma_rmb()` observation is not a substitute for a complete TX memory-ordering design. No DMA allocation or mapping API is implemented.

Interrupts are not a single callback: Linux has an ISR path that reads/acknowledges interrupt causes (ICT or direct status), masks/filters causes under an IRQ lock, then hands RX work to per-queue NAPI pollers; NAPI uses a budget and only restores interrupt service when polling completes. A Windows design needs an equivalent bounded split between the interrupt service routine and deferred processing, with per-queue synchronization, cancellation on power transitions, and a guarantee that no DPC/work item can touch freed DMA memory. This remains design work, not implemented code.

### 4. JF/HR classification: source validation, device still unknown

The RF-ID type values in Linux `iwl-config.h` match the existing offline classifier:
- JF2 = `0x105`
- JF1 = `0x108`
- HR2 = `0x10A`
- HR1 = `0x10C`

Linux extracts the type with `(rf_id & 0x0FFF000) >> 12` and the RF step with `(rf_id & 0x0000F00) >> 8`. The classifier's mapping is therefore source-aligned. This validates the parser's mapping, **not the Lenovo's identity**: no actual `CSR_HW_RFID` value has been read from the Yoga Slim 7. The PnP revision, subsystem ID and Windows firmware string do not supply that value. JF/HR remains unknown until an approved, read-only, independently reviewed acquisition path exists; no register access is authorized or required for this documentation milestone.

### 5. Windows 11 Secure Boot-compatible driver route

The AX211 prototype is not a base to extend by changing its INF. The AX201 needs a separate QuZ-aware driver package and a reviewed device-ownership model. The intended architecture is:

- **Kernel driver:** a hardware-specific PCIe/KMDF driver boundary for PnP resource ownership, interrupt registration, DMA enabler/common buffers, power management, firmware command transport, RX/TX queues, watchdogs and a fail-closed teardown path. It must not expose arbitrary register or DMA operations to user mode.
- **User-mode radio/AWDL service:** consumes bounded, versioned IOCTL messages and owns AWDL scheduling, peer/discovery state and packet policy. It cannot provide DMA addresses or program hardware.
- **DropWin application:** reuses the existing consent, sender metadata, file validation and receive UI.
- **Virtual network interface:** only if required by the final AWDL/IP architecture; it is a separate component and must not be mistaken for the physical-radio driver.

This is an architecture proposal, not a driver skeleton. A custom driver must not be installed alongside the Intel function driver in a way that permits two drivers to own the same PCI function.

**Signing gate:** Microsoft's current documentation says attestation signing supports Windows Desktop kernel-mode drivers on Windows 10 and later, requires a Hardware Developer Program account and an EV certificate, and does not require HLK tests. It is not Windows certification and attestation-signed drivers are not published to Windows Update for retail audiences. This is the only plausible near-term Microsoft signing route for a controlled test package while retaining Secure Boot; it still must be validated against the exact Windows 11 Home build, package type, device installation policy and platform security configuration before any laptop test. Production-quality distribution should target WHCP/HLK certification. Test Mode, local test-signing and Secure Boot disablement remain excluded.

References:
- Microsoft attestation signing requirements and limitations: https://learn.microsoft.com/windows-hardware/drivers/dashboard/code-signing-attestation
- Microsoft driver-signing options, Windows Desktop support and certification distinction: https://learn.microsoft.com/windows-hardware/drivers/dashboard/driver-signing-offerings
- Microsoft kernel-mode signing policy: https://learn.microsoft.com/windows-hardware/drivers/install/kernel-mode-code-signing-policy--windows-vista-and-later-

### Gate A/B status after this pass

- **Firmware/NVM:** partial source map recorded; exact API-77 command/version and startup sequence still open.
- **RX/TX/interrupt/DMA:** RX allocation, free/used/status structures, NAPI ordering and quiescence constraints mapped from source; TX completion and full IRQ/DMA lifecycle still open. No hardware-facing implementation.
- **JF/HR:** numeric classification confirmed from upstream source; physical Lenovo variant remains unknown.
- **Secure Boot driver:** architecture and Microsoft attestation-signing candidate documented; exact Windows 11 Home acceptance and a full signed package are not yet demonstrated.

The next safe work item is to turn the source map into a versioned host-only specification and synthetic state tests for queue ownership, RX completion ordering, interrupt/NAPI state transitions, and failure/timeout handling. Do not write a PCI/DMA/firmware driver until that specification has an independent review and the signing gate is resolved.


## Synthetic fail-closed DMA teardown gate — 2026-11-16

Added `dropwin/platform/intel_ax201_lifecycle.py` with a pure-Python `QuzDmaQuiescenceGate`. It requires three independent synthetic confirmations before its predicate allows DMA-memory release: RX DMA idle, PCIe bus mastering disabled, and RX NAPI/deferred work synchronized. A timeout/failure permanently closes the gate; the model refuses later “success” flags and reports that memory must remain quarantined.

Tests in `tests/test_intel_ax201_lifecycle.py` cover each missing prerequisite, the independent nature of RX idle versus bus-master stop and NAPI synchronization, and permanent fail-closed behavior.

This is a safety-contract model only. It does not issue a stop request, poll a device, synchronize real Windows DPC/work items, allocate or free DMA memory, or prove the Linux timing values are sufficient for a Windows implementation. The Windows driver must implement and independently validate those operations using the actual WDF/PCIe lifecycle.
