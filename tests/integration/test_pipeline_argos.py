import sys
from pathlib import Path

import pytest

from gamelingo.domain.models import TranslationUnit
from gamelingo.storage.database import Database
from gamelingo.translation.argos_provider import ArgosTranslateProvider
from gamelingo.translation.pipeline import TranslationPipeline


@pytest.fixture
def db(tmp_path: Path):
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    database.migrate()
    conn = database.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES ('proj1', 'T', 'P', 'A', '1', 0)"
        )
        conn.execute(
            "INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES ('f1', 'proj1', 'f.json', 'json', 'hash', 0, 0)"
        )
    return database


def test_pipeline_with_argos_provider(monkeypatch, db):
    class FakeTranslator:
        def translate(self, text):
            # Translate while keeping mask if any
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

    provider = ArgosTranslateProvider(batch_limit=2)
    pipeline = TranslationPipeline(db, provider)

    units = [
        TranslationUnit(
            id="1",
            file_id="f1",
            locator="l1",
            source_text="Hello",
            context="ctx1",
            tokens_json="[]",
            source_hash="h1",
        ),
        TranslationUnit(
            id="2",
            file_id="f1",
            locator="l2",
            source_text="Hello",
            context="ctx1",
            tokens_json="[]",
            source_hash="h1",
        ),  # Duplicate
        TranslationUnit(
            id="3",
            file_id="f1",
            locator="l3",
            source_text="World %1",
            context="ctx2",
            tokens_json="[]",
            source_hash="h2",
        ),
    ]

    # Insert source units
    conn = db.connect()
    with conn:
        for u in units:
            conn.execute(
                "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    u.id,
                    u.file_id,
                    u.locator,
                    u.source_text,
                    u.context,
                    u.tokens_json,
                    u.source_hash,
                ),
            )

    job_id = pipeline.create_job("proj1", units, "ja", "en")

    # Run the pipeline
    status = pipeline.resume_job(job_id)

    assert status["status"] == "completed"

    # Verify results in DB
    records = conn.execute(
        "SELECT unit_id, final_text FROM translation_records"
    ).fetchall()

    records_dict = {r["unit_id"]: r["final_text"] for r in records}
    assert records_dict["1"] == "Hello TR"
    assert records_dict["2"] == "Hello TR"
    assert records_dict["3"] == "World %1 TR"

    # Assert cache hit on second run
    job_id2 = pipeline.create_job("proj1", units, "ja", "en")
    status2 = pipeline.resume_job(job_id2)
    # The job is complete instantly since all are cached
    assert status2["status"] == "completed"
