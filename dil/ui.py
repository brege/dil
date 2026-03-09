from __future__ import annotations

from dataclasses import dataclass

from rich.box import Box
from rich.console import Console
from rich.table import Table


TOKEI = Box("    \n    \n ━━ \n    \n ── \n ── \n    \n ━━ \n")


@dataclass(frozen=True)
class LitterRow:
    type: str
    rule: str
    matches: int
    size: int


@dataclass(frozen=True)
class OverviewRow:
    type: str
    matches: int
    size: int


@dataclass(frozen=True)
class ScanRow:
    type: str
    rule: str
    path: str


def size(value: int) -> str:
    if value < 1000:
        return f"{value} B"
    current = float(value)
    for unit in ("KB", "MB", "GB", "TB"):
        current /= 1000.0
        if current < 1000.0:
            return f"{current:.1f} {unit}"
    return f"{current:.1f} PB"


def overview(console: Console, root: str, rows: list[OverviewRow]) -> None:
    table = Table(box=TOKEI, pad_edge=False)
    table.add_column("Type")
    table.add_column("Matches", justify="right")
    table.add_column("Reclaimable", justify="right")
    for row in rows:
        table.add_row(row.type, f"{row.matches:,}", size(row.size))
    console.print(root)
    console.print(table)


def litter(console: Console, rows: list[LitterRow]) -> None:
    table = Table(box=TOKEI, show_footer=True, pad_edge=False)
    table.add_column("Type", footer="Total")
    table.add_column("Rule")
    table.add_column("Matches", justify="right")
    table.add_column("Size", justify="right")

    total_matches = 0
    total_size = 0
    current = ""
    for index, row in enumerate(rows):
        label = row.type if row.type != current else ""
        table.add_row(label, row.rule, f"{row.matches:,}", size(row.size))
        total_matches += row.matches
        total_size += row.size
        current = row.type
        if index + 1 < len(rows) and rows[index + 1].type != row.type:
            table.add_section()

    table.columns[2].footer = f"{total_matches:,}"
    table.columns[3].footer = size(total_size)
    console.print(table)


def scan(console: Console, rows: list[ScanRow]) -> None:
    table = Table(box=TOKEI, pad_edge=False)
    table.add_column("Type")
    table.add_column("Rule")
    table.add_column("Path", overflow="ellipsis")

    current = ""
    for index, row in enumerate(rows):
        label = row.type if row.type != current else ""
        table.add_row(label, row.rule, row.path)
        current = row.type
        if index + 1 < len(rows) and rows[index + 1].type != row.type:
            table.add_section()

    console.print(table)
