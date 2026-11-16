from dropwin.awdl.backend import AwdlBackend


def test_backend_is_explicitly_unavailable_until_implemented() -> None:
    status = AwdlBackend().probe()
    assert status.available is False
    assert "non implica compatibilità AirDrop" in status.message
