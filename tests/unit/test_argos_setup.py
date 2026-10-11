import sys
import types
import urllib.error
import urllib.request
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from gamelingo.translation.argos_setup import ArgosSetupService, ModelStatus


@pytest.fixture
def mock_argos_modules(monkeypatch):
    fake_argos = types.ModuleType("argostranslate")
    fake_translate = types.ModuleType("argostranslate.translate")
    fake_package = types.ModuleType("argostranslate.package")
    fake_argos.translate = fake_translate
    fake_argos.package = fake_package

    mock_install_from_path = MagicMock()
    mock_update_package_index = MagicMock()
    mock_get_available_packages = MagicMock(return_value=[])
    mock_get_installed_languages = MagicMock(return_value=[])

    fake_translate.get_installed_languages = mock_get_installed_languages
    fake_package.install_from_path = mock_install_from_path
    fake_package.update_package_index = mock_update_package_index
    fake_package.get_available_packages = mock_get_available_packages

    monkeypatch.setitem(sys.modules, "argostranslate", fake_argos)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", fake_translate)
    monkeypatch.setitem(sys.modules, "argostranslate.package", fake_package)

    return {
        "argos": fake_argos,
        "translate": fake_translate,
        "package": fake_package,
        "get_installed_languages": mock_get_installed_languages,
        "install_from_path": mock_install_from_path,
        "update_package_index": mock_update_package_index,
        "get_available_packages": mock_get_available_packages,
    }


def test_check_status_installed(mock_argos_modules):
    class MockLang:
        def __init__(self, code):
            self.code = code

        def get_translation(self, other):
            return "mock_translator"

    mock_argos_modules["get_installed_languages"].return_value = [
        MockLang("ja"),
        MockLang("en"),
    ]

    status = ArgosSetupService.check_status("ja", "en")
    assert status["status"] == ModelStatus.READY
    assert "Model is installed" in status["message"]
    mock_argos_modules["get_installed_languages"].assert_called_once()


def test_check_status_not_installed(mock_argos_modules):
    mock_argos_modules["get_installed_languages"].return_value = []

    status = ArgosSetupService.check_status("ja", "en")
    assert status["status"] == ModelStatus.NOT_INSTALLED
    assert "not installed" in status["message"]


def test_check_status_no_route(mock_argos_modules):
    class MockLang:
        def __init__(self, code):
            self.code = code

        def get_translation(self, other):
            return None

    mock_argos_modules["get_installed_languages"].return_value = [
        MockLang("ja"),
        MockLang("en"),
    ]

    status = ArgosSetupService.check_status("ja", "en")
    assert status["status"] == ModelStatus.NOT_INSTALLED
    assert "not available" in status["message"]


def test_check_status_dependency_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "argostranslate", None)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", None)

    status = ArgosSetupService.check_status("ja", "en")
    assert status["status"] == ModelStatus.DEPENDENCY_MISSING


def test_install_from_file_valid(tmp_path, mock_argos_modules):
    zip_path = tmp_path / "valid.argosmodel"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("metadata.json", "{}")

    with patch(
        "gamelingo.translation.argos_setup.ArgosSetupService.check_status",
        return_value={"status": ModelStatus.READY, "message": "OK"},
    ):
        ArgosSetupService.install_from_file("ja", "en", str(zip_path))

    mock_argos_modules["install_from_path"].assert_called_once_with(str(zip_path))


def test_install_from_file_invalid_zip(tmp_path, mock_argos_modules):
    invalid_path = tmp_path / "invalid.argosmodel"
    invalid_path.write_text("not a zip")

    with pytest.raises(ValueError, match="not a valid zip"):
        ArgosSetupService.install_from_file("ja", "en", str(invalid_path))


def test_install_from_file_missing_metadata(tmp_path, mock_argos_modules):
    zip_path = tmp_path / "no_meta.argosmodel"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("dummy.txt", "data")

    with pytest.raises(ValueError, match="metadata.json missing"):
        ArgosSetupService.install_from_file("ja", "en", str(zip_path))


def test_install_from_network_success(mock_argos_modules, monkeypatch):
    class MockPkg:
        from_code = "ja"
        to_code = "en"
        links = ["http://example.com/model.zip"]
        package_version = "1.0"

    mock_argos_modules["get_available_packages"].return_value = [MockPkg()]

    mock_urlopen = MagicMock()
    mock_response = MagicMock()
    mock_response.info.return_value = {"Content-Length": "100"}
    mock_response.read.side_effect = [b"dummy data", b""]
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    with patch(
        "gamelingo.translation.argos_setup.ArgosSetupService.check_status",
        return_value={"status": ModelStatus.READY, "message": "OK"},
    ):
        ArgosSetupService.install_from_network("ja", "en")

    mock_argos_modules["install_from_path"].assert_called_once()
    mock_urlopen.assert_called_once()
    req = mock_urlopen.call_args[0][0]
    assert req.headers["User-agent"] == "GameLingo/1.0"


def test_install_from_network_http_error(mock_argos_modules, monkeypatch):
    class MockPkg:
        from_code = "ja"
        to_code = "en"
        links = ["http://example.com/model.zip"]
        package_version = "1.0"

    mock_argos_modules["get_available_packages"].return_value = [MockPkg()]

    def fail_open(*args, **kwargs):
        raise urllib.error.URLError("Failed to resolve")

    monkeypatch.setattr(urllib.request, "urlopen", fail_open)

    with pytest.raises(urllib.error.URLError):
        ArgosSetupService.install_from_network("ja", "en")
