from pathlib import Path

from scripts import doctor


def test_proxy_endpoint_parses_host_and_port() -> None:
    assert doctor._proxy_endpoint("socks5://127.0.0.1:2080") == ("127.0.0.1", 2080)
    assert doctor._proxy_endpoint(None) is None


def test_path_check_reports_required_missing_path_as_error(tmp_path: Path) -> None:
    check = doctor._path_check("sample", tmp_path / "missing.txt", required=True)

    assert check.status == "error"
    assert check.is_error is True


def test_path_check_reports_optional_missing_path_as_warning(tmp_path: Path) -> None:
    check = doctor._path_check("sample", tmp_path / "missing.txt", required=False)

    assert check.status == "warning"
    assert check.is_warning is True


def test_path_check_reports_existing_path_as_ok(tmp_path: Path) -> None:
    path = tmp_path / "exists.txt"
    path.write_text("ok", encoding="utf-8")

    check = doctor._path_check("sample", path, required=True)

    assert check.status == "ok"
    assert check.detail == str(path)
