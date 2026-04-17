"""
BDF Parser – Model layer
Parses Nastran BDF files into structured card objects.

Supported formats:
  - Free-field (comma-separated)
  - Small-field (8-character fixed-width columns)
  - Large-field (16-character columns, continuation with *)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BdfCard:
    """Represents a single Nastran bulk-data card."""
    keyword: str
    fields: List[str]
    raw_lines: List[str]
    line_number: int          # 1-based line number of the first line in the file

    @property
    def card_id(self) -> Optional[str]:
        """Return the primary ID field (field index 1) if present."""
        return self.fields[1].strip() if len(self.fields) > 1 else None

    @property
    def key(self) -> str:
        """Unique key: 'KEYWORD/ID' (or just 'KEYWORD' if no ID)."""
        cid = self.card_id
        return f"{self.keyword}/{cid}" if cid else self.keyword

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "fields": self.fields,
            "raw_lines": self.raw_lines,
            "line_number": self.line_number,
            "card_id": self.card_id,
            "key": self.key,
        }


@dataclass
class BdfModel:
    """Parsed representation of a BDF file."""
    cards: List[BdfCard] = field(default_factory=list)
    executive_lines: List[str] = field(default_factory=list)
    case_control_lines: List[str] = field(default_factory=list)
    unsupported_lines: List[str] = field(default_factory=list)

    # -----------------------------------------------------------------------
    # Convenience accessors
    # -----------------------------------------------------------------------
    def cards_by_keyword(self) -> Dict[str, List[BdfCard]]:
        result: Dict[str, List[BdfCard]] = {}
        for card in self.cards:
            result.setdefault(card.keyword, []).append(card)
        return result

    def card_by_key(self) -> Dict[str, BdfCard]:
        return {c.key: c for c in self.cards}

    def keywords(self) -> List[str]:
        seen = set()
        out = []
        for c in self.cards:
            if c.keyword not in seen:
                seen.add(c.keyword)
                out.append(c.keyword)
        return out

    def summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for card in self.cards:
            summary[card.keyword] = summary.get(card.keyword, 0) + 1
        return summary


# ---------------------------------------------------------------------------
# Parser implementation
# ---------------------------------------------------------------------------

class BdfParser:
    """Stateless BDF parser.  Call parse_file() or parse_text()."""

    # Sections in a BDF file
    _SECTION_EXECUTIVE = "executive"
    _SECTION_CASE = "case_control"
    _SECTION_BULK = "bulk"

    def parse_file(self, filepath: str) -> BdfModel:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        return self.parse_text(text)

    def parse_text(self, text: str) -> BdfModel:
        lines = text.splitlines()
        return self._parse_lines(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_lines(self, lines: List[str]) -> BdfModel:
        model = BdfModel()
        section = self._SECTION_EXECUTIVE

        # Collect raw physical lines for the bulk-data section, tracking
        # the 1-based line number in the original file.
        bulk_lines: List[tuple[int, str]] = []  # (1-based lineno, stripped text)

        for lineno, raw in enumerate(lines, start=1):
            stripped = raw.rstrip()

            # Detect section separators
            upper = stripped.upper().strip()
            if upper.startswith("CEND"):
                section = self._SECTION_CASE
                model.executive_lines.append(stripped)
                continue
            if upper.startswith("BEGIN BULK") or upper == "BEGIN":
                section = self._SECTION_BULK
                continue
            if upper.startswith("ENDDATA"):
                break

            if section == self._SECTION_EXECUTIVE:
                model.executive_lines.append(stripped)
            elif section == self._SECTION_CASE:
                model.case_control_lines.append(stripped)
            else:
                bulk_lines.append((lineno, stripped))

        # If no sections found at all, treat everything as bulk data
        if not bulk_lines and section == self._SECTION_EXECUTIVE:
            bulk_lines = [(i + 1, l.rstrip()) for i, l in enumerate(lines)]

        self._parse_bulk(bulk_lines, model)
        return model

    def _parse_bulk(
        self,
        bulk_lines: List[tuple[int, str]],
        model: BdfModel,
    ) -> None:
        """Group physical lines into logical cards and parse each."""
        # First pass: group continuation lines together.
        # A continuation line starts with '+' or '*' in column 0 (fixed-field)
        # or with a comma at the beginning (free-field continuation after ,+...).
        groups: List[List[tuple[int, str]]] = []
        current_group: List[tuple[int, str]] = []

        for lineno, line in bulk_lines:
            if not line or line.startswith("$"):
                # Comment or blank – flush current group
                if current_group:
                    groups.append(current_group)
                    current_group = []
                continue

            # Continuation line detection
            if line and line[0] in ("+", "*"):
                current_group.append((lineno, line))
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [(lineno, line)]

        if current_group:
            groups.append(current_group)

        for group in groups:
            card = self._parse_card_group(group)
            if card:
                model.cards.append(card)
            else:
                for _, line in group:
                    model.unsupported_lines.append(line)

    def _parse_card_group(
        self, group: List[tuple[int, str]]
    ) -> Optional[BdfCard]:
        """Parse a logical card (one or more physical lines)."""
        if not group:
            return None

        first_lineno, first_line = group[0]
        raw_lines = [line for _, line in group]

        # Detect format from first line
        if "," in first_line:
            fields = self._parse_free_field(group)
        elif first_line.startswith("*"):
            fields = self._parse_large_field(group)
        else:
            fields = self._parse_small_field(group)

        if not fields:
            return None

        keyword = fields[0].strip().upper().rstrip("*")
        if not keyword:
            return None

        return BdfCard(
            keyword=keyword,
            fields=fields,
            raw_lines=raw_lines,
            line_number=first_lineno,
        )

    # ------------------------------------------------------------------
    # Format parsers
    # ------------------------------------------------------------------

    def _parse_small_field(self, group: List[tuple[int, str]]) -> List[str]:
        """8-character small-field format."""
        fields: List[str] = []
        for idx, (_, line) in enumerate(group):
            # Pad to at least 80 chars
            padded = line.ljust(80)
            if idx == 0:
                # Columns 1-8: keyword; 9-16, 17-24, …, 73-80: data; 73-80: continuation
                fields.append(padded[0:8])
                for col in range(8, 72, 8):
                    fields.append(padded[col : col + 8])
            else:
                # Continuation: column 1 is '+' or '*' marker, col 9 onwards are data
                fields.append(padded[0:8])  # continuation marker
                for col in range(8, 72, 8):
                    fields.append(padded[col : col + 8])
        return fields

    def _parse_large_field(self, group: List[tuple[int, str]]) -> List[str]:
        """16-character large-field format (lines starting with *)."""
        fields: List[str] = []
        for idx, (_, line) in enumerate(group):
            padded = line.ljust(80)
            if idx == 0:
                fields.append(padded[0:8])   # keyword (with *)
                for col in range(8, 72, 16):
                    fields.append(padded[col : col + 16])
            else:
                fields.append(padded[0:8])
                for col in range(8, 72, 16):
                    fields.append(padded[col : col + 16])
        return fields

    def _parse_free_field(self, group: List[tuple[int, str]]) -> List[str]:
        """Comma-separated free-field format."""
        full = " ".join(line for _, line in group)
        # Remove trailing continuation markers like +abc
        parts = re.split(r",", full)
        # Strip and return
        return [p.strip() for p in parts]
