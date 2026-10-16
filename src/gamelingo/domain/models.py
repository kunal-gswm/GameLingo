import time
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class GameFile:
    id: str
    project_id: str
    relative_path: str
    format: str
    source_hash: str
    size: int
    detected_at: float


@dataclass
class TranslationUnit:
    id: str
    file_id: str
    locator: str  # JSON path or similar unique locator within the file
    source_text: str
    context: str
    tokens_json: str
    source_hash: str
    status: str = "untranslated"


@dataclass
class TranslationRecord:
    id: str
    unit_id: str
    provider: str = ""
    model: str = ""
    draft_text: str = ""
    final_text: str = ""
    quality_flags: str = "[]"
    created_at: float = 0.0
    updated_at: float = 0.0
    source_hash: Optional[str] = None

    def __post_init__(self):
        if not self.id or not str(self.id).strip():
            raise ValueError("TranslationRecord id cannot be empty.")
        if not self.unit_id or not str(self.unit_id).strip():
            raise ValueError("TranslationRecord unit_id cannot be empty.")
        now = time.time()
        if self.created_at == 0.0:
            self.created_at = now
        if self.updated_at == 0.0:
            self.updated_at = self.created_at

    def validate_for_approval(self) -> List[str]:
        """Validates that this record has valid, non-empty translation content suitable for approval."""
        errors = []
        effective_text = (self.final_text or self.draft_text or "").strip()
        if not effective_text:
            errors.append("Approved translation text cannot be empty.")
        return errors
