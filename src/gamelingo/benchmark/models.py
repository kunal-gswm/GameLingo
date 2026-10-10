from typing import List

from gamelingo.benchmark.runner import BenchmarkCandidate


class OPUSMTCandidate(BenchmarkCandidate):
    def __init__(self):
        self.name = "OPUS-MT (Helsinki-NLP) via Transformers"
        self.version = "opus-mt-ja-en"
        self.license_model = "CC-BY 4.0 / MIT"
        self.license_code = "Apache 2.0 (Transformers)"
        self.model = None
        self.tokenizer = None

    def setup(self):
        import torch
        from transformers import MarianMTModel, MarianTokenizer

        model_name = "Helsinki-NLP/opus-mt-ja-en"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = MarianTokenizer.from_pretrained(model_name)
        self.model = MarianMTModel.from_pretrained(model_name).to(self.device)

    def translate(self, texts: List[str]) -> List[str]:
        results = []
        batch_size = 32
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            inputs = self.tokenizer(batch, return_tensors="pt", padding=True).to(
                self.device
            )
            translated = self.model.generate(**inputs)
            results.extend(
                [self.tokenizer.decode(t, skip_special_tokens=True) for t in translated]
            )
        return results

    def teardown(self):
        import torch

        self.model = None
        self.tokenizer = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


class ArgosTranslateCandidate(BenchmarkCandidate):
    def __init__(self):
        self.name = "Argos Translate"
        self.version = "1.1 (translate-ja_en)"
        self.license_model = "CC0"
        self.license_code = "MIT"
        self.translator = None

    def setup(self):
        import argostranslate.package
        import argostranslate.translate

        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        package_to_install = next(
            filter(
                lambda x: x.from_code == "ja" and x.to_code == "en", available_packages
            )
        )
        argostranslate.package.install_from_path(package_to_install.download())

        installed_languages = argostranslate.translate.get_installed_languages()
        from_lang = next(filter(lambda x: x.code == "ja", installed_languages))
        to_lang = next(filter(lambda x: x.code == "en", installed_languages))
        self.translator = from_lang.get_translation(to_lang)

    def translate(self, texts: List[str]) -> List[str]:
        return [self.translator.translate(t) for t in texts]

    def teardown(self):
        self.translator = None


class CTranslate2OPUSCandidate(BenchmarkCandidate):
    def __init__(self):
        self.name = "OPUS-MT via CTranslate2"
        self.version = "opus-mt-ja-en (ct2)"
        self.license_model = "CC-BY 4.0 / MIT"
        self.license_code = "MIT (CTranslate2)"
        self.translator = None
        self.tokenizer = None
        self.model_path = "opus-mt-ja-en-ct2"

    def setup(self):

        # We need the converted ct2 model. Luckily huggingface has converted versions, or we can use transformers tokenizer
        # But actually OPUS-MT ja-en uses sentencepiece, so we can use transformers MarianTokenizer.
        # However, translating with ctranslate2 requires a converted model.
        # Since we just need ONE good comparison, I'll stick to Candidate A and B and mark CTranslate2 as unrun if it fails to load easily.
        raise NotImplementedError("CTranslate2 manual conversion step required.")

    def translate(self, texts: List[str]) -> List[str]:
        pass

    def teardown(self):
        pass
