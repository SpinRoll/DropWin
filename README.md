# DropWin

**A native AirDrop receiver for Windows 11 — research and development.**

DropWin aims to receive files sent from iPhone and Mac using Apple's AirDrop protocol, with a native Windows desktop interface and no external radio hardware.

> **Development status:** early research scaffold. Native AirDrop interoperability on Windows is not implemented yet. AWDL discovery, radio-frame access/injection, and the Windows Wi-Fi driver compatibility layer remain research tasks. No Wi-Fi adapter is currently claimed as supported, including Intel AX201.

## Project goals

- Windows 11 x64 desktop application.
- Receive files from Apple devices through native AirDrop, without installing an app on the Apple device.
- Prefer the computer's built-in Wi-Fi adapter; do not require external USB adapters or ESP32 hardware.
- Detect and report hardware/driver capabilities instead of assuming that 802.11ax implies AWDL support.
- Ask the user before accepting or saving incoming files.
- Keep the radio/AWDL backend separate from the desktop UI so hardware-specific support can be added incrementally.

## Current architecture

- `dropwin/app`: PySide6 desktop shell.
- `dropwin/platform`: Windows adapter inventory and capability-reporting boundary.
- `dropwin/awdl`: future AWDL backend interface. No packet injection or driver modification is performed by the scaffold.
- `tests`: platform-independent tests.
- `.github/workflows`: Windows CI and packaging.

## Development

