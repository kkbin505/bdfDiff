"""Tests for GitManager path normalization helpers."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.model.git_manager import GitManager


class TestGitManagerPathNormalization:
    def test_relative_path_to_repo_relative(self):
        manager = GitManager(repo_path=os.path.join("D:/", "repo"))
        rel = manager._to_repo_relative("models/plate_v1.bdf")
        assert rel == "models/plate_v1.bdf"

    def test_absolute_path_to_repo_relative(self):
        manager = GitManager(repo_path=os.path.join("D:/", "repo"))
        abs_file = os.path.join("D:/", "repo", "models", "plate_v1.bdf")
        rel = manager._to_repo_relative(abs_file)
        assert rel == "models/plate_v1.bdf"

    def test_path_outside_repo_returns_none(self):
        manager = GitManager(repo_path=os.path.join("D:/", "repo"))
        outside = os.path.join("D:/", "other", "plate_v1.bdf")
        rel = manager._to_repo_relative(outside)
        assert rel is None

    def test_resolve_repo_file(self):
        manager = GitManager(repo_path=os.path.join("D:/", "repo"))
        resolved = manager.resolve_repo_file("models/plate_v1.bdf")
        expected = os.path.join("D:/", "repo", "models", "plate_v1.bdf")
        assert os.path.normpath(resolved or "") == os.path.normpath(expected)
