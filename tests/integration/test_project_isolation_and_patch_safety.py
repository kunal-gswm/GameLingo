import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from gamelingo.app import cmd_plan_create
from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.gui.pages.dashboard import DashboardPage
from gamelingo.gui.pages.patch_page import PatchPage
from gamelingo.gui.pages.review_page import ReviewPage
from gamelingo.gui.state import AppState
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan, validate_plan
from gamelingo.services.extraction import ExtractionService
from gamelingo.storage.database import Database
from gamelingo.translation.review import ReviewService


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def create_synthetic_rpgmaker_game(
    game_dir: Path, map1_lines: list, game_title: str = "Test RPG"
):
    data_dir = game_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    js_dir = game_dir / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    (js_dir / "rmmz_core.js").write_text("// RMMZ", encoding="utf-8")
    (game_dir / "game.rmmzproject").write_text("", encoding="utf-8")

    (data_dir / "System.json").write_text(
        json.dumps(
            {
                "gameTitle": game_title,
                "terms": {
                    "basic": ["Level", "HP", "MP"],
                    "commands": ["Fight", "Escape"],
                },
            }
        ),
        encoding="utf-8",
    )

    events1 = []
    for idx, text in enumerate(map1_lines, start=1):
        events1.append(
            {
                "id": idx,
                "name": f"EV{idx}",
                "pages": [
                    {
                        "list": [
                            {"code": 101, "parameters": ["Actor1", 0, 0, 2, "Hero"]},
                            {"code": 401, "parameters": [text]},
                            {"code": 0, "parameters": []},
                        ]
                    }
                ],
            }
        )
    (data_dir / "Map001.json").write_text(
        json.dumps({"events": [None] + events1}),
        encoding="utf-8",
    )


class ArgsObj:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Scenario 1: Default project dashboard counts only default units
# ---------------------------------------------------------------------------
def test_scenario_1_default_dashboard_counts_only_default_units(qapp, tmp_path: Path):
    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    game_default = tmp_path / "game_default"
    create_synthetic_rpgmaker_game(
        game_default, ["Default Line 1", "Default Line 2"], "Default Game"
    )

    game_b = tmp_path / "game_b"
    create_synthetic_rpgmaker_game(
        game_b, ["Project B Line 1", "Project B Line 2", "Project B Line 3"], "Game B"
    )

    service = ExtractionService(db)
    service.extract_project(game_default, project_id="default")
    service.extract_project(game_b, project_id="proj_b")

    state = AppState()
    state.open_workspace(tmp_path / "workspace")
    state.set_game_path(game_default, project_id="default")

    dashboard = DashboardPage(state)
    dashboard.refresh()

    # Default has 2 map lines * 2 + 1 gameTitle + 5 terms = 10 units
    # Project B has 3 map lines * 2 + 1 gameTitle + 5 terms = 12 units
    # Total units across DB = 22, but dashboard must show ONLY default's units (10)
    assert dashboard.lbl_metric_extracted.text() == "10"


# ---------------------------------------------------------------------------
# Scenario 2: Default patch plan cannot contain another project's approvals
# ---------------------------------------------------------------------------
def test_scenario_2_default_patch_plan_cannot_contain_another_project_approvals(
    qapp, tmp_path: Path
):
    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    game_default = tmp_path / "game_default"
    create_synthetic_rpgmaker_game(game_default, ["Def Text 1"], "Default Game")
    game_b = tmp_path / "game_b"
    create_synthetic_rpgmaker_game(game_b, ["B Text 1"], "Game B")

    service = ExtractionService(db)
    service.extract_project(game_default, project_id="default")
    service.extract_project(game_b, project_id="proj_b")

    review = ReviewService(db)
    # Approve one unit in default
    u_def = next(
        u
        for u in review.list_units_for_review("default", ["untranslated"])
        if u["source_text"] == "Def Text 1"
    )
    review.update_translation(u_def["id"], "Traduction Def 1")
    review.approve(u_def["id"])

    # Approve one unit in proj_b
    u_b = next(
        u
        for u in review.list_units_for_review("proj_b", ["untranslated"])
        if u["source_text"] == "B Text 1"
    )
    review.update_translation(u_b["id"], "Traduction B 1")
    review.approve(u_b["id"])

    state = AppState()
    state.open_workspace(tmp_path / "workspace")
    state.set_game_path(game_default, project_id="default")

    patch_page = PatchPage(state)
    patch_page.refresh()
    patch_page.on_create_plan()

    assert patch_page.current_plan is not None
    plan = patch_page.current_plan
    assert plan["project_id"] == "default"
    assert plan["target_root"] == str(game_default.resolve())

    # Ensure plan edits ONLY contain default units, NOT proj_b units
    edit_unit_ids = [e["unit_id"] for e in plan["edits"]]
    assert u_def["id"] in edit_unit_ids
    assert u_b["id"] not in edit_unit_ids


