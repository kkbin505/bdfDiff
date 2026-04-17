"""Tests for BdfParser (Model layer)."""

import os
import sys
import pytest

# Make sure app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.model.bdf_parser import BdfParser, BdfCard, BdfModel

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_files")
V1 = os.path.join(SAMPLE_DIR, "sample_v1.bdf")
V2 = os.path.join(SAMPLE_DIR, "sample_v2.bdf")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_v1() -> BdfModel:
    return BdfParser().parse_file(V1)


def parse_v2() -> BdfModel:
    return BdfParser().parse_file(V2)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBdfParserBasic:
    def test_parse_file_returns_model(self):
        model = parse_v1()
        assert isinstance(model, BdfModel)

    def test_cards_not_empty(self):
        model = parse_v1()
        assert len(model.cards) > 0

    def test_grid_cards_present(self):
        model = parse_v1()
        grids = [c for c in model.cards if c.keyword == "GRID"]
        assert len(grids) == 6

    def test_pshell_present(self):
        model = parse_v1()
        props = [c for c in model.cards if c.keyword == "PSHELL"]
        assert len(props) == 1

    def test_mat1_present(self):
        model = parse_v1()
        mats = [c for c in model.cards if c.keyword == "MAT1"]
        assert len(mats) == 1

    def test_cquad4_elements(self):
        model = parse_v1()
        elems = [c for c in model.cards if c.keyword == "CQUAD4"]
        assert len(elems) == 2

    def test_card_id_extraction(self):
        model = parse_v1()
        grids = [c for c in model.cards if c.keyword == "GRID"]
        ids = {c.card_id.strip() for c in grids}
        # GRIDs 1–6 should be found
        assert "1" in ids
        assert "6" in ids

    def test_card_key_format(self):
        model = parse_v1()
        for card in model.cards:
            assert "/" in card.key, f"key {card.key!r} missing '/'"

    def test_summary_counts(self):
        model = parse_v1()
        summary = model.summary()
        assert summary["GRID"] == 6
        assert summary["CQUAD4"] == 2

    def test_keywords_list(self):
        model = parse_v1()
        kws = model.keywords()
        assert "GRID" in kws
        assert "MAT1" in kws

    def test_v2_has_more_grids(self):
        model = parse_v2()
        grids = [c for c in model.cards if c.keyword == "GRID"]
        assert len(grids) == 8   # v2 adds GRID 7 and GRID 8

    def test_v2_has_more_elements(self):
        model = parse_v2()
        elems = [c for c in model.cards if c.keyword == "CQUAD4"]
        assert len(elems) == 3


class TestBdfParserText:
    """Test parsing directly from text strings."""

    SIMPLE_BDF = """\
BEGIN BULK
GRID    1               0.0     0.0     0.0
GRID    2               1.0     0.0     0.0
MAT1    1       200000.0        0.3
ENDDATA
"""

    FREE_FIELD_BDF = """\
BEGIN BULK
GRID,1,,0.0,0.0,0.0
GRID,2,,1.0,0.0,0.0
ENDDATA
"""

    def test_parse_text_simple(self):
        model = BdfParser().parse_text(self.SIMPLE_BDF)
        assert len([c for c in model.cards if c.keyword == "GRID"]) == 2
        assert len([c for c in model.cards if c.keyword == "MAT1"]) == 1

    def test_parse_text_free_field(self):
        model = BdfParser().parse_text(self.FREE_FIELD_BDF)
        grids = [c for c in model.cards if c.keyword == "GRID"]
        assert len(grids) == 2

    def test_card_by_key_unique(self):
        model = BdfParser().parse_text(self.SIMPLE_BDF)
        by_key = model.card_by_key()
        assert "GRID/1" in by_key or any("GRID" in k for k in by_key)

    def test_empty_text(self):
        model = BdfParser().parse_text("")
        assert model.cards == []

    def test_comment_only(self):
        model = BdfParser().parse_text("$ This is a comment\n$ Another comment\n")
        assert model.cards == []
