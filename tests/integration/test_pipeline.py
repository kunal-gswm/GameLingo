import pytest
from gamelingo.storage.database import Database
from gamelingo.domain.models import TranslationUnit
from gamelingo.translation.provider import FakeProvider, TranslationRequest
from gamelingo.translation.pipeline import TranslationPipeline
import tempfile
from pathlib import Path
import sqlite3

@pytest.fixture
def db(tmp_path: Path):
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    database.migrate()
    # create project so foreign keys work
    conn = database.connect()
    with conn:
        conn.execute("INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES ('proj1', 'T', 'P', 'A', '1', 0)")
        conn.execute("INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES ('file1', 'proj1', 'f.json', 'json', 'hash', 0, 0)")
    return database

def test_pipeline_basic(db):
    provider = FakeProvider(batch_limit=2)
    pipeline = TranslationPipeline(db, provider)
    
    units = [
        TranslationUnit("u1", "file1", "loc1", "Hello", "ctx1", "[]", "h1"),
        TranslationUnit("u2", "file1", "loc2", "World", "ctx1", "[]", "h2"),
        TranslationUnit("u3", "file1", "loc3", "Hello", "ctx2", "[]", "h3") # different context
    ]
    
    conn = db.connect()
    with conn:
        for u in units:
            conn.execute("INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash) VALUES (?, ?, ?, ?, ?, ?, ?)", (u.id, u.file_id, u.locator, u.source_text, u.context, u.tokens_json, u.source_hash))
            
    job_id = pipeline.create_job("proj1", units, "en", "es")
    report = pipeline.resume_job(job_id)
    
    assert report["status"] == "completed"
    assert provider.calls == 2 # 3 unique requests, chunk size 2 -> 2 calls
    
    cur = conn.execute("SELECT * FROM translation_records")
    records = cur.fetchall()
    assert len(records) == 3
    for r in records:
        assert r["final_text"] in ["Hello TR", "World TR"]
        
    cur = conn.execute("SELECT * FROM translation_memory")
    mem = cur.fetchall()
    assert len(mem) == 3 # Hello-ctx1, World-ctx1, Hello-ctx2
    
def test_pipeline_deduplication(db):
    provider = FakeProvider(batch_limit=2)
    pipeline = TranslationPipeline(db, provider)
    
    units = [
        TranslationUnit("u1", "file1", "loc1", "Hello", "ctx1", "[]", "h1"),
        TranslationUnit("u2", "file1", "loc2", "Hello", "ctx1", "[]", "h2")
    ]
    
    conn = db.connect()
    with conn:
        for u in units:
            conn.execute("INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash) VALUES (?, ?, ?, ?, ?, ?, ?)", (u.id, u.file_id, u.locator, u.source_text, u.context, u.tokens_json, u.source_hash))
            
    job_id = pipeline.create_job("proj1", units, "en", "es")
    pipeline.resume_job(job_id)
    
    assert provider.calls == 1 # 1 unique request
    
    cur = conn.execute("SELECT * FROM translation_records")
    records = cur.fetchall()
    assert len(records) == 2 # Both units get records

def test_pipeline_persistent_cache(db):
    provider = FakeProvider(batch_limit=2)
    pipeline = TranslationPipeline(db, provider)
    
    units = [TranslationUnit("u1", "file1", "loc1", "Hello", "ctx1", "[]", "h1")]
    
    conn = db.connect()
    with conn:
        conn.execute("INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash) VALUES (?, ?, ?, ?, ?, ?, ?)", (units[0].id, units[0].file_id, units[0].locator, units[0].source_text, units[0].context, units[0].tokens_json, units[0].source_hash))
            
    job_id = pipeline.create_job("proj1", units, "en", "es")
    pipeline.resume_job(job_id)
    assert provider.calls == 1
    
    # Second job with same text/context
    units2 = [TranslationUnit("u2", "file1", "loc2", "Hello", "ctx1", "[]", "h2")]
    with conn:
        conn.execute("INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash) VALUES (?, ?, ?, ?, ?, ?, ?)", (units2[0].id, units2[0].file_id, units2[0].locator, units2[0].source_text, units2[0].context, units2[0].tokens_json, units2[0].source_hash))
        
    job_id2 = pipeline.create_job("proj1", units2, "en", "es")
    # Resume not needed because cache hits during create_job
    assert provider.calls == 1 # Still 1!
    
    cur = conn.execute("SELECT final_text FROM translation_records WHERE unit_id = 'u2'")
    assert cur.fetchone()["final_text"] == "Hello TR"
    
def test_pipeline_resume_and_retry(db):
    provider = FakeProvider(simulate_error_for=["FailOnce"], batch_limit=2)
    pipeline = TranslationPipeline(db, provider)
    
    units = [TranslationUnit("u1", "file1", "loc1", "FailOnce", "ctx1", "[]", "h1")]
    conn = db.connect()
    with conn:
        conn.execute("INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash) VALUES (?, ?, ?, ?, ?, ?, ?)", (units[0].id, units[0].file_id, units[0].locator, units[0].source_text, units[0].context, units[0].tokens_json, units[0].source_hash))
        
    job_id = pipeline.create_job("proj1", units, "en", "es")
    report = pipeline.resume_job(job_id)
    
    assert report["status"] == "running" # One chunk failed, it stopped executing next chunks (though there is only 1 chunk here)
    
    # Remove error simulation
    provider.simulate_error_for = []
    
    report2 = pipeline.resume_job(job_id)
    assert report2["status"] == "completed"
