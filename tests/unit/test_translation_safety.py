"""
Unit tests for translation safety hardening (GL Phase 2).
Covers:
1. Python format specifiers (%02d, %.2f, %(name)s, %1..%9, repeated %d/%d).
2. Ren'Py bracket interpolations ([player_name], [_gl_unlocked], [flag!t]) and escaped brackets ([[).
3. Ren'Py formatting tags ({color=...}, {size=...}, {b}, {/b}) and unclosed tag detection.
4. Acceptance gate in validate_translation(): detecting dropped, duplicated, unexpected tokens, unescaped brackets, and multiline newline mismatch.
5. Acceptance gate in patch planner: create_plan() rejecting unsafe edits and validate_plan() blocking unsafe plans.
6. Acceptance gate in review service: approve() raising ValueError on errors and approve_all() skipping error units.
"""

from pathlib import Path

import pytest

from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.patching.planner import PlanValidationError, create_plan, validate_plan
from gamelingo.storage.database import Database
from gamelingo.translation.placeholders import (
    PLACEHOLDER_REGEX,
    PlaceholderProtector,
)
from gamelingo.translation.review import ReviewService
from gamelingo.translation.validation import validate_translation

# =========================================================================
# 1. Placeholder and Format Specifier Regex Matching Tests
# =========================================================================


def test_format_specifier_matching():
    """Verifies that PLACEHOLDER_REGEX matches all required Python printf and index placeholders."""
    samples = [
        ("%s", "%s"),
        ("%d", "%d"),
        ("%02d", "%02d"),
        ("%.2f", "%.2f"),
        ("%+10.4f", "%+10.4f"),
        ("%(player_name)s", "%(player_name)s"),
        ("%1", "%1"),
        ("%9", "%9"),
    ]
    for text, expected in samples:
        matches = [m.group(0) for m in PLACEHOLDER_REGEX.finditer(text)]
        assert expected in matches, f"Failed to match '{expected}' in '{text}'"


def test_renpy_markup_and_escapes_matching():
    """Verifies that PLACEHOLDER_REGEX matches Ren'Py tags, brackets, and escaped delimiters."""
    samples = [
        ("[player_name]", "[player_name]"),
        ("[_gl_unlocked]", "[_gl_unlocked]"),
        ("[flag!t]", "[flag!t]"),
        ("[item:val]", "[item:val]"),
        ("[[", "[["),
        ("{{", "{{"),
        ("{b}", "{b}"),
        ("{/b}", "{/b}"),
        ("{color=#ff0000}", "{color=#ff0000}"),
        ("{size=21}", "{size=21}"),
    ]
    for text, expected in samples:
        matches = [m.group(0) for m in PLACEHOLDER_REGEX.finditer(text)]
        assert expected in matches, f"Failed to match '{expected}' in '{text}'"


# =========================================================================
# 2. Acceptance Gate in validate_translation() Tests
# =========================================================================


def test_validation_detects_missing_placeholders():
    """Rejects translations where placeholders from the source are missing."""
    issues = validate_translation("Level %d / %d", "Level %d")
    errors = [i for i in issues if i.severity == "error"]
    assert any(i.code == "MISSING_PLACEHOLDER" for i in errors)


def test_validation_detects_duplicated_placeholders():
    """Rejects translations where placeholders are duplicated."""
    issues = validate_translation("Value: %d", "Value: %d %d")
    errors = [i for i in issues if i.severity == "error"]
    assert any(
        i.code in ("DUPLICATED_PLACEHOLDER", "DUPLICATE_PLACEHOLDER") for i in errors
    )


def test_validation_detects_unexpected_tokens():
    """Rejects translations that introduce new placeholder tokens not present in source."""
    issues = validate_translation("Hello world", "Hello [player_name]")
    errors = [i for i in issues if i.severity == "error"]
    assert any(i.code in ("UNEXPECTED_PLACEHOLDER", "UNEXPECTED_TOKEN") for i in errors)


def test_validation_detects_unescaped_brackets():
    """Detects unescaped square brackets that could cause Ren'Py expression evaluation crashes."""
    # When source has no brackets, target introducing [Current life] is an unsafe interpolation
    issues = validate_translation("夜の本命", "[Current life] Night's choice")
    errors = [i for i in issues if i.severity == "error"]
    assert any(
        i.code in ("UNSAFE_INTERPOLATION", "UNEXPECTED_PLACEHOLDER", "UNEXPECTED_TOKEN")
        for i in errors
    )


def test_validation_detects_unclosed_tags():
    """Detects unclosed Ren'Py formatting tags such as {b} without {/b}."""
    issues = validate_translation("{b}Important{/b}", "{b}Important")
    errors = [i for i in issues if i.severity == "error"]
    assert any(i.code == "MALFORMED_MARKUP" for i in errors)


def test_validation_detects_multiline_newline_mismatch():
    """Detects newline count mismatches across multiline texts."""
    source = "Line 1\nLine 2\nLine 3"
    target = "Line 1 Line 2 Line 3"
    issues = validate_translation(source, target)
    errors = [i for i in issues if i.severity == "error"]
    assert any(i.code == "NEWLINE_MISMATCH" for i in errors)


def test_validation_permits_clean_translation_with_preserved_markup():
    """Passes translations where all format specifiers, tags, and newlines match perfectly."""
    source = "{size=15}%d/%d{/size}\n[_gl_unlocked] items"
    target = "{size=15}%d/%d{/size}\n[_gl_unlocked] items"
    issues = validate_translation(source, target, is_passthrough=True)
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) == 0


