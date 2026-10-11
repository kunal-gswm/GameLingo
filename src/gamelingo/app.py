import argparse
import json
import sys
import time
from pathlib import Path

from gamelingo import __version__
from gamelingo.adapters.registry import detect_adapter
from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan, preview_plan, validate_plan
from gamelingo.storage.database import Database
from gamelingo.translation.pipeline import TranslationPipeline
from gamelingo.translation.review import ReviewService


def get_db(workspace: str) -> Database:
    path = Path(workspace)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    db_path = path / "gamelingo.db"
    db = Database(db_path)
    db.migrate()
    return db


def cmd_project_init(args):
    db = get_db(args.workspace)
    conn = db.connect()
    with conn:
        cur = conn.execute("SELECT id FROM projects WHERE id = 'default'")
        if not cur.fetchone():
            conn.execute(
                "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "default",
                    "Default Project",
                    "",
                    "rpgmaker_mv_mz",
                    "1.0",
                    time.time(),
                ),
            )
    print(f"Initialized workspace at {Path(args.workspace).absolute()}")


def cmd_project_info(args):
    db = get_db(args.workspace)
    conn = db.connect()
    cur = conn.execute("SELECT * FROM projects WHERE id = 'default'")
    row = cur.fetchone()
    if row:
        print(f"Project ID: {row['id']}")
        print(f"Title: {row['title']}")
        print(f"Install Path: {row['install_path']}")
        print(f"Adapter: {row['adapter_id']}")
    else:
        print("No project found. Run 'project init'.")
        sys.exit(1)


def cmd_project_verify(args):
    db = get_db(args.workspace)
    conn = db.connect()
    cur = conn.execute("SELECT install_path FROM projects WHERE id = 'default'")
    row = cur.fetchone()
    if not row or not row["install_path"]:
        print("Project uninitialized or missing game path. Run 'extract <path>' first.")
        sys.exit(1)
    ipath = Path(row["install_path"])
    if not ipath.exists():
        print(f"Error: Game path {ipath} does not exist.")
        sys.exit(1)
    print("Project verified OK.")


def cmd_game_detect(args):
    adapter, version, conf = detect_adapter(Path(args.game_path))
    if adapter and conf > 0.0:
        print(f"Detected {version} (confidence: {conf:.2f})")
    else:
        print("No supported game engine detected at this path.")
        sys.exit(1)


def cmd_game_inspect(args):
    cmd_game_detect(args)


def cmd_extract(args):
    db = get_db(args.workspace)
    game_path = Path(args.game_path).resolve()
    adapter, version, conf = detect_adapter(game_path)
    if not adapter or conf == 0.0:
        print(f"Unsupported game path: {game_path}")
        sys.exit(1)

    if hasattr(adapter, "diagnose"):
        diag = adapter.diagnose(game_path)
        if not diag.get("has_source_scripts", True):
            print(f"Extraction unsupported: {diag.get('message')}")
            sys.exit(1)

    conn = db.connect()
    with conn:
        cur = conn.execute("SELECT id FROM projects WHERE id = 'default'")
        if not cur.fetchone():
            conn.execute(
                "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "default",
                    "Default Project",
                    str(game_path),
                    adapter.adapter_id,
                    "1.0",
                    time.time(),
                ),
            )
        else:
            conn.execute(
                "UPDATE projects SET install_path = ?, adapter_id = ? WHERE id = 'default'",
                (str(game_path), adapter.adapter_id),
            )

    print(f"Extracting texts from {game_path}...")
    units = list(adapter.extract(game_path))

    with conn:
        for u in units:
            if hasattr(adapter, "get_relative_path"):
                rel = adapter.get_relative_path(game_path, u.file_id)
            else:
                rel = (
                    f"data/{u.file_id}"
                    if (game_path / "data" / u.file_id).exists()
                    else f"www/data/{u.file_id}"
                )
            fmt = "rpy" if getattr(adapter, "adapter_id", "") == "renpy" else "json"
            conn.execute(
                "INSERT OR IGNORE INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (u.file_id, "default", rel, fmt, "", 0, time.time()),
            )

            # Using INSERT OR IGNORE to not overwrite if they exist, but actually we should update if source changed.
            # For this CLI step, INSERT OR IGNORE is a safe start, but let's do INSERT OR REPLACE to keep it fresh
            # Wait, replacing means we might lose status!
            # Let's do INSERT OR IGNORE
            conn.execute(
                "INSERT OR IGNORE INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    u.id,
                    u.file_id,
                    u.locator,
                    u.source_text,
                    u.context,
                    u.tokens_json,
                    u.source_hash,
                    u.status,
                ),
            )

    print(f"Extracted {len(units)} units.")


