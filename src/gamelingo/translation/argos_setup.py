import shutil
import tempfile
import urllib.request
from enum import Enum, auto
from pathlib import Path


class ModelStatus(Enum):
    DEPENDENCY_MISSING = auto()
    NOT_INSTALLED = auto()
    READY = auto()
    ERROR = auto()


class ArgosSetupService:
    @classmethod
    def check_status(cls, source_lang: str, target_lang: str) -> dict:
        """
        Checks if a model is installed without hitting the network.
        Returns a structured dictionary with 'status' and 'message'.
        """
        try:
            import argostranslate.translate
        except ImportError:
            return {
                "status": ModelStatus.DEPENDENCY_MISSING,
                "message": "Argos Translate library is not installed.",
            }

        try:
            installed = argostranslate.translate.get_installed_languages()
            from_lang = next(
                (lang for lang in installed if lang.code == source_lang), None
            )
            to_lang = next(
                (lang for lang in installed if lang.code == target_lang), None
            )

            if not from_lang or not to_lang:
                return {
                    "status": ModelStatus.NOT_INSTALLED,
                    "message": f"Language package {source_lang}->{target_lang} is not installed.",
                }

            translator = from_lang.get_translation(to_lang)
            if not translator:
                return {
                    "status": ModelStatus.NOT_INSTALLED,
                    "message": f"Translation route {source_lang}->{target_lang} not available.",
                }

            return {
                "status": ModelStatus.READY,
                "message": "Model is installed and ready.",
            }
        except Exception as e:
            return {
                "status": ModelStatus.ERROR,
                "message": f"Environmental error checking model: {str(e)}",
            }

    @classmethod
    def get_online_metadata(cls, source_lang: str, target_lang: str) -> dict:
        import argostranslate.package

        argostranslate.package.update_package_index()
        available = argostranslate.package.get_available_packages()
        pkg = next(
            (
                x
                for x in available
                if x.from_code == source_lang and x.to_code == target_lang
            ),
            None,
        )
        if not pkg:
            raise ValueError(
                f"No online package found for {source_lang}->{target_lang} in Argos index."
            )

        url = pkg.links[0] if pkg.links else None
        if not url:
            raise ValueError(
                f"Online package for {source_lang}->{target_lang} has no valid download links."
            )

        return {
            "version": pkg.package_version,
            "url": url,
            "provider": "Argos Open Tech",
            "license": "Usually CC0 or MIT (varies by model)",
        }

    @classmethod
    def install_from_network(
        cls, source_lang: str, target_lang: str, progress_callback=None
    ):
        meta = cls.get_online_metadata(source_lang, target_lang)
        url = meta["url"]

        import argostranslate.package

        req = urllib.request.Request(url, headers={"User-Agent": "GameLingo/1.0"})
        with urllib.request.urlopen(req) as response:
            total_size = int(response.info().get("Content-Length", 0))
            if total_size > 0:
                _, _, free = shutil.disk_usage("/")
                if free < total_size * 2:
                    raise IOError("Not enough disk space to install the model.")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".argosmodel") as tmp:
                downloaded = 0
                block_size = 8192
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    tmp.write(buffer)
                    if progress_callback and total_size > 0:
                        progress_callback(int(downloaded * 100 / total_size))
                tmp_path = tmp.name

        try:
            argostranslate.package.install_from_path(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        status = cls.check_status(source_lang, target_lang)
        if status["status"] != ModelStatus.READY:
            raise RuntimeError(
                f"Installation completed but model is not ready: {status['message']}"
            )

    @classmethod
    def install_from_file(cls, source_lang: str, target_lang: str, file_path: str):
        from zipfile import BadZipFile, ZipFile

        import argostranslate.package

        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Package file not found: {file_path}")

        try:
            with ZipFile(file_path, "r") as z:
                # Basic validation
                if not any("metadata.json" in name for name in z.namelist()):
                    raise ValueError(
                        "Not a valid Argos model package (metadata.json missing)."
                    )
        except BadZipFile:
            raise ValueError(
                "The provided file is not a valid zip archive (.argosmodel)."
            )

        argostranslate.package.install_from_path(str(path_obj))

        status = cls.check_status(source_lang, target_lang)
        if status["status"] != ModelStatus.READY:
            raise RuntimeError(
                f"Installation completed but model is not ready for {source_lang}->{target_lang}: {status['message']}"
            )
