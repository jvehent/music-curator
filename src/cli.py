import argparse
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

from .config import CuratorConfig
from .scanner import MusicScanner
from .organizer.planner import OrganizationPlanner
from .organizer.copier import MusicCopier
from .organizer.manifest import write_manifests

console = Console(force_terminal=False)


def scan_cmd(args):
    source = Path(args.source).resolve()
    if not source.exists():
        console.print(f"[red]Error:[/red] Source directory '{source}' does not exist.")
        sys.exit(1)

    console.print(f"[bold cyan]Scanning directory:[/bold cyan] {source}")
    scanner = MusicScanner(source)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Scanning audio files...", total=None)

        def cb(curr, total, name):
            progress.update(task, total=total, completed=curr, description=f"[cyan]Scanning: {name[:30]}")

        tracks, art_map = scanner.scan_files(progress_cb=cb)

    console.print(f"\n[green][OK] Found {len(tracks)} audio files and {len(art_map)} album artwork folders.[/green]\n")

    # Display preview table
    table = Table(title="Audio Files Sample Preview", show_lines=True)
    table.add_column("Track", justify="center", style="cyan")
    table.add_column("Artist", style="magenta")
    table.add_column("Album", style="yellow")
    table.add_column("Title", style="white")
    table.add_column("Format", justify="center", style="blue")
    table.add_column("Confidence", justify="center")

    for t in tracks[:15]:
        conf_color = "green" if t.confidence == "high" else ("yellow" if t.confidence == "medium" else "red")
        table.add_row(
            str(t.track_number or "-"),
            t.artist,
            t.album,
            t.title,
            t.format,
            f"[{conf_color}]{t.confidence}[/{conf_color}]"
        )

    console.print(table)
    if len(tracks) > 15:
        console.print(f"[dim]... and {len(tracks) - 15} more tracks.[/dim]\n")


def organize_cmd(args):
    source = Path(args.source).resolve()
    dest = Path(args.destination).resolve()

    if not source.exists():
        console.print(f"[red]Error:[/red] Source directory '{source}' does not exist.")
        sys.exit(1)

    console.print(f"[bold green]Starting Music Curator[/bold green]")
    console.print(f"Source:      [cyan]{source}[/cyan]")
    console.print(f"Destination: [magenta]{dest}[/magenta]")
    console.print(f"Dry Run:     {'[yellow]YES (Simulation only)[/yellow]' if args.dry_run else '[bold red]NO (Copying files)[/bold red]'}")

    cfg = CuratorConfig(
        source_dir=source,
        destination_dir=dest,
        dry_run=args.dry_run,
        uconnect_mode=not args.no_uconnect,
        max_component_length=args.max_len,
        artwork_action=args.artwork_action,
        write_tags_to_destination=not args.no_tags,
        copy_album_art=args.copy_art,
    )

    scanner = MusicScanner(source)
    tracks, art_map = scanner.scan_files()
    planner = OrganizationPlanner(cfg)
    plan = planner.create_plan(tracks)

    console.print(f"[green][OK] Plan generated for {len(plan)} tracks.[/green]\n")

    # Table preview
    table = Table(title="Planned Organization (Sample)", show_lines=True)
    table.add_column("Artist", style="magenta")
    table.add_column("Album", style="yellow")
    table.add_column("Filename", style="cyan")
    table.add_column("Status", justify="center")

    for p in plan[:10]:
        status_color = "green" if p.status == "ready" else "yellow"
        table.add_row(
            p.target_artist_dir,
            p.target_album_dir,
            p.target_filename,
            f"[{status_color}]{p.status}[/{status_color}]"
        )
    console.print(table)

    manifest_paths = write_manifests(plan, dest)
    console.print(f"\n[bold]Audit manifest written to:[/bold] {manifest_paths['csv']}")

    if args.dry_run:
        console.print("\n[yellow]Dry run completed! No files were copied.[/yellow]")
        return

    console.print("\n[bold cyan]Executing safe non-destructive copy...[/bold cyan]")
    copier = MusicCopier(cfg)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} ({task.fields[speed]} MB/s)"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Copying...", total=len(plan), speed=0.0)

        def cb(prog):
            progress.update(
                task,
                completed=prog.current_index,
                description=f"[cyan]Copying: {prog.current_file[:25]}",
                speed=prog.speed_mb_s,
            )

        completed = copier.execute_plan(plan, album_art_map=art_map, progress_cb=cb)

    console.print(f"\n[bold green][OK] Done! {len(completed)} files safely copied to {dest}[/bold green]")
    console.print("[dim]Original files in source directory remain untouched.[/dim]\n")


def main():
    parser = argparse.ArgumentParser(description="Harmoniq Music Curator - Clean Audio Organizer")
    subparsers = parser.add_subparsers(dest="command")

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan and inspect directory")
    p_scan.add_argument("source", help="Source music directory")

    # organize
    p_org = subparsers.add_parser("organize", help="Organize music into <artist>/<album>/ structure")
    p_org.add_argument("source", help="Source music directory")
    p_org.add_argument("destination", help="Target output directory")
    p_org.add_argument("--dry-run", action="store_true", help="Simulate without copying files")
    p_org.add_argument("--no-uconnect", action="store_true", help="Disable Uconnect 430N/730N strict rules")
    p_org.add_argument("--max-len", type=int, default=32, help="Max filename/folder character length (default: 32)")
    p_org.add_argument("--artwork-action", choices=["strip", "resize_500", "keep"], default="strip", help="Embedded artwork handling (default: strip)")
    p_org.add_argument("--copy-art", action="store_true", help="Copy folder artwork files (disabled by default for Uconnect)")
    p_org.add_argument("--no-tags", action="store_true", help="Do not write tags to copied files")

    # serve
    p_serve = subparsers.add_parser("serve", help="Launch interactive Web UI")
    p_serve.add_argument("--port", type=int, default=8765, help="Port to run on")

    args = parser.parse_args()
    if args.command == "scan":
        scan_cmd(args)
    elif args.command == "organize":
        organize_cmd(args)
    elif args.command == "serve":
        from .ui.server import start_server
        start_server(port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