# ---------------------------------------------------------------------------
# Scenario 3: Non-default project review queue displays only its own units
# ---------------------------------------------------------------------------
def test_scenario_3_non_default_project_review_queue_isolation(qapp, tmp_path: Path):
    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    game_a = tmp_path / "game_a"
    create_synthetic_rpgmaker_game(game_a, ["A Text Unique"], "Game A")
    game_b = tmp_path / "game_b"
    create_synthetic_rpgmaker_game(game_b, ["B Text Unique"], "Game B")

    service = ExtractionService(db)
    service.extract_project(game_a, project_id="proj_a")
    service.extract_project(game_b, project_id="proj_b")

    state = AppState()
    state.open_workspace(tmp_path / "workspace")
    state.set_game_path(game_b, project_id="proj_b")

    review_page = ReviewPage(state)
    # Set to 'all' so untranslated units are visible in queue
    review_page.cmb_status.setCurrentIndex(1)
    review_page.refresh()

    items = [
        review_page.list_widget.item(i).text()
        for i in range(review_page.list_widget.count())
    ]
    assert any("B Text Unique" in t for t in items)
    assert not any("A Text Unique" in t for t in items)


# ---------------------------------------------------------------------------
# Scenario 4: Switching projects refreshes review queue and counts without leaking units
# ---------------------------------------------------------------------------
def test_scenario_4_switching_projects_refreshes_queue_without_leaks(
    qapp, tmp_path: Path
):
    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    game_a = tmp_path / "game_a"
    create_synthetic_rpgmaker_game(game_a, ["Line Game A"], "Game A")
    game_b = tmp_path / "game_b"
    create_synthetic_rpgmaker_game(game_b, ["Line Game B"], "Game B")

    service = ExtractionService(db)
    service.extract_project(game_a, project_id="proj_a")
    service.extract_project(game_b, project_id="proj_b")

    state = AppState()
    state.open_workspace(tmp_path / "workspace")

    # Select Game A
    state.set_game_path(game_a, project_id="proj_a")
    review_page = ReviewPage(state)
    review_page.cmb_status.setCurrentIndex(1)  # All items
    review_page.refresh()

    # Select an item in Game A
    assert review_page.list_widget.count() > 0
    review_page.list_widget.setCurrentRow(0)
    assert review_page.current_unit_id is not None
    selected_id_a = review_page.current_unit_id
    assert selected_id_a.startswith("proj_a::")

    # Switch to Game B
    state.set_game_path(game_b, project_id="proj_b")
    review_page.refresh()

    # Current unit must be reset, editor cleared, no Game A units in list
    assert review_page.current_unit_id is None
    assert review_page.txt_source.toPlainText() == ""
    assert review_page.txt_target.toPlainText() == ""

    for i in range(review_page.list_widget.count()):
        u_id = review_page.list_widget.item(i).data(Qt.UserRole)
        assert u_id is not None
        assert u_id.startswith("proj_b::")
        assert not u_id.startswith("proj_a::")


