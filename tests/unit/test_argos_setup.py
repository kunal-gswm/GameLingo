import urllib.request
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from gamelingo.translation.argos_setup import ArgosSetupService, ModelStatus


def test_check_status_installed(monkeypatch):
    class MockLang:
        def __init__(self, code):
            self.code = code

        def get_translation(self, other):
            return "mock_translator"

    mock_get_langs = MagicMock(return_value=[MockLang("ja"), MockLang("en")])
    monkeypatch.setattr(
        "argostranslate.translate.get_installed_languages", mock_get_langs
    )

    status = ArgosSetupService.check_status("ja", "en")
    assert status["status"] == ModelStatus.READY
    assert "Model is installed" in status["message"]
    mock_get_langs.assert_called_once()


def test_check_status_not_installed(monkeypatch):
    mock_get_langs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "argostranslate.translate.get_installed_languages", mock_get_langs
    )

    status = ArgosSetupService.check_status("ja", "en")
    assert status["status"] == ModelStatus.NOT_INSTALLED
    assert "not installed" in status["message"]


def test_check_status_no_route(monkeypatch):
    class MockLang:
        def __init__(self, code):
            self.code = code

        def get_translation(self, other):
            return None

    mock_get_langs = MagicMock(return_value=[MockLang("ja"), MockLang("en")])
    monkeypatch.setattr(
        "argostranslate.translate.get_installed_languages", mock_get_langs
    )

    status = ArgosSetupService.check_status("ja", "en")
    assert status["status"] == ModelStatus.NOT_INSTALLED
    assert "not available" in status["message"]


def test_check_status_dependency_missing(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "argostranslate.translate", None)

    status = ArgosSetupService.check_status("ja", "en")
    assert status["status"] == ModelStatus.DEPENDENCY_MISSING


def test_install_from_file_valid(tmp_path, monkeypatch):
    # Create a dummy valid zip
    zip_path = tmp_path / "valid.argosmodel"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("metadata.json", "{}")

    mock_install = MagicMock()
    monkeypatch.setattr("argostranslate.package.install_from_path", mock_install)

    with patch(
        "gamelingo.translation.argos_setup.ArgosSetupService.check_status",
        return_value={"status": ModelStatus.READY, "message": "OK"},
    ):
        ArgosSetupService.install_from_file("ja", "en", str(zip_path))

    mock_install.assert_called_once_with(str(zip_path))


def test_install_from_file_invalid_zip(tmp_path):
    invalid_path = tmp_path / "invalid.argosmodel"
    invalid_path.write_text("not a zip")

    with pytest.raises(ValueError, match="not a valid zip"):
        ArgosSetupService.install_from_file("ja", "en", str(invalid_path))


def test_install_from_file_missing_metadata(tmp_path):
    zip_path = tmp_path / "no_meta.argosmodel"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("dummy.txt", "data")

    with pytest.raises(ValueError, match="metadata.json missing"):
        ArgosSetupService.install_from_file("ja", "en", str(zip_path))


def test_install_from_network_success(monkeypatch):
    class MockPkg:
        from_code = "ja"
        to_code = "en"
        links = ["http://example.com/model.zip"]
        package_version = "1.0"

    monkeypatch.setattr("argostranslate.package.update_package_index", MagicMock())
    monkeypatch.setattr(
        "argostranslate.package.get_available_packages",
        MagicMock(return_value=[MockPkg()]),
    )

    mock_urlopen = MagicMock()
    mock_response = MagicMock()
    mock_response.info.return_value = {"Content-Length": "100"}
    mock_response.read.side_effect = [b"dummy data", b""]
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    mock_install = MagicMock()
    monkeypatch.setattr("argostranslate.package.install_from_path", mock_install)

    with patch(
        "gamelingo.translation.argos_setup.ArgosSetupService.check_status",
        return_value={"status": ModelStatus.READY, "message": "OK"},
    ):
        ArgosSetupService.install_from_network("ja", "en")

    mock_install.assert_called_once()
    mock_urlopen.assert_called_once()
    req = mock_urlopen.call_args[0][0]
    assert req.headers["User-agent"] == "GameLingo/1.0"


def test_install_from_network_http_error(monkeypatch):
    class MockPkg:
        from_code = "ja"
        to_code = "en"
        links = ["http://example.com/model.zip"]
        package_version = "1.0"

    monkeypatch.setattr("argostranslate.package.update_package_index", MagicMock())
    monkeypatch.setattr(
        "argostranslate.package.get_available_packages",
        MagicMock(return_value=[MockPkg()]),
    )

    def fail_open(*args, **kwargs):
        raise urllib.error.URLError("Failed to resolve")

    monkeypatch.setattr(urllib.request, "urlopen", fail_open)

    with pytest.raises(urllib.error.URLError):
        ArgosSetupService.install_from_network("ja", "en")
