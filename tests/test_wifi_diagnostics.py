from __future__ import annotations

import json
import subprocess

from dropwin.platform import windows


AX201_PNP_ID = r"PCI\VEN_8086&DEV_A0F0&SUBSYS_00748086&REV_20"


def test_wifi_diagnostics_are_not_available_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(windows.platform, "system", lambda: "Linux")
    assert "solo su Windows" in windows.collect_wifi_diagnostics()


def test_adapter_inventory_reads_pnp_device_id_without_modifying_settings(monkeypatch) -> None:
    monkeypatch.setattr(windows.platform, "system", lambda: "Windows")
    calls: list[list[str]] = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        payload = json.dumps(
            {
                "Name": "Wi-Fi",
                "InterfaceDescription": "Intel(R) Wi-Fi 6 AX201 160MHz",
                "PnPDeviceID": AX201_PNP_ID,
            }
        )
        return subprocess.CompletedProcess(arguments, 0, stdout=payload, stderr="")

    monkeypatch.setattr(windows.subprocess, "run", fake_run)
    adapters = windows.get_wireless_adapters()

    assert len(calls) == 1
    assert calls[0][0] == "powershell.exe"
    assert "Get-NetAdapter" in calls[0][-1]
    assert "PnPDeviceID" in calls[0][-1]
    assert len(adapters) == 1
    assert adapters[0].name == "Wi-Fi"
    assert adapters[0].pnp_device_id == AX201_PNP_ID


def test_wifi_diagnostics_collects_pnp_and_read_only_netsh_reports(monkeypatch) -> None:
    monkeypatch.setattr(windows.platform, "system", lambda: "Windows")
    calls: list[list[str]] = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        if arguments[0] == "powershell.exe":
            payload = json.dumps(
                {
                    "Name": "Wi-Fi",
                    "InterfaceDescription": "Intel(R) Wi-Fi 6 AX201 160MHz",
                    "PnPDeviceID": AX201_PNP_ID,
                }
            )
            return subprocess.CompletedProcess(arguments, 0, stdout=payload, stderr="")
        if arguments[-2:] == ["show", "drivers"]:
            return subprocess.CompletedProcess(
                arguments, 0, stdout="Report driver di prova", stderr=""
            )
        return subprocess.CompletedProcess(
            arguments, 0, stdout="Report capability di prova", stderr=""
        )

    monkeypatch.setattr(windows.subprocess, "run", fake_run)
    report = windows.collect_wifi_diagnostics()

    assert len(calls) == 3
    assert calls[0][0] == "powershell.exe"
    assert "PnPDeviceID" in calls[0][-1]
    assert calls[1][-2:] == ["show", "drivers"]
    assert calls[2][-1:] == ["wirelesscapabilities"]
    assert "non dimostrano il supporto awdl" in report.casefold()
    assert AX201_PNP_ID in report
    assert "profilo mac: intel quz" in report.casefold()
    assert "max tfd queue: 256" in report.casefold()
    assert "famiglia jf/hr ancora da confermare" in report.casefold()
    assert "Report driver di prova" in report
    assert "Report capability di prova" in report
