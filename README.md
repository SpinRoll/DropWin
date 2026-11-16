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

## Research references

- [OpenDrop](https://github.com/seemoo-lab/opendrop) — Python AirDrop protocol implementation; upstream documents macOS and Linux/AWDL requirements, not native Windows support.
- [Open Wireless Link (OWL)](https://github.com/seemoo-lab/owl) — open AWDL implementation primarily for Linux.
- [winawdl](https://github.com/raph559/winawdl) — experimental Windows AWDL/AirDrop work to study; its reported hardware support must not be generalized.

Any reuse of third-party code must follow its license and attribution requirements. No upstream repository is vendored in this initial scaffold.

## Security

AirDrop-compatible file receiving is a security-sensitive feature. The eventual implementation must not auto-accept arbitrary incoming files. It should display sender/file metadata, require explicit acceptance, validate destination paths, avoid overwrites by default, and enforce configurable file-size limits.

## License

This project is currently marked as **GPL-3.0-or-later** to align with the intended study/reuse of GPL-licensed OpenDrop code. Review all third-party licenses before incorporating code or distributing binaries. See [LICENSE](LICENSE).

## Disclaimer

DropWin is an independent community project and is not affiliated with, endorsed by, or sponsored by Apple Inc. AirDrop and Apple are trademarks of Apple Inc.