# ---------------------------------------------------------------------------
# Scenario 5: CLI plan creation for project B contains no units from project A
# ---------------------------------------------------------------------------
def test_scenario_5_cli_plan_create_isolation(tmp_path: Path):
    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    game_a = tmp_path / "game_a"
    create_synthetic_rpgmaker_game(game_a, ["Dialogue Alpha"], "Game A")
    game_b = tmp_path / "game_b"
    create_synthetic_rpgmaker_game(game_b, ["Dialogue Beta"], "Game B")

    service = ExtractionService(db)
    service.extract_project(game_a, project_id="proj_a")
    service.extract_project(game_b, project_id="proj_b")

    review = ReviewService(db)
    # Approve units in both
    u_a = next(
        u
        for u in review.list_units_for_review("proj_a", ["untranslated"])
        if u["source_text"] == "Dialogue Alpha"
    )
    review.update_translation(u_a["id"], "Trad Alpha")
    review.approve(u_a["id"])

    u_b = next(
        u
        for u in review.list_units_for_review("proj_b", ["untranslated"])
        if u["source_text"] == "Dialogue Beta"
    )
    review.update_translation(u_b["id"], "Trad Beta")
    review.approve(u_b["id"])

    plan_file_b = tmp_path / "plan_b.json"
    args = ArgsObj(
        workspace=str(tmp_path / "workspace"),
        project_id="proj_b",
        plan_file=str(plan_file_b),
        activate_language=False,
    )
    cmd_plan_create(args)

    assert plan_file_b.exists()
    with open(plan_file_b, "r", encoding="utf-8") as f:
        plan_b = json.load(f)

    assert plan_b["project_id"] == "proj_b"
    assert plan_b["target_root"] == str(game_b.resolve())
    unit_ids = [e["unit_id"] for e in plan_b["edits"]]
    assert u_b["id"] in unit_ids
    assert u_a["id"] not in unit_ids


# ---------------------------------------------------------------------------
# Scenario 6: Plan for project A rejected when applied against project B root
# ---------------------------------------------------------------------------
def test_scenario_6_plan_a_rejected_when_applied_against_project_b_root(tmp_path: Path):
    game_a = tmp_path / "game_a"
    create_synthetic_rpgmaker_game(game_a, ["Text A"], "Game A")
    game_b = tmp_path / "game_b"
    create_synthetic_rpgmaker_game(game_b, ["Text B"], "Game B")

    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    service.extract_project(game_a, project_id="proj_a")
    service.extract_project(game_b, project_id="proj_b")

    review = ReviewService(db)
    u_a_short = next(
        u
        for u in review.list_units_for_review("proj_a", ["untranslated"])
        if u["source_text"] == "Text A"
    )
    review.update_translation(u_a_short["id"], "Trad A")
    review.approve(u_a_short["id"])
    u_a = review.get_unit(u_a_short["id"])

    # Create plan for proj_a
    unit = TranslationUnit(
        id=u_a["id"],
        file_id=u_a["file_id"],
        locator=u_a["locator"],
        source_text=u_a["source_text"],
        context=u_a["context"],
        tokens_json=u_a["tokens_json"],
        source_hash=u_a["source_hash"],
        status="approved",
    )
    rec = TranslationRecord(
        id="rec_a",
        unit_id=u_a["id"],
        draft_text="Trad A",
        final_text="Trad A",
    )
    file_map = {u_a["file_id"]: "data/Map001.json"}
    plan_a = create_plan(game_a, "proj_a", [unit], [rec], file_map)

    # Applying against game_b must fail closed!
    backup_root = tmp_path / "workspace" / "backups"
    report = apply_plan(
        game_b, plan_a, backup_root, execute=True, expected_project_id="proj_b"
    )
    assert report["status"] == "failed"
    assert any("mismatch" in e.lower() for e in report["errors"])


