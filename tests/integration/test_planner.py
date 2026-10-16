import json
from pathlib import Path

import pytest

from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.patching.planner import (
    PlanValidationError,
    create_plan,
    preview_plan,
    validate_plan,
)


@pytest.fixture
def plan_setup(tmp_path: Path):
    source_root = tmp_path / "game_root"
    source_root.mkdir()

    file1 = source_root / "data" / "Map001.json"
    file1.parent.mkdir()

    data = {
        "events": [
            None,
            {
                "pages": [
                    {
                        "list": [
                            {"code": 401, "parameters": ["Hello!"]},
                            {"code": 102, "parameters": [["Yes", "No"]]},
                            {"code": 402, "parameters": [0, "Yes"]},
                        ]
                    }
                ]
            },
        ]
    }
    with open(file1, "w", encoding="utf-8") as f:
        json.dump(data, f)

    u1 = TranslationUnit(
        "u1",
        "data/Map001.json",
        "events[1].pages[0].list[0]",
        "Hello!",
        "ctx",
        "[]",
        "hash1",
        "approved",
    )
    r1 = TranslationRecord("r1", "u1", "prov", "mod", "Hola!", "Hola!", "flag", 0, 0)

    u2 = TranslationUnit(
        "u2",
        "data/Map001.json",
        "events[1].pages[0].list[1].choices[1]",
        "No",
        "ctx",
        "[]",
        "hash2",
    )
    r2 = TranslationRecord("r2", "u2", "prov", "mod", "No", "No", "flag", 0, 0)

    return source_root, [u1, u2], [r1, r2]


def test_create_valid_plan(plan_setup):
    source_root, units, records = plan_setup

    for __u in units:
        __u.status = "approved"
    plan = create_plan(source_root, "proj1", units, records)

    assert plan["version"] == "1.1"
    assert len(plan["edits"]) == 2
    assert all(e["status"] == "valid" for e in plan["edits"])

    # validate
    assert validate_plan(source_root, plan) is True

    # preview
    preview = preview_plan(plan)
    assert "[VALID] data/Map001.json @ events[1].pages[0].list[0]" in preview
    assert "+ Hola!" in preview


def test_missing_translation(plan_setup):
    source_root, units, records = plan_setup

    for __u in units:
        __u.status = "approved"
    plan = create_plan(source_root, "proj1", units, [records[0]])  # r2 missing

    edits = plan["edits"]
    assert edits[0]["status"] == "valid"
    assert edits[1]["status"] == "rejected"
    assert edits[1]["reason"] == "missing_translation"


def test_stale_source(plan_setup):
    source_root, units, records = plan_setup

    # Change the original file so it doesn't match the TranslationUnit
    file1 = source_root / "data" / "Map001.json"
    with open(file1, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["events"][1]["pages"][0]["list"][0]["parameters"][0] = "Modified Source!"
    with open(file1, "w", encoding="utf-8") as f:
        json.dump(data, f)

    for __u in units:
        __u.status = "approved"
    plan = create_plan(source_root, "proj1", units, records)

    stale_edit = next(e for e in plan["edits"] if e["unit_id"] == "u1")
    assert stale_edit["status"] == "rejected"
    assert stale_edit["reason"] == "stale_source"


def test_conflict_translations(plan_setup):
    source_root, units, records = plan_setup

    u3 = TranslationUnit(
        "u3",
        "data/Map001.json",
        "events[1].pages[0].list[0]",
        "Hello!",
        "ctx",
        "[]",
        "hash1",
        "approved",
    )
    r3 = TranslationRecord(
        "r3",
        "u3",
        "prov",
        "mod",
        "Different Translation",
        "Different Translation",
        "flag",
        0,
        0,
    )

    units.append(u3)
    records.append(r3)

    for __u in units:
        __u.status = "approved"
    plan = create_plan(source_root, "proj1", units, records)

    conflicts = [e for e in plan["edits"] if e["status"] == "conflict"]
    assert len(conflicts) == 2


def test_validate_plan_catches_unsafe_paths(plan_setup):
    source_root, units, records = plan_setup
    for __u in units:
        __u.status = "approved"
    plan = create_plan(source_root, "proj1", units, records)

    plan["edits"][0]["file_path"] = "../unsafe.json"

    with pytest.raises(PlanValidationError, match="Invalid path"):
        validate_plan(source_root, plan)


def test_validate_plan_catches_stale_source(plan_setup):
    source_root, units, records = plan_setup
    for __u in units:
        __u.status = "approved"
    plan = create_plan(source_root, "proj1", units, records)

    # modify file after plan is created
    file1 = source_root / "data" / "Map001.json"
    with open(file1, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["events"][1]["pages"][0]["list"][0]["parameters"][0] = "Modified Source!"
    with open(file1, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(PlanValidationError, match="Stale source"):
        validate_plan(source_root, plan)
