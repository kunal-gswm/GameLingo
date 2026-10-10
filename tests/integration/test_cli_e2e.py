import json
import sys
from unittest.mock import patch

import pytest

from gamelingo.app import main


@pytest.fixture
def e2e_setup(tmp_path):
    ws = tmp_path / "workspace"
    game = tmp_path / "game"
    game.mkdir()
    (game / "data").mkdir()

    # Create fake game data
    data = {
        "events": [
            None,
            {"pages": [{"list": [{"code": 401, "parameters": ["Hello, World!"]}]}]},
        ]
    }
    with open(game / "data" / "Map001.json", "w", encoding="utf-8") as f:
        json.dump(data, f)

    with open(game / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "Test", "versionId": 1}, f)

    return ws, game


def run_cli(*args):
    with patch.object(sys, "argv", ["gamelingo", *args]):
        try:
            return main()
        except SystemExit as e:
            return e.code


def test_cli_e2e(e2e_setup, monkeypatch):
    ws, game = e2e_setup

    # Init
    assert run_cli("--workspace", str(ws), "project", "init") == 0
    assert run_cli("--workspace", str(ws), "project", "info") == 0

    # Detect
    assert run_cli("--workspace", str(ws), "game", "detect", str(game)) == 0

    # Extract
    assert run_cli("--workspace", str(ws), "extract", str(game)) == 0

    # Translate
    # Mock ArgosTranslateProvider so it doesn't fail
    from gamelingo.translation.provider import TranslationResult

    class FakeArgosProvider:
        def __init__(self, *args, **kwargs):
            pass

        def translate_batch(self, reqs):
            return [
                TranslationResult(r.id, "Hola, World!", "fake_provider", "fake_model")
                for r in reqs
            ]

    # We must patch it in app.py
    import gamelingo.app as app

    monkeypatch.setattr(app, "ArgosTranslateProvider", FakeArgosProvider, raising=False)
    # Also patch it in the module scope where it's imported inside the function
    import sys

    class MockArgosModule:
        ArgosTranslateProvider = FakeArgosProvider

    monkeypatch.setitem(
        sys.modules, "gamelingo.translation.argos_provider", MockArgosModule()
    )

    assert run_cli("--workspace", str(ws), "translate") == 0

    # Review
    assert run_cli("--workspace", str(ws), "review", "list") == 0

    # Find the unit id
    db_path = ws / "gamelingo.db"
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT id FROM translation_units").fetchone()
    assert row
    unit_id = row["id"]
    conn.close()

    assert run_cli("--workspace", str(ws), "review", "show", unit_id) == 0

    # Edit text
    assert (
        run_cli("--workspace", str(ws), "review", "edit", unit_id, "Hola edited") == 0
    )

    # Approve
    assert run_cli("--workspace", str(ws), "review", "approve", unit_id) == 0

    # Plan
    plan_file = ws / "plan.json"
    assert (
        run_cli("--workspace", str(ws), "plan", "create", "--plan-file", str(plan_file))
        == 0
    )
    assert plan_file.exists()

    assert run_cli("--workspace", str(ws), "plan", "validate", str(plan_file)) == 0

    # Apply preview
    assert run_cli("--workspace", str(ws), "apply", str(plan_file)) == 0

    # Apply execute
    assert (
        run_cli("--workspace", str(ws), "apply", str(plan_file), "--execute", "--yes")
        == 0
    )

    # Verify patch
    with open(game / "data" / "Map001.json", "r", encoding="utf-8") as f:
        patched_data = json.load(f)
    assert (
        patched_data["events"][1]["pages"][0]["list"][0]["parameters"][0]
        == "Hola edited"
    )
