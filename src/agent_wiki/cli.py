"""CLI entry point for agent-wiki."""

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent-wiki",
        description="Wiki management tools for Obsidian-style markdown wikis",
    )
    parser.add_argument(
        "--root", type=Path, help="Wiki root directory (required for most commands)"
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output", help="JSON output"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialize a new Agent Wiki project")
    p_init.add_argument("path", help="Directory to create the project in")
    p_init.add_argument("--name", help="Project name (defaults to directory name)")

    # lint
    p_lint = sub.add_parser("lint", help="Check wiki health")
    p_lint.add_argument(
        "--severity",
        choices=["error", "warning", "info"],
        help="Filter by minimum severity",
    )

    # move
    p_move = sub.add_parser("move", help="Move/rename a file and update all links")
    p_move.add_argument("old_path", help="Current path (relative to root)")
    p_move.add_argument("new_path", help="New path (relative to root)")

    # merge
    p_merge = sub.add_parser("merge", help="Merge source into target")
    p_merge.add_argument("source", help="File to merge from (will be deleted)")
    p_merge.add_argument("target", help="File to merge into")

    # rename
    p_rename = sub.add_parser("rename", help="Rename a page by name")
    p_rename.add_argument("old_name")
    p_rename.add_argument("new_name")

    # convert
    p_convert = sub.add_parser("convert", help="Convert documents to markdown")
    convert_sub = p_convert.add_subparsers(dest="format", required=True)

    p_pdf = convert_sub.add_parser("pdf", help="Convert PDF to markdown")
    p_pdf.add_argument("input", help="Input PDF path")
    p_pdf.add_argument("output", help="Output markdown path")
    p_pdf.add_argument("--max-dpi", type=int, default=150)
    p_pdf.add_argument("--no-images", action="store_true")

    for fmt in ("docx", "pptx", "xlsx"):
        p_fmt = convert_sub.add_parser(fmt, help=f"Convert {fmt} (not yet implemented)")
        p_fmt.add_argument("input")
        p_fmt.add_argument("output")

    # backlinks
    p_bl = sub.add_parser("backlinks", help="Find pages linking to a page")
    p_bl.add_argument("page_name")

    # stats
    sub.add_parser("stats", help="Show wiki statistics")

    # find-references
    p_refs = sub.add_parser("find-references", help="Search for a term")
    p_refs.add_argument("term")

    # update-index
    sub.add_parser("update-index", help="Auto-generate index.md from topic structure")

    # log
    p_log = sub.add_parser("log", help="Append an entry to log.md")
    p_log.add_argument("action", help="Action type (ingest, query, lint, etc.)")
    p_log.add_argument("description", help="Short description")
    p_log.add_argument("--details", default="", help="Multi-line details")

    # sources-status
    p_status = sub.add_parser("sources-status", help="Auto-generate sources-status.md")
    p_status.add_argument("--raw-dir", help="Raw files directory")
    p_status.add_argument("--kanban-dir", help="Kanban directory")

    # kanban
    p_kanban = sub.add_parser("kanban", help="Kanban pipeline operations")
    kanban_sub = p_kanban.add_subparsers(dest="kanban_command", required=True)

    p_kprocess = kanban_sub.add_parser(
        "process", help="Scan, convert, and create task cards"
    )
    p_kprocess.add_argument("input_dir", help="Directory to scan (e.g. raw/)")
    p_kprocess.add_argument("--output-dir", help="Converted output directory")
    p_kprocess.add_argument("--completed-dir", default="./completed")
    p_kprocess.add_argument("--kanban-dir", help="Backlog directory for cards")
    p_kprocess.add_argument("--max-dpi", type=int, default=150)

    kanban_sub.add_parser("status", help="Show card counts per column")

    p_klist = kanban_sub.add_parser("list", help="List task cards")
    p_klist.add_argument(
        "--column", choices=["backlog", "processing", "review", "done"]
    )
    p_klist.add_argument("--agent", help="Filter by agent type")

    p_krecover = kanban_sub.add_parser("recover", help="Recover stale processing cards")
    p_krecover.add_argument(
        "--max-age", type=int, default=30, help="Minutes before stale"
    )

    args = parser.parse_args(argv)

    # init doesn't need --root
    if args.command == "init":
        from agent_wiki.init_project import init_project

        root = init_project(args.path, name=args.name)
        print(f"Initialized Agent Wiki project at: {root}")
        return 0

    # All other commands require --root
    if not args.root:
        parser.error("--root is required for this command")

    from agent_wiki import WikiRoot

    wiki = WikiRoot(args.root)

    if args.command == "lint":
        issues = wiki.lint()
        if args.severity:
            sev_order = {"error": 0, "warning": 1, "info": 2}
            min_sev = sev_order[args.severity]
            issues = [i for i in issues if sev_order[i.severity.value] <= min_sev]

        if args.json_output:
            print(json.dumps([i.to_dict() for i in issues], indent=2))
        else:
            if not issues:
                print("No issues found.")
            else:
                for issue in issues:
                    rel = (
                        issue.file.relative_to(wiki.root)
                        if wiki.root in issue.file.parents
                        else issue.file
                    )
                    print(f"[{issue.severity.value}] {issue.kind.value}: {rel}")
                    print(f"  {issue.message}")
                    if issue.suggestion:
                        print(f"  → {issue.suggestion}")
                print(f"\nTotal: {len(issues)} issues")
        return 1 if issues else 0

    elif args.command == "move":
        modified = wiki.move(args.old_path, args.new_path)
        if args.json_output:
            print(json.dumps([str(p) for p in modified]))
        else:
            print(f"Moved and updated {len(modified)} files:")
            for p in modified:
                print(f"  {p.relative_to(wiki.root)}")

    elif args.command == "merge":
        modified = wiki.merge(args.source, args.target)
        if args.json_output:
            print(json.dumps([str(p) for p in modified]))
        else:
            print(f"Merged and updated {len(modified)} files:")
            for p in modified:
                print(f"  {p.relative_to(wiki.root)}")

    elif args.command == "rename":
        modified = wiki.rename(args.old_name, args.new_name)
        if args.json_output:
            print(json.dumps([str(p) for p in modified]))
        else:
            print(f"Renamed and updated {len(modified)} files:")
            for p in modified:
                print(f"  {p.relative_to(wiki.root)}")

    elif args.command == "convert":
        if args.format == "pdf":
            out = wiki.convert_pdf(
                args.input,
                args.output,
                max_dpi=args.max_dpi,
                extract_images=not args.no_images,
            )
            print(f"Converted: {out}")
        else:
            print(f"Format '{args.format}' is not yet implemented.", file=sys.stderr)
            return 2

    elif args.command == "backlinks":
        pages = wiki.backlinks(args.page_name)
        if args.json_output:
            print(json.dumps([str(p.relative_to(wiki.root)) for p in pages]))
        else:
            if not pages:
                print(f"No pages link to '{args.page_name}'")
            else:
                print(f"Pages linking to '{args.page_name}':")
                for p in pages:
                    print(f"  {p.relative_to(wiki.root)}")

    elif args.command == "stats":
        s = wiki.stats()
        if args.json_output:
            print(json.dumps(s.to_dict(), indent=2))
        else:
            print(f"Total pages:    {s.total_pages}")
            print(f"  Topics:       {s.topic_pages}")
            print(f"  Sources:      {s.source_pages}")
            print(f"Total links:    {s.total_links} ({s.unique_links} unique)")
            print(f"Orphan pages:   {s.orphan_count}")
            print(f"Broken links:   {s.broken_link_count}")

    elif args.command == "find-references":
        refs = wiki.find_references(args.term)
        if args.json_output:
            print(
                json.dumps(
                    {str(k.relative_to(wiki.root)): v for k, v in refs.items()},
                    indent=2,
                )
            )
        else:
            if not refs:
                print(f"No references to '{args.term}' found")
            else:
                print(f"References to '{args.term}':")
                for p, count in refs.items():
                    print(f"  {count:3d}x  {p.relative_to(wiki.root)}")

    elif args.command == "update-index":
        path = wiki.update_index()
        print(f"Updated: {path.relative_to(wiki.root)}")

    elif args.command == "log":
        path = wiki.append_log(args.action, args.description, args.details)
        print(f"Appended to: {path.relative_to(wiki.root)}")

    elif args.command == "sources-status":
        raw = Path(args.raw_dir) if args.raw_dir else None
        kb = Path(args.kanban_dir) if args.kanban_dir else None
        path = wiki.generate_sources_status(raw_dir=raw, kanban_dir=kb)
        print(f"Generated: {path.relative_to(wiki.root)}")

    elif args.command == "kanban":
        from agent_wiki import kanban as _kanban

        kanban_dir = wiki.root.parent / "kanban"

        if args.kanban_command == "process":
            cards = wiki.kanban_process(
                input_dir=args.input_dir,
                output_dir=args.output_dir,
                completed_dir=args.completed_dir,
                kanban_dir=args.kanban_dir,
                max_dpi=args.max_dpi,
            )
            if args.json_output:
                print(json.dumps([str(c) for c in cards]))
            else:
                if not cards:
                    print("No new files to process.")
                else:
                    print(f"Processed {len(cards)} files:")
                    for c in cards:
                        print(f"  {c.name}")

        elif args.kanban_command == "status":
            counts = wiki.kanban_status()
            if args.json_output:
                print(json.dumps(counts))
            else:
                total = sum(counts.values())
                print(f"Kanban: {total} cards")
                for col, n in counts.items():
                    print(f"  {col:12s}  {n}")

        elif args.kanban_command == "list":
            cards = wiki.kanban_list(column=args.column, agent=args.agent)
            if args.json_output:
                print(json.dumps(cards, indent=2, default=str))
            else:
                if not cards:
                    print("No cards found.")
                else:
                    for c in cards:
                        agent = c.get("agent", "?")
                        col = c.get("column", "?")
                        name = Path(c["path"]).stem
                        print(f"  [{col}] {name}  (agent: {agent})")

        elif args.kanban_command == "recover":
            recovered = _kanban.recover_stale(
                kanban_dir / "processing",
                kanban_dir / "backlog",
                max_age_minutes=args.max_age,
            )
            if args.json_output:
                print(json.dumps([str(p) for p in recovered]))
            else:
                if not recovered:
                    print("No stale cards to recover.")
                else:
                    print(f"Recovered {len(recovered)} stale cards:")
                    for p in recovered:
                        print(f"  {p.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