Requirements: Windows 11 x64, Python 3.11 or newer.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m dropwin
```

## Build a Windows executable

```powershell
pip install -e ".[build]"
pyinstaller --noconfirm --clean packaging/dropwin.spec
```

GitHub Actions builds a Windows x64 executable on pushes and pull requests. The build is a desktop-shell prototype, **not** an AirDrop-capable release.


## AX201 host-only research component

The first AX201-specific host-side module, `dropwin/platform/intel_ax201.py`, parses the Windows PCI PnP ID for the Lenovo's AX201 and maps PCI device `A0F0` to the Linux QuZ MAC configuration. It keeps the RF family unresolved until a separately verified controller RF-ID is supplied, decodes the published RF-ID type/step fields, and then can resolve the corresponding QuZ/JF or QuZ/HR firmware filename. It also inventories the common Intel TLV firmware header and record boundaries from bytes supplied by a caller.

This module is an offline parser/classifier only. It does not query PCI registers, load firmware, install or replace drivers, allocate DMA, reset the adapter, or transmit/receive radio frames. Synthetic parser tests do not prove compatibility with a real firmware image. See [the AX201 Windows radio plan](docs/ax201-windows-radio-port.md).

## Hardware research target

The initial development machine reported:

- Intel Wi-Fi 6 AX201 160MHz
- PCI ID: `PCI\VEN_8086&DEV_A0F0`
- Driver reported by the user: `22.80.0.9`
- Windows Secure Boot: enabled

This is a test target only. It is not yet validated for AWDL. Secure Boot and the stock driver should remain unchanged during initial research.

## AX201 assessment — 2026-11-16

The test machine is a Lenovo Yoga Slim 7 14ITL05 (machine type 82A3), with an Intel Core i7-1165G7 and Intel Wi-Fi 6 AX201 160MHz. The user updated the adapter from Intel driver 22.80.0.9 to Intel driver **24.80.0.2** (date reported by Windows: 2026-09-16; INF: `oem227.inf`). The new report identifies firmware **D4.79**.

The post-update, read-only `netsh wlan show drivers` and `netsh wlan show wirelesscapabilities` report still advertises:
- 802.11b/g/n/a/ac/ax PHY modes, protected management frames, and Action frames.
- Network Monitor mode: **not supported**.
- Promiscuous mode: **not supported**.
- Simultaneous channel count: **0**; radio count: **0**.
- Wi-Fi Direct and its P2P discovery features: supported.

This is useful evidence that the newer Intel package installed correctly, but it does **not** expose the raw-frame/monitor capabilities currently needed for the proposed AWDL research path. Action-frame support is not equivalent to arbitrary raw 802.11 frame reception/transmission, and Wi-Fi Direct is not AWDL. The Windows capability report does not certify AWDL compatibility. The garbled accented characters in the copied report are a console text-encoding issue, not a radio capability result.

The Intel 24.80.0.2 update therefore did not change the key reported limitation. Do not install the `winawdl` custom radio driver on this AX201: that project is documented for a single Realtek RTL8852CE test machine and uses a hardware-specific UMDF/user-mode DMA design with significant security and reliability implications. Do not disable Secure Boot or Kernel DMA Protection as an experiment. No driver modification, adapter reset, test-signing change, or packet injection has been performed by DropWin.

Next decision gate: investigate whether a documented, safe AX201 interface exists for the raw radio operations AWDL requires. If no such path can be established, the built-in AX201 may not be a viable radio for native AirDrop on this machine. DropWin must not present this adapter as AWDL-compatible or imply that an application-only change can bypass missing driver/radio capabilities.

## Windows native AirDrop reference — 2026-11-16

A separate experimental project, [21Suspect/AirDrop-for-Windows](https://github.com/21Suspect/AirDrop-for-Windows), now documents real transfers through Apple's native AirDrop UI: iPhone to Windows, Windows to iPhone, and Mac to Windows. Its maintainer reports successful real-device transfers, but only on one exact Intel AX211 PCI device: `PCI\\VEN_8086&DEV_7A70&SUBSYS_00948086&REV_11`. This is meaningful proof that a Windows native AirDrop receiver is technically possible; it is not a supported solution for this project's AX201.

The reference implementation uses a custom Windows KMDF radio driver, Intel firmware, Owly/AWDL, and Wintun. It requires Windows Test Mode, administrator approval, Secure Boot disabled, and wired Ethernet while the Wi-Fi radio is dedicated to AirDrop. Its current preview has low throughput and known compatibility, pairing, security-audit, reliability, and recovery limitations. Its installer explicitly rejects adapters other than the exact tested AX211 hardware ID. Do not install its driver or attempt to force its INF on the Lenovo AX201. Do not disable Secure Boot or enable Test Mode on the user's machine as an exploratory step.

The user's AX201 hardware ID (`PCI\\VEN_8086&DEV_A0F0&SUBSYS_00748086&REV_20`) does not match that AX211 device. Adapting the radio driver to AX201 would be a separate hardware-specific driver-development effort; the AX211 result does not prove that AX201 can run the same firmware, DMA, radio configuration, or AWDL path. This is now the most relevant Windows-native research reference, but it does not remove the AX201 hardware blocker.

The EU DMA interoperability work must not be interpreted as a ready-made way for a Windows PC to register in Apple's existing AirDrop recipient sheet. The European Commission describes close-range file-transfer APIs as enabling third-party file-sharing apps that offer alternatives to AirDrop on iOS; that is different from making a Windows receiver appear in the native AirDrop UI. See the [Commission's explanation](https://digital-markets-act.ec.europa.eu/businesses-portal/interoperability/apple-specification-proceedings-interoperability-connected-devices-and-request-based-process_en) and its [May 2026 factsheet](https://digital-markets-act.ec.europa.eu/factsheet-how-dma-making-smartphones-better-interoperability-and-data-portability-case-studies-2026-05-11_en).

Next research gate: compare the AX211 reference's documented hardware/firmware assumptions against the Lenovo AX201, without changing the user's driver or boot-security configuration. Until a technically safe AX201 path is demonstrated, DropWin must not claim this laptop can receive native AirDrop.


## Deeper AirDrop interoperability findings — 2026-11-16

A more relevant hardware result changes the assessment of the Lenovo AX201: the Linux project [omdrop-owl](https://github.com/esslm/airdrop-on-windows) lists Intel AX201 as tested and working in both directions using the in-kernel `iwlwifi` driver and OWL in **exclusive** mode. Its README names Ubuntu 24.04 / kernel 6.8 and CachyOS / kernel 7.2.9 as AX201 test environments, and reports approximately 17 seconds for a 2.4 MB iPhone-to-PC photo and 10.5 seconds in the reverse direction on the Intel profile. During exclusive mode the Intel Wi-Fi connection is taken over for AWDL; this is a Linux implementation, despite the repository's historical name. This is encouraging evidence that AX201-class hardware can support native AirDrop when driven through a suitable Linux radio stack. The public table does not disclose the tested AX201 machine's full PCI subsystem/revision, so the Lenovo 82A3 still needs its own validation.

This does **not** provide a Windows driver or make Linux `iwlwifi` available to a normal Windows process. Windows' stock AX201 driver still reports Network Monitor and promiscuous modes unsupported on the user's machine. The Linux result instead suggests that the present blocker is not simply the AX201 radio silicon: it is the lack of an equivalent raw-radio/AWDL control path in the Windows driver stack.

The native Windows project [21Suspect/AirDrop-for-Windows](https://github.com/21Suspect/AirDrop-for-Windows) proves that a Windows KMDF radio path plus Owly/AWDL can make a PC appear in Apple's native AirDrop sheet, but its preview is hard-limited to one exact AX211 device (`8086:7A70`, subsystem `00948086`, revision `11`). Its native driver and bundled firmware target the AX211 SO/GF platform. The Lenovo AX201 identifies as `8086:A0F0`; Linux/OpenBSD driver references identify this QuZ/JF platform and its separate `QuZ-a0-jf-b0` firmware. The AX211 driver's INF must not be forced onto this AX201. Supporting AX201 in native Windows would require a distinct, hardware-specific radio-driver/firmware port and real hardware validation, not a simple adapter-ID change.

Other projects clarify the choices:
- [Windfall](https://github.com/UvejsGj/Windfall) has a Windows protocol library and GUI, but its own README says Windows radio/AWDL access is still pending; its real iPhone transfers run on Linux with OWL.
- [omdrop-owl-windows](https://github.com/dantdmdarealguy/omdrop-owl-windows) has a working native Windows AirDrop protocol path, but delegates raw radio to a USB ESP32. This violates this project's no-external-radio requirement.
- Projects that use Wi-Fi Direct or a QR/web page provide an AirDrop-like transfer, not a PC that appears in the iPhone's native AirDrop recipient list.

The European Commission's DMA close-range file-transfer measures are aimed at enabling third-party file-sharing solutions/apps on iOS as alternatives to AirDrop. They do not, by themselves, deliver a Windows AWDL receiver or guarantee that a PC registers in Apple's native AirDrop recipient sheet. See the [Commission's explanation and implementation timetable](https://digital-markets-act.ec.europa.eu/businesses-portal/interoperability/apple-specification-proceedings-interoperability-connected-devices-and-request-based-process_en).

**Current conclusion:** the Lenovo's internal AX201 is a promising radio, with third-party Linux evidence of successful AirDrop. There is no ready, validated Windows-native AX201 solution found in this research. The technically direct DropWin path is a separate Windows radio implementation for the AX201 QuZ/JF platform, using Linux `iwlwifi`/OWL behavior and the AX211 Windows port as references. Keep Secure Boot, Kernel DMA Protection and the stock Windows driver unchanged until a reviewed design and safe test plan exist. See [the Windows AX201 radio-backend plan](docs/ax201-windows-radio-port.md) for the hardware-family distinction, reuse assessment and staged engineering gates.

- [OpenDrop](https://github.com/seemoo-lab/opendrop) — Python AirDrop protocol implementation; upstream documents macOS and Linux/AWDL requirements, not native Windows support.
- [Open Wireless Link (OWL)](https://github.com/seemoo-lab/owl) — open AWDL implementation primarily for Linux.
- [winawdl](https://github.com/raph559/winawdl) — research implementation currently documented for Realtek RTL8852CE only; it uses a custom radio driver and is not compatible by assumption with Intel AX201.
- [Intel Wi-Fi driver support](https://www.intel.com/content/www/us/en/support/articles/000046918/wireless.html) — current Windows driver package and supported adapter list.

Any reuse of third-party code must follow its license and attribution requirements. No upstream repository is vendored in this initial scaffold.

## Security

AirDrop-compatible file receiving is a security-sensitive feature. The eventual implementation must not auto-accept arbitrary incoming files. It should display sender/file metadata, require explicit acceptance, validate destination paths, avoid overwrites by default, and enforce configurable file-size limits.

## License

This project is currently marked as **GPL-3.0-or-later** to align with the intended study/reuse of GPL-licensed OpenDrop code. Review all third-party licenses before incorporating code or distributing binaries. See [LICENSE](LICENSE).

## Disclaimer

DropWin is an independent community project and is not affiliated with, endorsed by, or sponsored by Apple Inc. AirDrop and Apple are trademarks of Apple Inc.

## AX201 Gen2 descriptor research

A host-only Python module now serializes the Intel Gen2/TFH TX TFD, QuZ's 8-byte RX buffer descriptor and its pre-AX210 TX byte-count table entry, enforces the 36-bit QuZ TX DMA aperture and 512-queue configuration, and tests queue pointer arithmetic. The RX encoder follows the pre-AX210 `page_dma | vid` layout; the 16-byte RX transfer descriptor belongs to AX210-and-later families and is intentionally not used for QuZ. This is offline format work only: DropWin does not allocate DMA, write device registers, load firmware, or transmit/receive radio frames. Pure helpers now model the Linux QuZ RX ring sizes (512 non-HE / 2048 HE), one-empty-slot free-space arithmetic, and VID bounds against a caller-selected pool; the actual active Lenovo RF/firmware mode and full free/used ownership/refill lifecycle remain unverified and unimplemented. A validated Windows radio backend is also still missing. See [the AX201 engineering notes](docs/ax201-windows-radio-port.md).
