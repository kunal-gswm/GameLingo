import argparse
import json
import sys
from pathlib import Path

from gamelingo import __version__
from gamelingo.storage.database import Database
from gamelingo.translation.review import ReviewService


def _get_db():
    # Very basic default for CLI test purposes
    db_path = Path("gamelingo.db")
    db = Database(db_path)
    db.migrate()
    return db


def cmd_list(args):
    service = ReviewService(_get_db())
    statuses = args.status.split(",") if args.status else None
    units = service.list_units_for_review(args.project, statuses)

    print(f"Found {len(units)} units:")
    for u in units:
        print(
            f"[{u['status']}] ID: {u['id']} | Source: {u['source_text'][:30]} | Target: {(u.get('translated_text') or '')[:30]}"
        )


def cmd_show(args):
    service = ReviewService(_get_db())
    unit = service.get_unit(args.unit_id)
    if not unit:
        print(f"Error: Unit {args.unit_id} not found.")
        sys.exit(1)

    print(f"Unit ID: {unit['id']}")
    print(f"Status:  {unit['status']}")
    print(f"Source:  {unit['source_text']}")
    print(f"Context: {unit['context']}")
    print(f"Target:  {unit.get('translated_text', '')}")
    if unit.get("quality_flags"):
        try:
            flags = json.loads(unit["quality_flags"])
            if flags:
                print("Validation Issues:")
                for f in flags:
                    print(f" - [{f['severity'].upper()}] {f['code']}: {f['message']}")
        except Exception:
            pass


def cmd_edit(args):
    service = ReviewService(_get_db())
    try:
        service.update_translation(args.unit_id, args.text)
        print(f"Updated unit {args.unit_id}. Status re-evaluated.")
        cmd_show(args)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_approve(args):
    service = ReviewService(_get_db())
    try:
        service.approve(args.unit_id)
        print(f"Approved unit {args.unit_id}.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_reject(args):
    service = ReviewService(_get_db())
    try:
        service.reject(args.unit_id, args.reason)
        print(f"Rejected unit {args.unit_id}.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"GameLingo v{__version__} - Local-first game translation workbench"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Review commands
    p_review = subparsers.add_parser("review", help="Review translated texts")
    r_sub = p_review.add_subparsers(dest="review_cmd")

    p_list = r_sub.add_parser("list", help="List units for review")
    p_list.add_argument("--project", help="Filter by project ID")
    p_list.add_argument(
        "--status",
        help="Filter by status (comma-separated, e.g., 'needs_review,draft')",
    )
    p_list.set_defaults(func=cmd_list)

    p_show = r_sub.add_parser("show", help="Show full details of a unit")
    p_show.add_argument("unit_id", help="The ID of the translation unit")
    p_show.set_defaults(func=cmd_show)

    p_edit = r_sub.add_parser("edit", help="Edit the translation text manually")
    p_edit.add_argument("unit_id", help="The ID of the translation unit")
    p_edit.add_argument("text", help="The new translated text")
    p_edit.set_defaults(func=cmd_edit)

    p_approve = r_sub.add_parser("approve", help="Approve a valid translation")
    p_approve.add_argument("unit_id", help="The ID of the translation unit")
    p_approve.set_defaults(func=cmd_approve)

    p_reject = r_sub.add_parser("reject", help="Reject a translation")
    p_reject.add_argument("unit_id", help="The ID of the translation unit")
    p_reject.add_argument("--reason", default="", help="Optional reason for rejection")
    p_reject.set_defaults(func=cmd_reject)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        # Default behavior if no subcommand
        print(f"GameLingo v{__version__} - Local-first game translation workbench")
        print(
            "Project foundation successfully established. Use --help to see available commands."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
