import argparse
import sys

def main():
    parser = argparse.ArgumentParser(
        prog="eidolon",
        description="EIDOLON: A Linux config impact analyzer. See the consequences before you commit the change."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # edit command
    parser_edit = subparsers.add_parser("edit", help="Edit a config file with impact analysis")
    parser_edit.add_argument("path", help="Path to the config file")
    parser_edit.add_argument("--show-diff", action="store_true", help="Show raw unified diff")
    parser_edit.add_argument("--debug", action="store_true", help="Show debug information")
    parser_edit.add_argument("--no-ai", action="store_true", help="Skip AI explanation")

    # analyze command
    parser_analyze = subparsers.add_parser("analyze", help="Analyze a config file without editing")
    parser_analyze.add_argument("path", help="Path to the config file")

    # undo command
    parser_undo = subparsers.add_parser("undo", help="Restore the latest backup of a config file")
    parser_undo.add_argument("path", help="Path to the config file")

    # doctor command
    parser_doctor = subparsers.add_parser("doctor", help="Check system dependencies and configuration")
    parser_doctor.add_argument("--test-ai", action="store_true", help="Perform a test call to the AI")

    args = parser.parse_args()

    if args.command == "edit":
        from eidolon.core import handle_edit
        handle_edit(args.path, show_diff=args.show_diff, debug=args.debug, no_ai=args.no_ai)
    elif args.command == "analyze":
        print(f"Analyze command called on {args.path}")
    elif args.command == "undo":
        from eidolon.core import handle_undo
        handle_undo(args.path)
    elif args.command == "doctor":
        from eidolon.core import handle_doctor
        handle_doctor(test_ai=args.test_ai)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