# =========================================================================
# 3. Patch Planner Acceptance Gate Tests
# =========================================================================


def test_planner_create_plan_rejects_unsafe_translations(tmp_path: Path):
    """create_plan() must reject edits that fail safety validation even if unit status is approved."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    script = game_root / "script.rpy"
    script.write_text('define e = Character("Eileen")\n', encoding="utf-8")

    unit = TranslationUnit(
        id="u_unsafe",
        file_id="script.rpy",
        locator="line_1",
        source_text="Welcome %d",
        context="ctx",
        tokens_json="[]",
        source_hash="h1",
        status="approved",  # Marked approved, but translation is broken!
    )
    # Record dropped %d
    record = TranslationRecord(
        id="r_unsafe",
        unit_id="u_unsafe",
        provider="argos",
        model="1.1",
        draft_text="Welcome",
        final_text="Welcome",  # Missing %d!
        quality_flags="[]",
        created_at=0,
        updated_at=0,
    )

    plan = create_plan(tmp_path, "proj_test", [unit], [record], adapter_id="renpy")
    assert len(plan["edits"]) == 1
    edit = plan["edits"][0]
    assert edit["status"] == "rejected"
    assert edit["reason"] == "safety_validation_failed"


def test_planner_validate_plan_fails_closed_on_unsafe_edit(tmp_path: Path):
    """validate_plan() must raise PlanValidationError if a plan contains a valid edit with unsafe translation."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    script = game_root / "script.rpy"
    script.write_text('define e = Character("Eileen")\n', encoding="utf-8")

    malformed_plan = {
        "version": "1.0",
        "plan_id": "test_plan",
        "project_id": "proj_test",
        "adapter_id": "renpy",
        "edits": [
            {
                "unit_id": "u1",
                "file_id": "script.rpy",
                "file_path": "game/tl/english/strings.rpy",
                "source_file_path": "script.rpy",
                "locator": "l1",
                "original_text": "Score: %d",
                "translated_text": "Score: %d %s",  # Unexpected %s!
                "status": "valid",
                "engine": "renpy",
            }
        ],
    }

    with pytest.raises(PlanValidationError, match="Safety validation failed"):
        validate_plan(tmp_path, malformed_plan)


# =========================================================================
# 4. Review Service Acceptance Gate Tests
# =========================================================================


def test_review_service_blocks_approval_of_unsafe_unit(tmp_path: Path):
    """ReviewService.approve() raises ValueError if translated text fails safety validation."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    service = ReviewService(db)

    conn = db.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) "
            "VALUES ('proj1', 'Title', 'Path', 'renpy', '1.0', 0)"
        )
        conn.execute(
            "INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) "
            "VALUES ('f1', 'proj1', 'script.rpy', 'rpy', 'h', 0, 0)"
        )
        conn.execute(
            "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) "
            "VALUES ('u1', 'f1', 'l1', 'Total: %d items', 'c', '[]', 'h', 'draft')"
        )
        conn.execute(
            "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) "
            "VALUES ('r1', 'u1', 'argos', '1.1', 'Total items', 'Total items', '[]', 0, 0)"
        )

    with pytest.raises(ValueError, match="blocking errors"):
        service.approve("u1")


def test_review_service_approve_all_skips_unsafe_units(tmp_path: Path):
    """ReviewService.approve_all() approves valid units and skips units with safety errors."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    service = ReviewService(db)

    conn = db.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) "
            "VALUES ('proj1', 'Title', 'Path', 'renpy', '1.0', 0)"
        )
        conn.execute(
            "INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) "
            "VALUES ('f1', 'proj1', 'script.rpy', 'rpy', 'h', 0, 0)"
        )
        # Unit 1: Valid translation
        conn.execute(
            "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) "
            "VALUES ('u1', 'f1', 'l1', 'Hello %s', 'c', '[]', 'h', 'draft')"
        )
        conn.execute(
            "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) "
            "VALUES ('r1', 'u1', 'argos', '1.1', 'Hello %s', 'Hello %s', '[]', 0, 0)"
        )
        # Unit 2: Unsafe translation (dropped %s)
        conn.execute(
            "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) "
            "VALUES ('u2', 'f1', 'l2', 'Goodbye %s', 'c', '[]', 'h', 'draft')"
        )
        conn.execute(
            "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) "
            "VALUES ('r2', 'u2', 'argos', '1.1', 'Goodbye', 'Goodbye', '[]', 0, 0)"
        )

    summary = service.approve_all("proj1")
    assert summary["approved"] == 1
    assert summary["skipped"] == 1

    assert service.get_unit("u1")["status"] == "approved"
    assert service.get_unit("u2")["status"] == "draft"


# =========================================================================
# 5. Sentinel Style Resilience Tests
# =========================================================================


def test_placeholder_protector_sentinel_styles():
    """Verifies that PlaceholderProtector supports default, bracket, and brace sentinel styles."""
    src = "Score: %d in [location] with {color=#fff}tag{/color}"

    for style in ("default", "bracket", "brace"):
        prot = PlaceholderProtector(sentinel_style=style)
        masked = prot.mask(src)
        assert "%d" not in masked
        assert "[location]" not in masked
        assert "{color=#fff}" not in masked
        restored = prot.restore(masked)
        assert restored == src
