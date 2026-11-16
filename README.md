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

## Hardware research target

The initial development machine reported:

- Intel Wi-Fi 6 AX201 160MHz
- PCI ID: `PCI\VEN_8086&DEV_A0F0`
- Driver reported by the user: `22.80.0.9`
- Windows Secure Boot: enabled

This is a test target only. It is not yet validated for AWDL. Secure Boot and the stock driver should remain unchanged during initial research.

## AX201 assessment — 2026-11-16

The test machine's Intel Wi-Fi 6 AX201 is supported by Intel on Windows 11. Intel's current public package at the time of this update is 24.80.0 and lists AX201 among supported adapters. This is ordinary adapter/OS support, **not** evidence of AWDL, monitor-mode, raw 802.11 frame injection, or AWDL channel scheduling support. Intel's public compatibility material does not claim AirDrop/AWDL support for this adapter.

The user's actual read-only report from the installed 22.80.0.9 driver confirms: 802.11b/g/n/a/ac/ax PHY modes; management frames and Action frames supported; Network Monitor mode **not supported**; promiscuous mode **not supported**; simultaneous channel count reported as 0/unavailable. Action-frame support alone is not enough to implement AWDL. The garbled accented characters in the copied report are a console text-encoding issue, not a Wi-Fi capability result.

The reported machine driver is 22.80.0.9. DropWin now includes a read-only diagnostic view based on `netsh wlan show drivers` and `netsh wlan show wirelesscapabilities`. These Windows reports can establish the driver and advertised WLAN capabilities, but cannot certify AWDL compatibility. No driver update, adapter reset, test-signing change, Secure Boot change, or packet injection is performed.

The current `winawdl` research project reports end-to-end AirDrop tests on one Realtek RTL8852CE machine only. Its design notes explain that the stock Realtek driver also lacked monitor/promiscuous mode, so the project bypasses it with a custom UMDF radio driver and user-mode DMA. This is highly hardware-specific and carries significant risk (including direct bus-master DMA and temporarily taking Wi-Fi away from Windows). It is an architectural reference, not a drop-in backend for Intel AX201. Do not install its driver on this PC.

Next decision gate: identify the PC manufacturer/model and check its approved driver package before considering an update from Intel 22.80.0.9 to Intel's newer AX201-compatible package. A driver update may improve reliability or expose different documented capabilities, but there is no evidence it will add monitor mode or AWDL. Re-run the same read-only reports after any approved update. If monitor/raw-frame access remains unavailable, investigate whether a safe, documented AX201 radio path exists before considering a custom driver; otherwise evaluate a different internal Wi-Fi chipset. Do not imply that an app-only wrapper can bypass missing driver/radio capabilities.


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
