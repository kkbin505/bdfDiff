"""Tests for DiffEngine (Model layer)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.model.bdf_parser import BdfParser
from app.model.diff_engine import DiffEngine, DiffResult

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_files")
V1 = os.path.join(SAMPLE_DIR, "sample_v1.bdf")
V2 = os.path.join(SAMPLE_DIR, "sample_v2.bdf")


def _models_and_texts():
    parser = BdfParser()
    with open(V1) as f:
        old_text = f.read()
    with open(V2) as f:
        new_text = f.read()
    return parser.parse_text(old_text), parser.parse_text(new_text), old_text, new_text


class TestDiffEngineBasic:
    def test_diff_returns_result(self):
        old_m, new_m, old_t, new_t = _models_and_texts()
        result = DiffEngine().diff_models(old_m, new_m, old_t, new_t)
        assert isinstance(result, DiffResult)

    def test_added_cards_detected(self):
        old_m, new_m, old_t, new_t = _models_and_texts()
        result = DiffEngine().diff_models(old_m, new_m, old_t, new_t)
        # v2 adds GRID/7, GRID/8, CQUAD4/102
        assert result.added >= 3

    def test_modified_cards_detected(self):
        old_m, new_m, old_t, new_t = _models_and_texts()
        result = DiffEngine().diff_models(old_m, new_m, old_t, new_t)
        # PSHELL and FORCE cards were modified
        assert result.modified >= 1

    def test_removed_is_zero(self):
        old_m, new_m, old_t, new_t = _models_and_texts()
        result = DiffEngine().diff_models(old_m, new_m, old_t, new_t)
        # v2 is a superset of v1 – no removals
        assert result.removed == 0

    def test_unchanged_cards_exist(self):
        old_m, new_m, old_t, new_t = _models_and_texts()
        result = DiffEngine().diff_models(old_m, new_m, old_t, new_t)
        assert result.unchanged > 0

    def test_keyword_stats_populated(self):
        old_m, new_m, old_t, new_t = _models_and_texts()
        result = DiffEngine().diff_models(old_m, new_m, old_t, new_t)
        # At least GRID and CQUAD4 should appear in keyword_stats
        assert "GRID" in result.keyword_stats or "CQUAD4" in result.keyword_stats

    def test_text_diff_populated(self):
        old_m, new_m, old_t, new_t = _models_and_texts()
        result = DiffEngine().diff_models(old_m, new_m, old_t, new_t)
        assert len(result.text_diff) > 0

    def test_side_by_side_populated(self):
        old_m, new_m, old_t, new_t = _models_and_texts()
        result = DiffEngine().diff_models(old_m, new_m, old_t, new_t)
        assert len(result.side_by_side) > 0

    def test_to_dict_structure(self):
        old_m, new_m, old_t, new_t = _models_and_texts()
        result = DiffEngine().diff_models(old_m, new_m, old_t, new_t)
        d = result.to_dict()
        assert "summary" in d
        assert "card_diffs" in d
        assert "keyword_stats" in d
        assert "side_by_side" in d

    def test_summary_totals(self):
        old_m, new_m, old_t, new_t = _models_and_texts()
        result = DiffEngine().diff_models(old_m, new_m, old_t, new_t)
        total = result.added + result.removed + result.modified + result.unchanged
        assert total == len(result.card_diffs)


class TestDiffEngineIdentical:
    """Diffing a model against itself should show all unchanged."""

    def test_identical_has_no_changes(self):
        parser = BdfParser()
        with open(V1) as f:
            text = f.read()
        model = parser.parse_text(text)
        result = DiffEngine().diff_models(model, model, text, text)
        assert result.added == 0
        assert result.removed == 0
        assert result.modified == 0
        # card_by_key() de-duplicates cards that share the same key, so
        # the number of diff entries equals the number of unique keys.
        assert result.unchanged == len(model.card_by_key())


class TestDiffEngineTexts:
    def test_diff_texts_simple(self):
        old_t = "GRID    1               0.0     0.0     0.0\n"
        new_t = "GRID    1               1.0     0.0     0.0\n"
        result = DiffEngine().diff_texts(old_t, new_t)
        assert len(result.text_diff) > 0
        assert any("-" in line for line in result.text_diff)

    def test_side_by_side_change_types(self):
        old_t = "line1\nline2\nline3\n"
        new_t = "line1\nLINE2\nline3\nline4\n"
        result = DiffEngine().diff_texts(old_t, new_t)
        change_types = {row[4] for row in result.side_by_side}
        # Should have equal, replace, and insert rows
        assert "equal" in change_types
        assert "replace" in change_types or "insert" in change_types
