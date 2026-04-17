"""
Git Manager – Model layer
Wraps GitPython to provide version-control operations on a BDF repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import git  # type: ignore
    _GIT_AVAILABLE = True
except ImportError:
    _GIT_AVAILABLE = False


@dataclass
class CommitInfo:
    """Lightweight summary of a git commit."""
    sha: str
    short_sha: str
    message: str
    author: str
    date: str
    files_changed: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "sha": self.sha,
            "short_sha": self.short_sha,
            "message": self.message,
            "author": self.author,
            "date": self.date,
            "files_changed": self.files_changed,
        }


class GitManager:
    """Provides git operations for BDF file management."""

    def __init__(self, repo_path: str) -> None:
        self.repo_path = os.path.abspath(repo_path)
        self._repo: Optional[object] = None

        if not _GIT_AVAILABLE:
            return

        try:
            self._repo = git.Repo(self.repo_path, search_parent_directories=True)
        except Exception:
            self._repo = None

    @property
    def is_git_repo(self) -> bool:
        return self._repo is not None

    # ------------------------------------------------------------------
    # Commit listing
    # ------------------------------------------------------------------

    def list_commits(
        self,
        filepath: Optional[str] = None,
        max_count: int = 50,
    ) -> List[CommitInfo]:
        """Return a list of recent commits, optionally filtered to a file path."""
        if not self.is_git_repo:
            return []

        kwargs: dict = {"max_count": max_count}
        if filepath:
            kwargs["paths"] = os.path.relpath(filepath, self.repo_path)

        commits = []
        for commit in self._repo.iter_commits(**kwargs):  # type: ignore[union-attr]
            changed_files = []
            try:
                if commit.parents:
                    diff = commit.parents[0].diff(commit)
                    changed_files = [d.b_path or d.a_path for d in diff]
            except Exception:
                pass

            commits.append(
                CommitInfo(
                    sha=commit.hexsha,
                    short_sha=commit.hexsha[:7],
                    message=commit.message.strip(),
                    author=str(commit.author),
                    date=commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                    files_changed=changed_files,
                )
            )
        return commits

    # ------------------------------------------------------------------
    # File content retrieval
    # ------------------------------------------------------------------

    def get_file_at_commit(self, filepath: str, sha: str) -> Optional[str]:
        """Return the text content of *filepath* at commit *sha*.

        *filepath* may be absolute or relative to the repository root.
        """
        if not self.is_git_repo:
            return None

        rel = os.path.relpath(filepath, self.repo_path)
        try:
            commit = self._repo.commit(sha)  # type: ignore[union-attr]
            blob = commit.tree / rel.replace(os.sep, "/")
            return blob.data_stream.read().decode("utf-8", errors="replace")
        except Exception:
            return None

    def get_tracked_bdf_files(self) -> List[str]:
        """Return a list of *.bdf files tracked in the repository."""
        if not self.is_git_repo:
            return []

        result = []
        try:
            for item in self._repo.tree().traverse():  # type: ignore[union-attr]
                if hasattr(item, "path") and item.path.lower().endswith(".bdf"):
                    result.append(item.path)
        except Exception:
            pass
        return result

    # ------------------------------------------------------------------
    # Working-tree helpers
    # ------------------------------------------------------------------

    def get_current_branch(self) -> str:
        if not self.is_git_repo:
            return "N/A"
        try:
            return self._repo.active_branch.name  # type: ignore[union-attr]
        except Exception:
            return "detached HEAD"

    def get_repo_name(self) -> str:
        return os.path.basename(self.repo_path)
