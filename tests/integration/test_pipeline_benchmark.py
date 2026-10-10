import pytest
import time
from gamelingo.storage.database import Database
from gamelingo.domain.models import TranslationUnit
from gamelingo.translation.provider import FakeProvider
from gamelingo.translation.pipeline import TranslationPipeline
from pathlib import Path

def test_pipeline_benchmark(tmp_path: Path):
    db_path = tmp_path / "bench.db"
    database = Database(db_path)
    database.migrate()
    conn = database.connect()
    with conn:
        conn.execute("INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES ('p1', 'T', 'P', 'A', '1', 0)")
        conn.execute("INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES ('f1', 'p1', 'f.json', 'json', 'hash', 0, 0)")
        
    provider = FakeProvider(batch_limit=50)
    pipeline = TranslationPipeline(database, provider)
    
    # Generate 1000 units. 500 unique strings, each duplicated once.
    units = []
    for i in range(500):
        units.append(TranslationUnit(f"u{i}_a", "f1", f"l{i}_a", f"Text {i}", "ctx1", "[]", f"h{i}_a"))
        units.append(TranslationUnit(f"u{i}_b", "f1", f"l{i}_b", f"Text {i}", "ctx1", "[]", f"h{i}_b"))
        
    with conn:
        for u in units:
            conn.execute("INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash) VALUES (?, ?, ?, ?, ?, ?, ?)", (u.id, u.file_id, u.locator, u.source_text, u.context, u.tokens_json, u.source_hash))
            
    # Baseline with deduplication
    start_time = time.time()
    job1_id = pipeline.create_job("p1", units, "en", "es")
    pipeline.resume_job(job1_id)
    job1_time = time.time() - start_time
    
    print(f"\nJob 1 (Deduplication): 1000 units -> {provider.calls} provider calls. Time: {job1_time:.2f}s")
    assert provider.calls == 10 # 500 unique / 50 batch size = 10 batches
    
    # Second job with persistent cache reuse
    # We will pass the exact same units again to simulate a new extraction or similar run
    # Wait, we need new unit IDs to insert them into DB, or just use the same unit IDs?
    # Actually, we can just create a new project or just new units
    units2 = []
    for i in range(500):
        units2.append(TranslationUnit(f"u2_{i}", "f1", f"l2_{i}", f"Text {i}", "ctx1", "[]", f"h2_{i}"))
        
    with conn:
        for u in units2:
            conn.execute("INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash) VALUES (?, ?, ?, ?, ?, ?, ?)", (u.id, u.file_id, u.locator, u.source_text, u.context, u.tokens_json, u.source_hash))
            
    provider.calls = 0 # reset calls
    start_time = time.time()
    job2_id = pipeline.create_job("p1", units2, "en", "es")
    pipeline.resume_job(job2_id)
    job2_time = time.time() - start_time
    
    print(f"Job 2 (Persistent Cache): 500 units -> {provider.calls} provider calls. Time: {job2_time:.2f}s")
    assert provider.calls == 0 # 100% cache hit
