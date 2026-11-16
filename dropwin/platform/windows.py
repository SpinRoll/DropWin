from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class WirelessAdapter:
    name: str
    description: str


def get_wireless_adapters() -> list[WirelessAdapter]:
    """Read adapter names using PowerShell without changing driver settings.

    An empty result means detection was unavailable, not necessarily that Wi-Fi is absent.
    """
    if platform.system() != "Windows":
        return []

    script = (
        "Get-NetAdapter -ErrorAction SilentlyContinue | "
        "Where-Object { $_.InterfaceDescription -match 'Wi-Fi|Wireless|802.11' } | "
        "Select-Object -Property Name, InterfaceDescription | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    if completed.returncode != 0 or not completed.stdout.strip():
        return []

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []

    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return []

    adapters: list[WirelessAdapter] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("Name") or "").strip()
        description = str(item.get("InterfaceDescription") or "").strip()
        if name or description:
            adapters.append(WirelessAdapter(name=name, description=description))
    return adapters
