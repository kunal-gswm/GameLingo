from typing import List

from gamelingo.translation.placeholders import MaskingError, PlaceholderProtector
from gamelingo.translation.provider import (
    TranslationProvider,
    TranslationRequest,
    TranslationResult,
)


class ArgosTranslateProvider(TranslationProvider):
    def __init__(self, batch_limit: int = 100):
        self._batch_limit = batch_limit
        self._translator_map = {}

        try:
            import argostranslate  # noqa: F401
        except ImportError:
            raise ImportError(
                "argostranslate is not installed. Please install it using `uv sync --group argos` or `pip install argostranslate`."
            )

    @classmethod
    def is_model_installed(cls, source_lang: str, target_lang: str) -> bool:
        try:
            import argostranslate.translate

            installed_languages = argostranslate.translate.get_installed_languages()

            from_lang = next(
                (lang for lang in installed_languages if lang.code == source_lang), None
            )
            to_lang = next(
                (lang for lang in installed_languages if lang.code == target_lang), None
            )

            if not from_lang or not to_lang:
                return False

            translator = from_lang.get_translation(to_lang)
            return translator is not None
        except Exception:
            return False

    @classmethod
    def install_model(cls, source_lang: str, target_lang: str, progress_callback=None):
        import shutil

        import argostranslate.package

        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        package = next(
            filter(
                lambda x: x.from_code == source_lang and x.to_code == target_lang,
                available_packages,
            ),
            None,
        )
        if not package:
            raise ValueError(
                f"Language package {source_lang}->{target_lang} not found in Argos index."
            )

        import tempfile
        import urllib.request
        from pathlib import Path

        url = package.links[0]

        with urllib.request.urlopen(url) as response:
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

        if not cls.is_model_installed(source_lang, target_lang):
            raise RuntimeError(
                "Installation completed but model is not marked as installed."
            )

    @property
    def batch_limit(self) -> int:
        return self._batch_limit

    def _get_translator(self, source_lang: str, target_lang: str):
        key = (source_lang, target_lang)
        if key in self._translator_map:
            return self._translator_map[key]

        import argostranslate.translate

        installed_languages = argostranslate.translate.get_installed_languages()

        from_lang = None
        for lang in installed_languages:
            if lang.code == source_lang:
                from_lang = lang
                break

        to_lang = None
        for lang in installed_languages:
            if lang.code == target_lang:
                to_lang = lang
                break

        if not from_lang or not to_lang:
            raise ValueError(
                f"Language package {source_lang}->{target_lang} is not installed locally. "
                "Use the Argos package index to download and install it."
            )

        translator = from_lang.get_translation(to_lang)
        if not translator:
            raise ValueError(
                f"Translation route from {source_lang} to {target_lang} is not available."
            )

        self._translator_map[key] = translator
        return translator

    def translate_batch(
        self, requests: List[TranslationRequest]
    ) -> List[TranslationResult]:

        if len(requests) > self.batch_limit:
            raise ValueError(
                f"Batch size {len(requests)} exceeds limit {self.batch_limit}"
            )

        results = []
        for req in requests:
            # Handle empty
            if not req.source_text.strip():
                results.append(
                    TranslationResult(req.id, req.source_text, "argos", "1.1")
                )
                continue

            try:
                translator = self._get_translator(req.source_lang, req.target_lang)

                # Protect placeholders
                protector = PlaceholderProtector()
                masked_text = protector.mask(req.source_text)

                # Translate
                translated_masked = translator.translate(masked_text)

                # Restore
                final_text = protector.restore(translated_masked)

                results.append(TranslationResult(req.id, final_text, "argos", "1.1"))

            except MaskingError as e:
                results.append(
                    TranslationResult(
                        req.id, "", "argos", "1.1", error=f"Placeholder error: {str(e)}"
                    )
                )
            except Exception as e:
                results.append(
                    TranslationResult(req.id, "", "argos", "1.1", error=str(e))
                )

        return results