# ---------------------------------------------------------------------------
# Scenario 7: Plan for project B rejected when validated or applied against project A root
# ---------------------------------------------------------------------------
def test_scenario_7_plan_b_rejected_when_validated_or_applied_against_project_a_root(
    tmp_path: Path,
):
    game_a = tmp_path / "game_a"
    create_synthetic_rpgmaker_game(game_a, ["Text A"], "Game A")
    game_b = tmp_path / "game_b"
    create_synthetic_rpgmaker_game(game_b, ["Text B"], "Game B")

    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    service.extract_project(game_b, project_id="proj_b")

    review = ReviewService(db)
    u_b_short = next(
        u
        for u in review.list_units_for_review("proj_b", ["untranslated"])
        if u["source_text"] == "Text B"
    )
    review.update_translation(u_b_short["id"], "Trad B")
    review.approve(u_b_short["id"])
    u_b = review.get_unit(u_b_short["id"])

    unit = TranslationUnit(
        id=u_b["id"],
        file_id=u_b["file_id"],
        locator=u_b["locator"],
        source_text=u_b["source_text"],
        context=u_b["context"],
        tokens_json=u_b["tokens_json"],
        source_hash=u_b["source_hash"],
        status="approved",
    )
    rec = TranslationRecord(
        id="rec_b",
        unit_id=u_b["id"],
        draft_text="Trad B",
        final_text="Trad B",
    )
    file_map = {u_b["file_id"]: "data/Map001.json"}
    plan_b = create_plan(game_b, "proj_b", [unit], [rec], file_map)

    from gamelingo.patching.planner import PlanValidationError

    # Validation against game_a root must fail
    with pytest.raises(PlanValidationError, match="target root mismatch"):
        validate_plan(game_a, plan_b)

    # Applying against game_a root must fail
    backup_root = tmp_path / "workspace" / "backups"
    report = apply_plan(game_a, plan_b, backup_root, execute=True)
    assert report["status"] == "failed"
    assert any("mismatch" in e.lower() for e in report["errors"])


# ---------------------------------------------------------------------------
# Scenario 8: Unknown project ID or unresolved install path fails safely
# ---------------------------------------------------------------------------
def test_scenario_8_unknown_project_fails_safely(tmp_path: Path):
    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    review = ReviewService(db)
    # Querying nonexistent project returns empty list without error
    units = review.list_units_for_review("nonexistent_project_xyz")
    assert units == []

    # CLI plan create with nonexistent project exits with code 1
    args = ArgsObj(
        workspace=str(tmp_path / "workspace"),
        project_id="nonexistent_project_xyz",
        plan_file=str(tmp_path / "plan_xyz.json"),
        activate_language=False,
    )
    with pytest.raises(SystemExit) as exc_info:
        cmd_plan_create(args)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Scenario 9: Selected project with no approved units cannot fall back to another project's approvals
# ---------------------------------------------------------------------------
def test_scenario_9_no_fallback_to_other_project_approvals(qapp, tmp_path: Path):
    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    game_default = tmp_path / "game_default"
    create_synthetic_rpgmaker_game(game_default, ["Def Approved"], "Default Game")
    game_unapproved = tmp_path / "game_unapproved"
    create_synthetic_rpgmaker_game(game_unapproved, ["Unapproved"], "Game Unapproved")

    service = ExtractionService(db)
    service.extract_project(game_default, project_id="default")
    service.extract_project(game_unapproved, project_id="proj_unapproved")

    review = ReviewService(db)
    u_def = next(
        u
        for u in review.list_units_for_review("default", ["untranslated"])
        if u["source_text"] == "Def Approved"
    )
    review.update_translation(u_def["id"], "Trad Def Approved")
    review.approve(u_def["id"])

    state = AppState()
    state.open_workspace(tmp_path / "workspace")
    state.set_game_path(game_unapproved, project_id="proj_unapproved")

    patch_page = PatchPage(state)
    patch_page.refresh()

    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        patch_page.on_create_plan()
        mock_info.assert_called_once()
        assert patch_page.current_plan is None
        assert not patch_page.btn_apply.isEnabled()


