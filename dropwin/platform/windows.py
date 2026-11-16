from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass

from dropwin.platform.intel_ax201 import identify_intel_radio


@dataclass(frozen=True)
class WirelessAdapter:
    name: str
    description: str
    pnp_device_id: str = ""


def get_wireless_adapters() -> list[WirelessAdapter]:
    """Read adapter names using PowerShell without changing driver settings.

    An empty result means detection was unavailable, not necessarily that Wi-Fi is absent.
    """
    if platform.system() != "Windows":
        return []

    script = (
        "Get-NetAdapter -ErrorAction SilentlyContinue | "
        "Where-Object { $_.InterfaceDescription -match 'Wi-Fi|Wireless|802.11' } | "
        "Select-Object -Property Name, InterfaceDescription, PnPDeviceID | ConvertTo-Json -Compress"
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
        pnp_device_id = str(item.get("PnPDeviceID") or "").strip()
        if name or description or pnp_device_id:
            adapters.append(
                WirelessAdapter(
                    name=name,
                    description=description,
                    pnp_device_id=pnp_device_id,
                )
            )
    return adapters


def collect_wifi_diagnostics() -> str:
    """Collect read-only Windows WLAN reports; this does not test or enable AWDL."""
    if platform.system() != "Windows":
        return "La diagnostica è disponibile solo su Windows."

    reports: list[str] = [
        "DIAGNOSTICA WI-FI DROPWIN",
        "Raccolta in sola lettura: nessuna impostazione o driver viene modificato.",
        "Questi report NON dimostrano il supporto AWDL.",
        "",
        "=== Identificazione hardware Wi-Fi ===",
    ]

    adapters = get_wireless_adapters()
    if not adapters:
        reports.append("Inventario PnP non disponibile.")
    for adapter in adapters:
        reports.append(
            f"{adapter.name}: {adapter.description or 'descrizione non disponibile'}"
        )
        if not adapter.pnp_device_id:
            reports.append("  PnPDeviceID non disponibile.")
            continue

        reports.append(f"  PnPDeviceID: {adapter.pnp_device_id}")
        profile = identify_intel_radio(adapter.pnp_device_id)
        if profile is None:
            reports.append("  Profilo Intel AX201 QuZ non riconosciuto da questo ID.")
            continue

        reports.append(
            "  Profilo MAC: Intel QuZ / device family 22000 "
            f"(max TFD queue: {profile.max_tfd_queue_size})."
        )
        reports.append(
            "  RF-ID non esposto dal PnP ID: famiglia JF/HR ancora da confermare."
        )
        reports.append(
            "  Identificazione hardware, non certificazione di compatibilità AWDL."
        )

    for title, arguments in (
        ("Driver Wi-Fi", ["netsh.exe", "wlan", "show", "drivers"]),
        ("Funzionalità Wi-Fi", ["netsh.exe", "wlan", "show", "wirelesscapabilities"]),
    ):
        reports.extend(["", f"=== {title} ==="])
        try:
            result = subprocess.run(
                arguments,
                check=False,
                capture_output=True,
                text=True,
                timeout=12,
                errors="replace",
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            reports.append(f"Comando non disponibile: {error}")
            continue

        output = result.stdout.strip() or result.stderr.strip()
        reports.append(output if output else f"Nessun output (codice {result.returncode}).")

    return "\n".join(reports)
