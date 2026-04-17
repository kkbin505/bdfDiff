"""
Diff Engine – Model layer
Computes card-level and text-level differences between two BDF models.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .bdf_parser import BdfCard, BdfModel


# ---------------------------------------------------------------------------
# Result data structures
# ---------------------------------------------------------------------------

@dataclass
class CardDiff:
    """Diff result for a single card."""
    key: str
    keyword: str
    status: str           # "added" | "removed" | "modified" | "unchanged"
    old_card: Optional[BdfCard]
    new_card: Optional[BdfCard]
    # Unified diff lines for individual field changes (only for "modified")
    field_diff: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "keyword": self.keyword,
            "status": self.status,
            "old_card": self.old_card.to_dict() if self.old_card else None,
            "new_card": self.new_card.to_dict() if self.new_card else None,
            "field_diff": self.field_diff,
        }


@dataclass
class DiffResult:
    """Aggregated diff between two BDF models."""
    card_diffs: List[CardDiff] = field(default_factory=list)
    # Unified text diff (list of diff lines)
    text_diff: List[str] = field(default_factory=list)
    # Side-by-side diff data [(left_lineno, left_line, right_lineno, right_line, change_type)]
    side_by_side: List[Tuple] = field(default_factory=list)

    # Summary counts
    added: int = 0
    removed: int = 0
    modified: int = 0
    unchanged: int = 0

    # Keyword-level breakdown  {keyword: {"added": n, "removed": n, "modified": n}}
    keyword_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "card_diffs": [cd.to_dict() for cd in self.card_diffs],
            "text_diff": self.text_diff,
            "side_by_side": [list(row) for row in self.side_by_side],
            "summary": {
                "added": self.added,
                "removed": self.removed,
                "modified": self.modified,
                "unchanged": self.unchanged,
                "total_changes": self.added + self.removed + self.modified,
            },
            "keyword_stats": self.keyword_stats,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class DiffEngine:
    """Computes diffs between BDF models or raw text."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def diff_models(
        self,
        old_model: BdfModel,
        new_model: BdfModel,
        old_text: str = "",
        new_text: str = "",
    ) -> DiffResult:
        """Compute a full diff between two BDF models."""
        result = DiffResult()

        old_cards = old_model.card_by_key()
        new_cards = new_model.card_by_key()

        all_keys = sorted(set(old_cards) | set(new_cards))

        for key in all_keys:
            old_card = old_cards.get(key)
            new_card = new_cards.get(key)
            keyword = (old_card or new_card).keyword  # type: ignore[union-attr]

            if old_card is None:
                status = "added"
            elif new_card is None:
                status = "removed"
            elif old_card.raw_lines == new_card.raw_lines:
                status = "unchanged"
            else:
                status = "modified"

            field_diff: List[str] = []
            if status == "modified" and old_card and new_card:
                field_diff = list(
                    difflib.unified_diff(
                        old_card.raw_lines,
                        new_card.raw_lines,
                        fromfile=f"old/{key}",
                        tofile=f"new/{key}",
                        lineterm="",
                    )
                )

            cd = CardDiff(
                key=key,
                keyword=keyword,
                status=status,
                old_card=old_card,
                new_card=new_card,
                field_diff=field_diff,
            )
            result.card_diffs.append(cd)

            # Update counts
            if status == "added":
                result.added += 1
            elif status == "removed":
                result.removed += 1
            elif status == "modified":
                result.modified += 1
            else:
                result.unchanged += 1

            # Update keyword stats
            if status != "unchanged":
                kw_stat = result.keyword_stats.setdefault(
                    keyword, {"added": 0, "removed": 0, "modified": 0}
                )
                kw_stat[status] = kw_stat.get(status, 0) + 1

        # Text-level diffs
        if old_text or new_text:
            result.text_diff = self._unified_text_diff(old_text, new_text)
            result.side_by_side = self._side_by_side_diff(old_text, new_text)

        return result

    def diff_texts(self, old_text: str, new_text: str) -> DiffResult:
        """Lightweight text-only diff (no BDF parsing required)."""
        result = DiffResult()
        result.text_diff = self._unified_text_diff(old_text, new_text)
        result.side_by_side = self._side_by_side_diff(old_text, new_text)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _unified_text_diff(self, old_text: str, new_text: str) -> List[str]:
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        return list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile="old.bdf",
                tofile="new.bdf",
            )
        )

    def _side_by_side_diff(
        self, old_text: str, new_text: str
    ) -> List[Tuple]:
        """Build a side-by-side diff as a list of row tuples.

        Each tuple: (left_lineno, left_line, right_lineno, right_line, change_type)
        change_type: "equal" | "replace" | "insert" | "delete"
        """
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
        rows: List[Tuple] = []

        left_no = 0
        right_no = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    rows.append(
                        (left_no + 1, old_lines[i1 + k],
                         right_no + 1, new_lines[j1 + k],
                         "equal")
                    )
                    left_no += 1
                    right_no += 1
            elif tag == "replace":
                # Pair up old/new lines
                old_chunk = old_lines[i1:i2]
                new_chunk = new_lines[j1:j2]
                for k in range(max(len(old_chunk), len(new_chunk))):
                    left_line = old_chunk[k] if k < len(old_chunk) else ""
                    right_line = new_chunk[k] if k < len(new_chunk) else ""
                    l_no = (left_no + 1) if k < len(old_chunk) else None
                    r_no = (right_no + 1) if k < len(new_chunk) else None
                    rows.append((l_no, left_line, r_no, right_line, "replace"))
                    if k < len(old_chunk):
                        left_no += 1
                    if k < len(new_chunk):
                        right_no += 1
            elif tag == "delete":
                for k in range(i2 - i1):
                    rows.append(
                        (left_no + 1, old_lines[i1 + k], None, "", "delete")
                    )
                    left_no += 1
            elif tag == "insert":
                for k in range(j2 - j1):
                    rows.append(
                        (None, "", right_no + 1, new_lines[j1 + k], "insert")
                    )
                    right_no += 1

        return rows
