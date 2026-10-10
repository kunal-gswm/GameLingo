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