def cmd_translate(args):
    db = get_db(args.workspace)
    from gamelingo.translation.argos_setup import ArgosSetupService, ModelStatus

    status = ArgosSetupService.check_status("ja", "en")
    if status["status"] != ModelStatus.READY:
        print(f"Cannot translate: {status['message']}")
        sys.exit(1)

    from gamelingo.translation.argos_provider import ArgosTranslateProvider

    provider = ArgosTranslateProvider()

    pipeline = TranslationPipeline(db, provider)

    conn = db.connect()
    cur = conn.execute("SELECT * FROM translation_units WHERE status = 'untranslated'")
    rows = cur.fetchall()

    if not rows:
        print("No untranslated units found.")
        sys.exit(0)

    units = []
    for r in rows:
        units.append(
            TranslationUnit(
                id=r["id"],
                file_id=r["file_id"],
                locator=r["locator"],
                source_text=r["source_text"],
                context=r["context"],
                tokens_json=r["tokens_json"],
                source_hash=r["source_hash"],
                status=r["status"],
            )
        )

    print(f"Starting translation job for {len(units)} units (JA -> EN)...")
    job_id = pipeline.create_job("default", units, "ja", "en", chunk_size=100)
    print(f"Created job {job_id}. Resuming execution...")

    while True:
        report = pipeline.resume_job(job_id)
        if report["status"] in ("completed", "failed"):
            break

    print(f"Job {job_id} finished with status: {report['status']}")
    print("Run 'gamelingo review list' to review translations.")


def cmd_jobs_list(args):
    db = get_db(args.workspace)
    conn = db.connect()
    cur = conn.execute("SELECT id, status, updated_at FROM jobs")
    jobs = cur.fetchall()
    for j in jobs:
        print(f"ID: {j['id']} | Status: {j['status']}")


def cmd_jobs_show(args):
    db = get_db(args.workspace)
    conn = db.connect()
    cur = conn.execute("SELECT * FROM jobs WHERE id = ?", (args.job_id,))
    row = cur.fetchone()
    if row:
        print(f"Job ID: {row['id']}")
        print(f"Status: {row['status']}")
        print(f"Counts: {row['counts']}")
    else:
        print(f"Job {args.job_id} not found.")
        sys.exit(1)


def cmd_jobs_resume(args):
    db = get_db(args.workspace)
    from gamelingo.translation.argos_setup import ArgosSetupService, ModelStatus

    status = ArgosSetupService.check_status("ja", "en")
    if status["status"] != ModelStatus.READY:
        print(f"Cannot resume job: {status['message']}")
        sys.exit(1)

    from gamelingo.translation.argos_provider import ArgosTranslateProvider

    provider = ArgosTranslateProvider()

    pipeline = TranslationPipeline(db, provider)
    report = pipeline.resume_job(args.job_id)
    print(f"Job status: {report['status']}")


# --- Review Commands ---
def cmd_review_list(args):
    service = ReviewService(get_db(args.workspace))
    statuses = args.status.split(",") if args.status else None
    units = service.list_units_for_review("default", statuses)
    print(f"Found {len(units)} units:")
    for u in units:
        print(
            f"[{u['status']}] ID: {u['id']} | Src: {u['source_text'][:20]} | Tgt: {(u.get('translated_text') or '')[:20]}"
        )


def cmd_review_show(args):
    service = ReviewService(get_db(args.workspace))
    unit = service.get_unit(args.unit_id)
    if not unit:
        print(f"Error: Unit {args.unit_id} not found.")
        sys.exit(1)
    print(f"Unit ID: {unit['id']}")
    print(f"Status:  {unit['status']}")
    print(f"Source:  {unit['source_text']}")
    print(f"Target:  {unit.get('translated_text', '')}")
    if unit.get("quality_flags"):
        try:
            flags = json.loads(unit["quality_flags"])
            if flags:
                print("Validation Issues:")
                for f in flags:
                    print(
                        f" - [{f.get('severity', 'error').upper()}] {f.get('code')}: {f.get('message')}"
                    )
        except Exception:
            pass


