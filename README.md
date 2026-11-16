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
