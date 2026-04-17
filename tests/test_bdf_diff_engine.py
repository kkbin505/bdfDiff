"""Tests for BDFDiffEngine (pyNastran-based node diff)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from app.model.bdf_diff_engine import BDFDiffEngine, PYNASTRAN_AVAILABLE
except Exception:  # pragma: no cover
    BDFDiffEngine = None
    PYNASTRAN_AVAILABLE = False

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_files")
V1 = os.path.join(SAMPLE_DIR, "sample_v1.bdf")
V2 = os.path.join(SAMPLE_DIR, "sample_v2.bdf")


pytestmark = pytest.mark.skipif(
    BDFDiffEngine is None or not PYNASTRAN_AVAILABLE,
    reason="pyNastran is not available",
)


class TestBDFDiffEngine:
    def test_diff_files_structure(self):
        result = BDFDiffEngine().diff_files(V1, V2)
        assert "nodes" in result
        assert "elements" in result
        assert "materials" in result
        assert "summary" in result
        assert "total_changes" in result["summary"]

    def test_node_diff_core_fields(self):
        result = BDFDiffEngine().diff_files(V1, V2)
        assert "added" in result["nodes"]
        assert "deleted" in result["nodes"]
        assert "modified" in result["nodes"]

    def test_node_modified_has_old_new_delta(self):
        engine = BDFDiffEngine(atol=1e-12)
        old_t = "BEGIN BULK\nGRID,1,,0.,0.,0.\nENDDATA\n"
        new_t = "BEGIN BULK\nGRID,1,,0.1,0.,0.\nENDDATA\n"
        result = engine.diff_texts(old_t, new_t)
        assert 1 in [int(k) for k in result["nodes"]["modified"].keys()]
        entry = result["nodes"]["modified"][1]
        assert "old" in entry and "new" in entry and "delta" in entry
        assert pytest.approx(entry["delta"][0], abs=1e-9) == 0.1