# ---------------------------------------------------------------------------
# Scenario 10: Single-project/default workflow still passes
# ---------------------------------------------------------------------------
def test_scenario_10_single_project_default_workflow_passes(qapp, tmp_path: Path):
    game_dir = tmp_path / "game"
    create_synthetic_rpgmaker_game(game_dir, ["Single Default Line"], "Single Game")

    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    res = service.extract_project(game_dir, project_id="default")
    assert res.extracted_units == 8

    review = ReviewService(db)
    units = review.list_units_for_review("default", ["untranslated"])
    target_u = next(u for u in units if u["source_text"] == "Single Default Line")
    review.update_translation(target_u["id"], "Single Translated Line")
    review.approve(target_u["id"])

    state = AppState()
    state.open_workspace(tmp_path / "workspace")
    state.set_game_path(game_dir, project_id="default")

    patch_page = PatchPage(state)
    patch_page.refresh()
    patch_page.on_create_plan()

    assert patch_page.current_plan is not None
    assert patch_page.btn_apply.isEnabled()
    assert patch_page.current_plan["project_id"] == "default"

    with (
        patch("PySide6.QtWidgets.QMessageBox.warning", return_value=QMessageBox.Yes),
        patch("PySide6.QtWidgets.QMessageBox.information"),
    ):
        patch_page.on_apply_plan()

    map_data = json.loads(
        (game_dir / "data" / "Map001.json").read_text(encoding="utf-8")
    )
    assert (
        map_data["events"][1]["pages"][0]["list"][1]["parameters"][0]
        == "Single Translated Line"
    )


# ---------------------------------------------------------------------------
# Scenario 11: Exact Extraction Lifecycle Metrics
# ---------------------------------------------------------------------------
def test_exact_extraction_lifecycle_metrics(tmp_path: Path):
    game_dir = tmp_path / "game_metrics"
    create_synthetic_rpgmaker_game(game_dir, ["Line 1", "Line 2", "Line 3"])

    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)

    # 1. Initial Extraction (3 events * 2 units + System.json 6 units = 12 units)
    res1 = service.extract_project(game_dir, project_id="proj_m")
    assert res1.added_units == 12
    assert res1.updated_units == 0
    assert res1.retained_units == 0
    assert res1.obsolete_units == 0
    assert res1.active_units == 12
    assert res1.extracted_units == 12

    # 2. Unchanged Re-extraction
    res2 = service.extract_project(game_dir, project_id="proj_m")
    assert res2.added_units == 0
    assert res2.updated_units == 0
    assert res2.retained_units == 12
    assert res2.obsolete_units == 0
    assert res2.active_units == 12

    # 3. Modified source text in Line 2
    create_synthetic_rpgmaker_game(game_dir, ["Line 1", "Line 2 Modified", "Line 3"])
    res3 = service.extract_project(game_dir, project_id="proj_m")
    assert res3.added_units == 0
    assert res3.updated_units == 1
    assert res3.retained_units == 11
    assert res3.obsolete_units == 0
    assert res3.active_units == 12

    # 4. Removed Line 3 (event 3 removed = 2 units removed, now 10 active, 2 obsolete)
    create_synthetic_rpgmaker_game(game_dir, ["Line 1", "Line 2 Modified"])
    res4 = service.extract_project(game_dir, project_id="proj_m")
    assert res4.added_units == 0
    assert res4.updated_units == 0
    assert res4.retained_units == 10
    assert res4.obsolete_units == 2
    assert res4.active_units == 10


# ---------------------------------------------------------------------------
# Scenario 12: Extraction Failure Safety
# ---------------------------------------------------------------------------
def test_extraction_failure_and_cancellation_safety(tmp_path: Path):
    game_dir = tmp_path / "game_failure"
    create_synthetic_rpgmaker_game(game_dir, ["Line Initial"])

    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    service.extract_project(game_dir, project_id="proj_fail")

    # Corrupt a file to cause extraction failure
    (game_dir / "data" / "Map001.json").write_text("{ INVALID JSON", encoding="utf-8")

    with pytest.raises(Exception):
        service.extract_project(game_dir, project_id="proj_fail")

    # Production units must remain intact from before the failure
    conn = db.connect()
    cur = conn.execute(
        "SELECT COUNT(*) as cnt FROM translation_units WHERE project_id = 'proj_fail'"
    )
    assert cur.fetchone()["cnt"] > 0

    # Staging tables must be clean
    cur = conn.execute("SELECT COUNT(*) as cnt FROM staging_translation_units")
    assert cur.fetchone()["cnt"] == 0