def cmd_review_edit(args):
    service = ReviewService(get_db(args.workspace))
    try:
        service.update_translation(args.unit_id, args.text)
        print(f"Updated unit {args.unit_id}. Status re-evaluated.")
        cmd_review_show(args)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_review_approve(args):
    service = ReviewService(get_db(args.workspace))
    try:
        service.approve(args.unit_id)
        print(f"Approved unit {args.unit_id}.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_review_reject(args):
    service = ReviewService(get_db(args.workspace))
    try:
        service.reject(args.unit_id, args.reason)
        print(f"Rejected unit {args.unit_id}.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_plan_create(args):
    db = get_db(args.workspace)
    conn = db.connect()

    cur = conn.execute("SELECT install_path FROM projects WHERE id = 'default'")
    row = cur.fetchone()
    if not row or not row["install_path"]:
        print("Project install path not found.")
        sys.exit(1)
    install_path = Path(row["install_path"])

    # We only fetch approved units. But wait, planner expects all units and filters them inside.
    # However, to be efficient, let's fetch units that have records.
    # The planner takes `units` and `records`.
    cur = conn.execute("SELECT * FROM translation_units WHERE status = 'approved'")
    unit_rows = cur.fetchall()

    if not unit_rows:
        print("No approved translations found to plan.")
        sys.exit(0)

    units = []
    unit_ids = []
    for r in unit_rows:
        units.append(
            TranslationUnit(
                id=r["id"],
                file_id=r["file_id"],
                locator=r["locator"],
                source_text=r["source_text"],
                context=r["context"],
                tokens_json=r["tokens_json"],
                source_hash=r["source_hash"],
                status=r["status"],
            )
        )
        unit_ids.append(r["id"])

    placeholders = ",".join("?" * len(unit_ids))
    cur = conn.execute(
        f"SELECT * FROM translation_records WHERE unit_id IN ({placeholders})",
        tuple(unit_ids),
    )
    rec_rows = cur.fetchall()

    records = []
    for r in rec_rows:
        records.append(
            TranslationRecord(
                id=r["id"],
                unit_id=r["unit_id"],
                provider=r["provider"],
                model=r["model"],
                draft_text=r["draft_text"],
                final_text=r["final_text"],
                quality_flags=r["quality_flags"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
        )

    # we need file_path_map
    cur = conn.execute("SELECT id, relative_path FROM game_files")
    file_path_map = {r["id"]: r["relative_path"] for r in cur.fetchall()}

    activate_lang = getattr(args, "activate_language", False)
    print("Creating patch plan...")
    plan = create_plan(
        install_path,
        "default",
        units,
        records,
        file_path_map,
        include_activation=activate_lang,
    )

    plan_file = Path(args.plan_file)
    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
    print(f"Plan created at {plan_file.absolute()}")
    print(preview_plan(plan))


def cmd_export_csv(args):
    db = get_db(args.workspace)
    from gamelingo.translation.export_import import ExportImportService

    svc = ExportImportService(db)

    statuses = args.status.split(",") if args.status else None
    out_path = Path(args.output)
    count = svc.export_csv(out_path, project_id=args.project_id, statuses=statuses)
    print(f"Exported {count} records to {out_path.absolute()}")


def cmd_import_preview(args):
    db = get_db(args.workspace)
    from gamelingo.translation.export_import import ExportImportService

    svc = ExportImportService(db)

    in_path = Path(args.input)
    try:
        preview = svc.import_csv_preview(in_path)
    except Exception as e:
        print(f"Import preview failed: {e}")
        sys.exit(1)

    print(f"Total Rows: {preview['total_rows']}")
    print(f"Valid Editable: {preview['valid_editable']}")
    print(f"Unchanged: {preview['unchanged']}")
    print(f"Invalid/Errors: {preview['invalid']}")
    print(f"Stale Source Conflicts: {preview['stale_source']}")
    print(f"Duplicate Rows: {preview['duplicate_rows']}")
    print(f"Validation Blocked: {preview['validation_blocked']}")
    print(f"Would Need Review: {preview['would_need_review']}")
    print(f"Approvals Invalidated: {preview['approval_invalidated']}")

    if preview["invalid"] > 0:
        print("\nInvalid Rows Details:")
        for r in preview["rows"]:
            if r["action"] == "error":
                print(f"Row {r['row']} (Unit {r['unit_id']}): {r['reason']}")
        sys.exit(1)


def cmd_import_apply(args):
    db = get_db(args.workspace)
    from gamelingo.translation.export_import import ExportImportService

    svc = ExportImportService(db)

    in_path = Path(args.input)
    if not args.yes:
        print("Use --yes to confirm import.")
        sys.exit(1)

    try:
        count = svc.import_csv_apply(in_path)
        print(f"Successfully imported {count} translations.")
    except Exception as e:
        print(f"Import failed: {e}")
        sys.exit(1)


def cmd_plan_validate(args):
    plan_file = Path(args.plan_file)
    if not plan_file.exists():
        print(f"Plan file {plan_file} not found.")
        sys.exit(1)
    with open(plan_file, "r", encoding="utf-8") as f:
        plan = json.load(f)

    db = get_db(args.workspace)
    conn = db.connect()
    cur = conn.execute("SELECT install_path FROM projects WHERE id = 'default'")
    row = cur.fetchone()
    install_path = Path(row["install_path"])

    try:
        validate_plan(install_path, plan)
        print("Plan is valid and safe to apply.")
    except Exception as e:
        print(f"Plan validation failed: {e}")
        sys.exit(1)


def cmd_plan_show(args):
    plan_file = Path(args.plan_file)
    with open(plan_file, "r", encoding="utf-8") as f:
        plan = json.load(f)
    print(preview_plan(plan))


def cmd_apply(args):
    plan_file = Path(args.plan_file)
    with open(plan_file, "r", encoding="utf-8") as f:
        plan = json.load(f)

    db = get_db(args.workspace)
    conn = db.connect()
    cur = conn.execute("SELECT install_path FROM projects WHERE id = 'default'")
    row = cur.fetchone()
    install_path = Path(row["install_path"])

    backup_root = Path(args.workspace) / "backups"

    execute = args.execute or args.yes
    if not execute:
        print("--- PREVIEW MODE --- (Use --execute --yes to apply)")

    try:
        report = apply_plan(
            install_path, plan, backup_root, execute=execute, overwrite=args.yes
        )
        print(f"Apply status: {report['status']}")
        if execute:
            if report.get("backup_id"):
                print(f"Backup created: {report['backup_id']}")
                print(f"Backup location: {report['backup_dir']}")
            print(
                f"Successfully changed {len(report.get('successfully_changed_files', []))} files."
            )
            if report.get("failed_files"):
                print(f"Failed to change {len(report['failed_files'])} files.")
            if report.get("recovery_status"):
                print(f"Recovery status: {report['recovery_status']}")
    except Exception as e:
        print(f"Apply failed: {e}")
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"GameLingo v{__version__} - Local-first game translation workbench"
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace directory (default: current directory)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Project commands
    p_proj = subparsers.add_parser("project", help="Project management")
    proj_sub = p_proj.add_subparsers(dest="proj_cmd", required=True)

    c_init = proj_sub.add_parser("init", help="Initialize workspace")
    c_init.set_defaults(func=cmd_project_init)

    c_info = proj_sub.add_parser("info", help="Project info")
    c_info.set_defaults(func=cmd_project_info)

    c_verify = proj_sub.add_parser("verify", help="Verify project config")
    c_verify.set_defaults(func=cmd_project_verify)

    # Game commands
    p_game = subparsers.add_parser("game", help="Game discovery")
    game_sub = p_game.add_subparsers(dest="game_cmd", required=True)

    c_detect = game_sub.add_parser("detect", help="Detect game engine")
    c_detect.add_argument("game_path")
    c_detect.set_defaults(func=cmd_game_detect)

    c_inspect = game_sub.add_parser("inspect", help="Inspect game")
    c_inspect.add_argument("game_path")
    c_inspect.set_defaults(func=cmd_game_inspect)

    # Extract
    p_ext = subparsers.add_parser("extract", help="Extract text")
    p_ext.add_argument("game_path")
    p_ext.set_defaults(func=cmd_extract)

    # Translate
    p_trans = subparsers.add_parser("translate", help="Translate texts")
    p_trans.set_defaults(func=cmd_translate)

    # Jobs
    p_jobs = subparsers.add_parser("jobs", help="Job management")
    jobs_sub = p_jobs.add_subparsers(dest="jobs_cmd", required=True)

    c_jl = jobs_sub.add_parser("list", help="List jobs")
    c_jl.set_defaults(func=cmd_jobs_list)

    c_js = jobs_sub.add_parser("show", help="Show job")
    c_js.add_argument("job_id")
    c_js.set_defaults(func=cmd_jobs_show)

    c_jr = jobs_sub.add_parser("resume", help="Resume job")
    c_jr.add_argument("job_id")
    c_jr.set_defaults(func=cmd_jobs_resume)

    # Review
    p_rev = subparsers.add_parser("review", help="Review translated texts")
    rev_sub = p_rev.add_subparsers(dest="rev_cmd", required=True)

    c_rl = rev_sub.add_parser("list", help="List units")
    c_rl.add_argument("--status", help="Filter by status")
    c_rl.set_defaults(func=cmd_review_list)

    c_rs = rev_sub.add_parser("show", help="Show unit")
    c_rs.add_argument("unit_id")
    c_rs.set_defaults(func=cmd_review_show)

    c_re = rev_sub.add_parser("edit", help="Edit unit")
    c_re.add_argument("unit_id")
    c_re.add_argument("text")
    c_re.set_defaults(func=cmd_review_edit)

    c_ra = rev_sub.add_parser("approve", help="Approve unit")
    c_ra.add_argument("unit_id")
    c_ra.set_defaults(func=cmd_review_approve)

    c_rr = rev_sub.add_parser("reject", help="Reject unit")
    c_rr.add_argument("unit_id")
    c_rr.add_argument("--reason", default="")
    c_rr.set_defaults(func=cmd_review_reject)

    # Plan
    p_plan = subparsers.add_parser("plan", help="Patch planning")
    plan_sub = p_plan.add_subparsers(dest="plan_cmd", required=True)

    # Export
    p_exp = subparsers.add_parser("export", help="Export translations")
    exp_sub = p_exp.add_subparsers(dest="exp_cmd", required=True)

    c_ec = exp_sub.add_parser("csv", help="Export to CSV")
    c_ec.add_argument("--output", required=True)
    c_ec.add_argument("--project-id", default="default")
    c_ec.add_argument("--status", help="Comma separated statuses")
    c_ec.set_defaults(func=cmd_export_csv)

    # Import
    p_imp = subparsers.add_parser("import", help="Import translations")
    imp_sub = p_imp.add_subparsers(dest="imp_cmd", required=True)

    c_ip = imp_sub.add_parser("preview", help="Preview import")
    c_ip.add_argument("input", help="CSV file path")
    c_ip.set_defaults(func=cmd_import_preview)

    c_ia = imp_sub.add_parser("apply", help="Apply import")
    c_ia.add_argument("input", help="CSV file path")
    c_ia.add_argument("--yes", action="store_true")
    c_ia.set_defaults(func=cmd_import_apply)

    c_pc = plan_sub.add_parser("create", help="Create patch plan")
    c_pc.add_argument("--plan-file", default="patch_plan.json")
    c_pc.add_argument(
        "--activate-language",
        action="store_true",
        help="Include Ren'Py language activation script (gamelingo_activate.rpy)",
    )
    c_pc.set_defaults(func=cmd_plan_create)

    c_pv = plan_sub.add_parser("validate", help="Validate plan")
    c_pv.add_argument("plan_file")
    c_pv.set_defaults(func=cmd_plan_validate)

    c_ps = plan_sub.add_parser("show", help="Show plan")
    c_ps.add_argument("plan_file")
    c_ps.set_defaults(func=cmd_plan_show)

    # Apply
    p_apply = subparsers.add_parser("apply", help="Apply patch")
    p_apply.add_argument("plan_file")
    p_apply.add_argument(
        "--execute", action="store_true", help="Execute the patch instead of preview"
    )
    p_apply.add_argument(
        "--yes", action="store_true", help="Confirm execution non-interactively"
    )
    p_apply.set_defaults(func=cmd_apply)

    args = parser.parse_args()
    try:
        args.func(args)
    except AttributeError:
        parser.print_help()

    return 0


if __name__ == "__main__":
    sys.exit(main())
