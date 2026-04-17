"""
Git Manager – Model layer
Wraps GitPython to provide version-control operations on a BDF repository.
"""

from __future__ import annotations

import os
import subprocess
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

    def _run_git(self, args: List[str]) -> Optional[str]:
        """Run git command in repo and return stdout on success."""
        try:
            proc = subprocess.run(
                ["git", "-C", self.repo_path, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except Exception:
            return None

        if proc.returncode != 0:
            return None
        return proc.stdout

    @property
    def is_git_repo(self) -> bool:
        if self._repo is not None:
            return True
        out = self._run_git(["rev-parse", "--is-inside-work-tree"])
        return (out or "").strip().lower() == "true"

    def _to_repo_relative(self, filepath: str) -> Optional[str]:
        """Normalize a file path to a repository-relative path.

        Accepts either an absolute path or a path already relative to the repo
        root. Returns None if the resulting path points outside the repository.
        """
        if not filepath:
            return None

        if os.path.isabs(filepath):
            abs_path = os.path.abspath(filepath)
        else:
            abs_path = os.path.abspath(os.path.join(self.repo_path, filepath))

        try:
            rel = os.path.relpath(abs_path, self.repo_path)
        except ValueError:
            return None

        if rel.startswith("..") or os.path.isabs(rel):
            return None
        return rel.replace(os.sep, "/")

    def resolve_repo_file(self, filepath: str) -> Optional[str]:
        """Return absolute path for a repository-relative file path."""
        rel = self._to_repo_relative(filepath)
        if rel is None:
            return None
        return os.path.join(self.repo_path, rel.replace("/", os.sep))

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

        rel: Optional[str] = None
        if filepath:
            rel = self._to_repo_relative(filepath)
            if rel is None:
                return []

        if self._repo is not None:
            kwargs: dict = {"max_count": max_count}
            if rel:
                kwargs["paths"] = rel

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

        args = [
            "log",
            f"--max-count={max_count}",
            "--date=format:%Y-%m-%d %H:%M:%S",
            "--pretty=format:__COMMIT__%n%H%x1f%h%x1f%an%x1f%ad%x1f%s",
            "--name-only",
        ]
        if rel:
            args.extend(["--", rel])

        out = self._run_git(args)
        if out is None:
            return []

        commits: List[CommitInfo] = []
        for block in out.split("__COMMIT__\n"):
            block = block.strip("\n")
            if not block:
                continue

            lines = [line for line in block.splitlines() if line.strip()]
            if not lines:
                continue

            header = lines[0].split("\x1f")
            if len(header) != 5:
                continue

            sha, short_sha, author, date, message = header
            files_changed = [ln.strip() for ln in lines[1:] if ln.strip()]
            commits.append(
                CommitInfo(
                    sha=sha,
                    short_sha=short_sha,
                    message=message,
                    author=author,
                    date=date,
                    files_changed=files_changed,
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

        rel = self._to_repo_relative(filepath)
        if rel is None:
            return None
        if self._repo is not None:
            try:
                commit = self._repo.commit(sha)  # type: ignore[union-attr]
                blob = commit.tree / rel
                return blob.data_stream.read().decode("utf-8", errors="replace")
            except Exception:
                return None

        return self._run_git(["show", f"{sha}:{rel}"])

    def get_tracked_bdf_files(self) -> List[str]:
        """Return a list of *.bdf files tracked in the repository."""
        if not self.is_git_repo:
            return []

        if self._repo is not None:
            result = []
            try:
                for item in self._repo.tree().traverse():  # type: ignore[union-attr]
                    if hasattr(item, "path") and item.path.lower().endswith(".bdf"):
                        result.append(item.path)
            except Exception:
                pass
            return result

        out = self._run_git(["ls-files"])
        if out is None:
            return []
        return [line.strip() for line in out.splitlines() if line.strip().lower().endswith(".bdf")]

    # ------------------------------------------------------------------
    # Working-tree helpers
    # ------------------------------------------------------------------

    def get_current_branch(self) -> str:
        if not self.is_git_repo:
            return "N/A"
        if self._repo is not None:
            try:
                return self._repo.active_branch.name  # type: ignore[union-attr]
            except Exception:
                return "detached HEAD"

        out = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if out is None:
            return "N/A"
        branch = out.strip()
        return "detached HEAD" if branch == "HEAD" else branch

    def get_repo_name(self) -> str:
        return os.path.basename(self.repo_path)
