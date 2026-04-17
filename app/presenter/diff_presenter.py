"""
Diff Presenter – Presenter layer
Orchestrates Model operations and prepares data for the View.
"""

from __future__ import annotations

import os
import tempfile
from typing import Dict, List, Optional, Tuple

from app.model.bdf_parser import BdfParser
from app.model.diff_engine import DiffEngine, DiffResult
from app.model.git_manager import GitManager


class DiffPresenter:
    """Central presenter: coordinates parsing, diffing, and data shaping."""

    def __init__(self, repo_path: str = ".") -> None:
        self.repo_path = os.path.abspath(repo_path)
        self._parser = BdfParser()
        self._engine = DiffEngine()
        self._git = GitManager(repo_path)

    # ------------------------------------------------------------------
    # File-based diff
    # ------------------------------------------------------------------

    def diff_files(
        self,
        old_path: str,
        new_path: str,
    ) -> dict:
        """Diff two BDF files on disk and return a view-ready dict."""
        old_text = self._read_file(old_path)
        new_text = self._read_file(new_path)
        return self._compute_diff(old_text, new_text, old_path, new_path)

    def diff_texts(self, old_text: str, new_text: str) -> dict:
        """Diff two BDF text strings and return a view-ready dict."""
        return self._compute_diff(old_text, new_text, "old.bdf", "new.bdf")

    # ------------------------------------------------------------------
    # Git-based diff
    # ------------------------------------------------------------------

    def diff_commits(
        self,
        filepath: str,
        old_sha: str,
        new_sha: str,
    ) -> dict:
        """Diff *filepath* between two git commits."""
        old_text = self._git.get_file_at_commit(filepath, old_sha) or ""
        new_text = self._git.get_file_at_commit(filepath, new_sha) or ""
        return self._compute_diff(
            old_text, new_text,
            f"{filepath}@{old_sha[:7]}",
            f"{filepath}@{new_sha[:7]}",
        )

    def diff_commit_vs_working(
        self,
        filepath: str,
        sha: str,
    ) -> dict:
        """Diff *filepath* between a git commit and the working-tree version."""
        old_text = self._git.get_file_at_commit(filepath, sha) or ""
        new_text = self._read_file(filepath)
        return self._compute_diff(
            old_text, new_text,
            f"{filepath}@{sha[:7]}",
            f"{filepath} (working tree)",
        )

    # ------------------------------------------------------------------
    # Git repository information
    # ------------------------------------------------------------------

    def get_repo_info(self) -> dict:
        return {
            "is_git_repo": self._git.is_git_repo,
            "repo_name": self._git.get_repo_name(),
            "current_branch": self._git.get_current_branch(),
            "bdf_files": self._git.get_tracked_bdf_files(),
        }

    def get_commits(
        self,
        filepath: Optional[str] = None,
        max_count: int = 50,
    ) -> List[dict]:
        commits = self._git.list_commits(filepath=filepath, max_count=max_count)
        return [c.to_dict() for c in commits]

    # ------------------------------------------------------------------
    # BDF file summary
    # ------------------------------------------------------------------

    def get_file_summary(self, filepath: str) -> dict:
        """Return a structured summary of a BDF file."""
        text = self._read_file(filepath)
        if not text:
            return {"error": f"Cannot read file: {filepath}"}
        model = self._parser.parse_text(text)
        return {
            "filepath": filepath,
            "summary": model.summary(),
            "keywords": model.keywords(),
            "total_cards": len(model.cards),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_diff(
        self,
        old_text: str,
        new_text: str,
        old_label: str,
        new_label: str,
    ) -> dict:
        old_model = self._parser.parse_text(old_text)
        new_model = self._parser.parse_text(new_text)
        result: DiffResult = self._engine.diff_models(
            old_model, new_model, old_text, new_text
        )

        # Keyword filter list for the UI
        changed_keywords = sorted(result.keyword_stats.keys())
        all_keywords = sorted(
            set(old_model.keywords()) | set(new_model.keywords())
        )

        # Group card diffs by keyword for templating convenience
        diffs_by_keyword: Dict[str, List[dict]] = {}
        for cd in result.card_diffs:
            diffs_by_keyword.setdefault(cd.keyword, []).append(cd.to_dict())

        return {
            "old_label": old_label,
            "new_label": new_label,
            "summary": result.to_dict()["summary"],
            "keyword_stats": result.keyword_stats,
            "all_keywords": all_keywords,
            "changed_keywords": changed_keywords,
            "card_diffs": [cd.to_dict() for cd in result.card_diffs],
            "diffs_by_keyword": diffs_by_keyword,
            "text_diff": result.text_diff,
            "side_by_side": result.side_by_side,
            "old_summary": old_model.summary(),
            "new_summary": new_model.summary(),
        }

    @staticmethod
    def _read_file(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return ""
