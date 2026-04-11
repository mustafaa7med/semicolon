"""
SemiColon CLI

Usage
-----
    semicolon <file.sql>           Format a single SQL file in-place.
    semicolon .                    Format every .sql file in the current directory.
    semicolon <file.sql> --check   Exit 1 if the file needs formatting (CI mode).
    semicolon . --check            CI check for all .sql files in the directory.
"""

from __future__ import annotations
import sys
from pathlib import Path
import click
from .formatter import format_sql

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _format_file(path: Path, check: bool) -> bool:
    """
    Format a single SQL file.

    Returns True if the file was (or would be) changed.
    In --check mode, does NOT write to disk.
    """
    original = _read(path)
    formatted = format_sql(original)

    changed = formatted != original

    if check:
        if changed:
            click.echo(
                click.style("✗ Would reformat: ", fg="red") + str(path)
            )
        else:
            click.echo(
                click.style("✓ Already formatted: ", fg="green") + str(path)
            )
        return changed

    if changed:
        _write(path, formatted)
        click.echo(click.style("Reformatted: ", fg="yellow") + str(path))
    else:
        click.echo(click.style("Unchanged:   ", fg="cyan") + str(path))

    return changed


@click.command(
    name="semicolon",
    help=(
        "SemiColon\n\n"
        "Pass a FILE path to format a single file, or '.' to format all "
        ".sql files in the current directory.\n\n"
        "Use --check for CI/CD: exits with code 1 if any file needs "
        "reformatting (no files are written)."
    ),
)
@click.argument("target", metavar="FILE_OR_DOT")
@click.option(
    "--check",
    is_flag=True,
    default=False,
    help="Check mode: exit 1 if formatting is needed without writing files.",
)
@click.version_option(package_name="semicolonfmt")
def main(target: str, check: bool) -> None:
    target_path = Path(target)

    if target == ".":
        sql_files = sorted(Path(".").rglob("*.sql"))
        if not sql_files:
            click.echo("No .sql files found in the current directory.")
            return
    elif target_path.is_file():
        if target_path.suffix.lower() != ".sql":
            click.echo(
                click.style("Warning: ", fg="yellow")
                + f"'{target}' does not have a .sql extension. Formatting anyway."
            )
        sql_files = [target_path]
    else:
        click.echo(
            click.style("Error: ", fg="red")
            + f"'{target}' is not a file or '.'.",
            err=True,
        )
        sys.exit(2)

    any_changed = False
    errors: list[str] = []

    for path in sql_files:
        try:
            changed = _format_file(path, check=check)
            if changed:
                any_changed = True
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}: {exc}")
            click.echo(
                click.style("Error formatting ", fg="red") + f"{path}: {exc}",
                err=True,
            )

    if errors:
        sys.exit(2)

    if check and any_changed:
        click.echo(
            "\n"
            + click.style(
                "Some files require reformatting. Run `semicolon` without "
                "--check to fix them.",
                fg="red",
            )
        )
        sys.exit(1)
