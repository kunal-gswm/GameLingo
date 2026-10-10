from dataclasses import dataclass


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
