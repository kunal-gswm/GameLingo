from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TranslationRequest:
    id: str
    source_text: str
    source_lang: str
    target_lang: str
    context: str = ""
    category: str = ""
    glossary: Dict[str, str] = field(default_factory=dict)


@dataclass
class TranslationResult:
    request_id: str
    target_text: str
    provider: str
    model: str
    error: Optional[str] = None


class TranslationProvider(ABC):
    @property
    @abstractmethod
    def batch_limit(self) -> int:
        pass

    @abstractmethod
    def translate_batch(
        self, requests: List[TranslationRequest]
    ) -> List[TranslationResult]:
        pass


class FakeProvider(TranslationProvider):
    def __init__(self, simulate_error_for: List[str] = None, batch_limit: int = 100):
        self.simulate_error_for = simulate_error_for or []
        self._batch_limit = batch_limit
        self.calls = 0

    @property
    def batch_limit(self) -> int:
        return self._batch_limit

    def translate_batch(
        self, requests: List[TranslationRequest]
    ) -> List[TranslationResult]:
        if len(requests) > self.batch_limit:
            raise ValueError(
                f"Batch size {len(requests)} exceeds limit {self.batch_limit}"
            )

        self.calls += 1
        results = []
        for req in requests:
            if req.source_text in self.simulate_error_for:
                results.append(
                    TranslationResult(
                        req.id, "", "fake", "fake-v1", error="Simulated error"
                    )
                )
            else:
                results.append(
                    TranslationResult(
                        req.id, req.source_text + " TR", "fake", "fake-v1"
                    )
                )
        return results
