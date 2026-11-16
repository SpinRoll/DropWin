from __future__ import annotations

import subprocess

from dropwin.platform import windows


def test_wifi_diagnostics_are_not_available_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(windows.platform, "system", lambda: "Linux")
    assert "solo su Windows" in windows.collect_wifi_diagnostics()


def test_wifi_diagnostics_collects_read_only_netsh_reports(monkeypatch) -> None:
    monkeypatch.setattr(windows.platform, "system", lambda: "Windows")
    calls: list[list[str]] = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, stdout="Report di prova", stderr="")

    monkeypatch.setattr(windows.subprocess, "run", fake_run)
    report = windows.collect_wifi_diagnostics()

    assert len(calls) == 2
    assert calls[0][-3:] == ["show", "drivers"][-3:]
    assert calls[1][-2:] == ["wirelesscapabilities"]
    assert "non dimostrano il supporto AWDL" in report
    assert report.count("Report di prova") == 2
