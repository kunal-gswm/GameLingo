import re
from typing import List

from gamelingo.translation.placeholders import MaskingError, PlaceholderProtector
from gamelingo.translation.provider import (
    TranslationProvider,
    TranslationRequest,
    TranslationResult,
)

_JP_CHAR_REGEX = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]")


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
        from gamelingo.translation.argos_setup import ArgosSetupService, ModelStatus

        status = ArgosSetupService.check_status(source_lang, target_lang)
        return status["status"] == ModelStatus.READY

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

                # Normalize Japanese lenticular brackets 【...】 to quotes to prevent
                # NMT from producing unescaped Ren'Py variable interpolation brackets [...]
                text_to_translate = (
                    req.source_text.replace("\u3010", '"').replace("\u3011", '"')
                    if req.source_lang == "ja"
                    else req.source_text
                )

                # Multi-stage sentinel protection:
                # 1. Try canonical 'default' (XXXTOKEN0XXX) for max compatibility.
                # 2. On NMT token splitting/mangling, fallback to 'bracket' ([T0]).
                # 3. If needed, fallback to 'brace' ({T0}).
                final_text = None
                last_mask_err = None
                for style in ("default", "bracket", "brace"):
                    try:
                        protector = PlaceholderProtector(sentinel_style=style)
                        masked_text = protector.mask(text_to_translate)
                        translated_masked = translator.translate(masked_text)
                        final_text = protector.restore(translated_masked)
                        last_mask_err = None
                        break
                    except MaskingError as me:
                        last_mask_err = me

                if last_mask_err is not None:
                    raise last_mask_err

                # Fallback to source text if translation is empty or whitespace
                if not final_text or not final_text.strip():
                    final_text = req.source_text

                results.append(TranslationResult(req.id, final_text, "argos", "1.1"))

            except MaskingError as e:
                results.append(
                    TranslationResult(
                        req.id,
                        "",
                        "argos",
                        "1.1",
                        error=f"Placeholder error: {str(e)}",
                    )
                )
            except Exception as e:
                results.append(
                    TranslationResult(req.id, "", "argos", "1.1", error=str(e))
                )

        return results
