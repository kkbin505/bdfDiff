"""Tests for DiffPresenter (Presenter layer)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.presenter.diff_presenter import DiffPresenter

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_files")
V1 = os.path.join(SAMPLE_DIR, "sample_v1.bdf")
V2 = os.path.join(SAMPLE_DIR, "sample_v2.bdf")


class TestDiffPresenterFiles:
    def setup_method(self):
        self.presenter = DiffPresenter(repo_path=os.path.join(SAMPLE_DIR, ".."))

    def test_diff_files_returns_dict(self):
        data = self.presenter.diff_files(V1, V2)
        assert isinstance(data, dict)

    def test_diff_files_has_summary(self):
        data = self.presenter.diff_files(V1, V2)
        assert "summary" in data
        assert "added" in data["summary"]

    def test_diff_files_labels(self):
        data = self.presenter.diff_files(V1, V2)
        assert "old_label" in data
        assert "new_label" in data

    def test_diff_files_card_diffs(self):
        data = self.presenter.diff_files(V1, V2)
        assert "card_diffs" in data
        assert isinstance(data["card_diffs"], list)
        assert len(data["card_diffs"]) > 0

    def test_diff_files_all_keywords(self):
        data = self.presenter.diff_files(V1, V2)
        assert "all_keywords" in data
        assert len(data["all_keywords"]) > 0

    def test_diff_files_diffs_by_keyword(self):
        data = self.presenter.diff_files(V1, V2)
        assert "diffs_by_keyword" in data
        diffs_by_kw = data["diffs_by_keyword"]
        assert isinstance(diffs_by_kw, dict)

    def test_diff_files_side_by_side(self):
        data = self.presenter.diff_files(V1, V2)
        assert "side_by_side" in data
        assert len(data["side_by_side"]) > 0

    def test_diff_files_text_diff(self):
        data = self.presenter.diff_files(V1, V2)
        assert "text_diff" in data
        assert len(data["text_diff"]) > 0

    def test_diff_texts_works(self):
        with open(V1, encoding="utf-8") as f:
            old = f.read()
        with open(V2, encoding="utf-8") as f:
            new = f.read()
        data = self.presenter.diff_texts(old, new)
        assert data["summary"]["added"] >= 3

    def test_get_file_summary(self):
        summary = self.presenter.get_file_summary(V1)
        assert "summary" in summary
        assert summary["summary"]["GRID"] == 6


class TestDiffPresenterGitInfo:
    def setup_method(self):
        self.presenter = DiffPresenter(repo_path=SAMPLE_DIR)

    def test_get_repo_info_returns_dict(self):
        info = self.presenter.get_repo_info()
        assert isinstance(info, dict)
        assert "is_git_repo" in info

    def test_get_commits_returns_list(self):
        commits = self.presenter.get_commits()
        assert isinstance(commits, list)


class TestDiffPresenterIdentical:
    def setup_method(self):
        self.presenter = DiffPresenter()

    def test_identical_texts_zero_changes(self):
        text = "GRID    1               0.0     0.0     0.0\n"
        data = self.presenter.diff_texts(text, text)
        assert data["summary"]["added"] == 0
        assert data["summary"]["removed"] == 0
        assert data["summary"]["modified"] == 0
