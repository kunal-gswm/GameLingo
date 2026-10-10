import sys

import pytest

from gamelingo.translation.argos_provider import ArgosTranslateProvider
from gamelingo.translation.provider import TranslationRequest


def test_missing_argos_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "argostranslate.translate", None)
    monkeypatch.setitem(sys.modules, "argostranslate", None)

    with pytest.raises(ImportError, match="argostranslate is not installed"):
        ArgosTranslateProvider()


def test_argos_provider_empty_string(monkeypatch):
    import sys

    class FakeLanguage:
        code = "en"

        def get_translation(self, other):
            return FakeTranslator()

    class FakeTranslator:
        def translate(self, text):
            return text + " TR"

    class FakeTranslate:
        def get_installed_languages(self):
            class Lang:
                def __init__(self, c):
                    self.code = c

                def get_translation(self, o):
                    return FakeTranslator()

            return [Lang("ja"), Lang("en")]

    class FakeArgosTranslate:
        translate = FakeTranslate()

    monkeypatch.setitem(sys.modules, "argostranslate", FakeArgosTranslate())
    monkeypatch.setitem(sys.modules, "argostranslate.translate", FakeTranslate())

    provider = ArgosTranslateProvider()

    # Test empty
    req1 = TranslationRequest(
        id="1", source_text="   ", source_lang="ja", target_lang="en"
    )
    res = provider.translate_batch([req1])
    assert res[0].target_text == "   "
    assert res[0].error is None


def test_argos_provider_translation_and_placeholders(monkeypatch):
    import sys

    class FakeTranslator:
        def translate(self, text):
            # simulate a normal translation that passes the placeholder through
            return text.replace("Hello", "Bonjour") + " TR"

    class FakeTranslate:
        def get_installed_languages(self):
            class Lang:
                def __init__(self, c):
                    self.code = c

                def get_translation(self, o):
                    return FakeTranslator()

            return [Lang("ja"), Lang("en")]

    class FakeArgosTranslate:
        translate = FakeTranslate()

    monkeypatch.setitem(sys.modules, "argostranslate", FakeArgosTranslate())
    monkeypatch.setitem(sys.modules, "argostranslate.translate", FakeTranslate())

    provider = ArgosTranslateProvider()

    req = TranslationRequest(
        id="2", source_text="Hello %1", source_lang="ja", target_lang="en"
    )
    res = provider.translate_batch([req])

    assert res[0].error is None
    assert "Bonjour" in res[0].target_text
    assert "%1" in res[0].target_text


def test_argos_provider_masking_error(monkeypatch):
    import sys

    class FakeTranslatorEatPlaceholder:
        def translate(self, text):
            # Eat the placeholder!
            return "A translation without tokens"

    class FakeTranslate:
        def get_installed_languages(self):
            class Lang:
                def __init__(self, c):
                    self.code = c

                def get_translation(self, o):
                    return FakeTranslatorEatPlaceholder()

            return [Lang("ja"), Lang("en")]

    class FakeArgosTranslate:
        translate = FakeTranslate()

    monkeypatch.setitem(sys.modules, "argostranslate", FakeArgosTranslate())
    monkeypatch.setitem(sys.modules, "argostranslate.translate", FakeTranslate())

    provider = ArgosTranslateProvider()

    req = TranslationRequest(
        id="3", source_text="Hello %1", source_lang="ja", target_lang="en"
    )
    res = provider.translate_batch([req])

    assert res[0].error is not None
    assert "Placeholder error" in res[0].error
    assert res[0].target_text == ""
