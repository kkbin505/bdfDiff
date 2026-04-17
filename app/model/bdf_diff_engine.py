"""
BDF Diff Engine using pyNastran.
Provides node-level structural diff data for 3D visualization.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Tuple

import numpy as np
from app.model.bdf_parser import BdfParser

try:
    from pyNastran.bdf.bdf import BDF
    PYNASTRAN_AVAILABLE = True
except Exception:  # pragma: no cover
    BDF = Any  # type: ignore[misc,assignment]
    PYNASTRAN_AVAILABLE = False


class BDFDiffEngine:
    """Diff engine for BDF entities backed by pyNastran."""

    def __init__(self, atol: float = 1e-6) -> None:
        self.atol = atol
        self._fallback_parser = BdfParser()

    def diff_files(self, old_path: str, new_path: str) -> dict:
        if PYNASTRAN_AVAILABLE:
            try:
                old_model = self._load_model_from_file(old_path)
                new_model = self._load_model_from_file(new_path)
                result = self._build_diff_result(old_model, new_model)
                result["engine"] = "pyNastran"
                return result
            except Exception:
                # Fall through to parser fallback when deck-level parsing fails.
                pass

        old_text = self._read_file(old_path)
        new_text = self._read_file(new_path)
        result = self._build_diff_result_fallback(old_text, new_text)
        result["engine"] = "fallback-parser"
        return result

    def diff_texts(self, old_text: str, new_text: str) -> dict:
        if PYNASTRAN_AVAILABLE:
            try:
                old_model = self._load_model_from_text(old_text)
                new_model = self._load_model_from_text(new_text)
                result = self._build_diff_result(old_model, new_model)
                result["engine"] = "pyNastran"
                return result
            except Exception:
                # Fall through to parser fallback when deck-level parsing fails.
                pass

        result = self._build_diff_result_fallback(old_text, new_text)
        result["engine"] = "fallback-parser"
        return result

    def _build_diff_result_fallback(self, old_text: str, new_text: str) -> dict:
        old_model = self._fallback_parser.parse_text(old_text)
        new_model = self._fallback_parser.parse_text(new_text)

        nodes1 = self._extract_nodes_from_parsed_model(old_model)
        nodes2 = self._extract_nodes_from_parsed_model(new_model)

        added, deleted, modified = self._diff_nodes_from_maps(nodes1, nodes2)

        elements1 = self._extract_elements_from_parsed_model(old_model)
        elements2 = self._extract_elements_from_parsed_model(new_model)
        eids1 = set(elements1)
        eids2 = set(elements2)

        element_added = sorted(eids2 - eids1)
        element_deleted = sorted(eids1 - eids2)
        element_modified: Dict[int, dict] = {}

        total_changes = (
            len(added)
            + len(deleted)
            + len(modified)
            + len(element_added)
            + len(element_deleted)
        )

        return {
            "nodes": {
                "added": added,
                "deleted": deleted,
                "modified": modified,
            },
            "elements": {
                "added": element_added,
                "deleted": element_deleted,
                "modified": element_modified,
            },
            "materials": {
                "added": [],
                "deleted": [],
                "modified": {},
            },
            "summary": {
                "total_changes": total_changes,
            },
            "render": {
                "nodes": {
                    "old": {str(nid): xyz.tolist() for nid, xyz in nodes1.items()},
                    "new": {str(nid): xyz.tolist() for nid, xyz in nodes2.items()},
                },
                "elements": {
                    "old": {str(eid): elem for eid, elem in elements1.items()},
                    "new": {str(eid): elem for eid, elem in elements2.items()},
                },
            },
        }

    def diff_nodes(self, m1: BDF, m2: BDF) -> Tuple[List[int], List[int], Dict[int, dict]]:
        """Compute node changes using the user-specified logic."""
        nodes1 = self._extract_nodes(m1)
        nodes2 = self._extract_nodes(m2)

        return self._diff_nodes_from_maps(nodes1, nodes2)

    def _diff_nodes_from_maps(
        self,
        nodes1: Dict[int, np.ndarray],
        nodes2: Dict[int, np.ndarray],
    ) -> Tuple[List[int], List[int], Dict[int, dict]]:

        ids1 = set(nodes1)
        ids2 = set(nodes2)

        added = sorted(ids2 - ids1)
        deleted = sorted(ids1 - ids2)
        common = ids1 & ids2

        modified: Dict[int, dict] = {}
        for nid in common:
            xyz1 = nodes1[nid]
            xyz2 = nodes2[nid]
            if not np.allclose(xyz1, xyz2, atol=self.atol):
                delta = xyz2 - xyz1
                modified[nid] = {
                    "old": xyz1.tolist(),
                    "new": xyz2.tolist(),
                    "delta": delta.tolist(),
                }

        return added, deleted, modified

    def _build_diff_result(self, m1: BDF, m2: BDF) -> dict:
        nodes1 = self._extract_nodes(m1)
        nodes2 = self._extract_nodes(m2)

        added, deleted, modified = self.diff_nodes(m1, m2)

        elements1 = self._extract_elements(m1)
        elements2 = self._extract_elements(m2)
        eids1 = set(elements1)
        eids2 = set(elements2)

        mats1 = set(self._extract_material_ids(m1))
        mats2 = set(self._extract_material_ids(m2))

        element_added = sorted(eids2 - eids1)
        element_deleted = sorted(eids1 - eids2)
        element_modified: Dict[int, dict] = {}

        total_changes = (
            len(added)
            + len(deleted)
            + len(modified)
            + len(element_added)
            + len(element_deleted)
            + len(element_modified)
            + len(mats2 - mats1)
            + len(mats1 - mats2)
        )

        return {
            "nodes": {
                "added": added,
                "deleted": deleted,
                "modified": modified,
            },
            "elements": {
                "added": element_added,
                "deleted": element_deleted,
                "modified": element_modified,
            },
            "materials": {
                "added": sorted(mats2 - mats1),
                "deleted": sorted(mats1 - mats2),
                "modified": {},
            },
            "summary": {
                "total_changes": total_changes,
            },
            # Rendering payload for Plotly
            "render": {
                "nodes": {
                    "old": {str(nid): xyz.tolist() for nid, xyz in nodes1.items()},
                    "new": {str(nid): xyz.tolist() for nid, xyz in nodes2.items()},
                },
                "elements": {
                    "old": {str(eid): elem for eid, elem in elements1.items()},
                    "new": {str(eid): elem for eid, elem in elements2.items()},
                },
            },
        }

    def _load_model_from_file(self, path: str) -> BDF:
        if not PYNASTRAN_AVAILABLE:
            raise RuntimeError("pyNastran is not installed")

        text = self._read_file(path)
        return self._load_model_from_text(text)

    def _load_model_from_text(self, text: str) -> BDF:
        # Parse only BULK cards to avoid executive/case-control encoding issues.
        bulk_text = self._extract_bulk_deck(text)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".bdf",
            encoding="utf-8",
            delete=False,
        ) as tmp:
            tmp.write(bulk_text)
            temp_path = tmp.name

        try:
            model = BDF(debug=False, log=None)
            # Bulk-only text behaves like a punch deck.
            model.read_bdf(temp_path, xref=False, punch=True)
            return model
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    @staticmethod
    def _extract_bulk_deck(text: str) -> str:
        """Return BULK-only content wrapped as a punch-friendly deck."""
        lines = text.splitlines()
        in_bulk = False
        bulk_lines: List[str] = []

        for raw in lines:
            line = raw.rstrip("\r\n")
            upper = line.strip().upper()

            if upper.startswith("BEGIN BULK") or upper == "BEGIN":
                in_bulk = True
                continue
            if upper.startswith("ENDDATA"):
                break

            if in_bulk:
                bulk_lines.append(line)

        # If no explicit BULK markers are found, use original lines as fallback.
        if not bulk_lines:
            bulk_lines = [ln.rstrip("\r\n") for ln in lines]

        return "\n".join(bulk_lines) + "\n"

    @staticmethod
    def _read_file(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return ""

    @staticmethod
    def _extract_nodes(model: BDF) -> Dict[int, np.ndarray]:
        nodes: Dict[int, np.ndarray] = {}
        for nid, node in model.nodes.items():
            try:
                xyz = np.asarray(node.xyz, dtype=float)
            except Exception:
                xyz = np.asarray(node.get_position(), dtype=float)
            nodes[int(nid)] = xyz
        return nodes

    @staticmethod
    def _extract_elements(model: BDF) -> Dict[int, dict]:
        elements: Dict[int, dict] = {}
        for eid, elem in model.elements.items():
            node_ids = [int(n) for n in getattr(elem, "node_ids", []) if n is not None]
            elements[int(eid)] = {
                "type": getattr(elem, "type", "UNKNOWN"),
                "node_ids": node_ids,
            }
        return elements

    @staticmethod
    def _extract_material_ids(model: BDF) -> List[int]:
        return [int(mid) for mid in model.materials.keys()]

    @staticmethod
    def _extract_nodes_from_parsed_model(model) -> Dict[int, np.ndarray]:
        nodes: Dict[int, np.ndarray] = {}
        for card in model.cards:
            if card.keyword != "GRID" or not card.raw_lines:
                continue

            tokens = card.raw_lines[0].replace(",", " ").split()
            if len(tokens) < 5:
                continue

            try:
                nid = int(tokens[1])
            except ValueError:
                continue

            # GRID nid cp x y z or GRID nid x y z
            try:
                if len(tokens) >= 6:
                    x, y, z = float(tokens[3]), float(tokens[4]), float(tokens[5])
                else:
                    x, y, z = float(tokens[2]), float(tokens[3]), float(tokens[4])
            except ValueError:
                continue

            nodes[nid] = np.asarray([x, y, z], dtype=float)
        return nodes

    @staticmethod
    def _extract_elements_from_parsed_model(model) -> Dict[int, dict]:
        elements: Dict[int, dict] = {}
        for card in model.cards:
            if card.keyword not in {"CQUAD4", "CTRIA3"} or not card.raw_lines:
                continue

            tokens = card.raw_lines[0].replace(",", " ").split()
            if len(tokens) < 6:
                continue

            try:
                eid = int(tokens[1])
            except ValueError:
                continue

            if card.keyword == "CQUAD4" and len(tokens) >= 7:
                raw_node_ids = tokens[3:7]
            elif card.keyword == "CTRIA3" and len(tokens) >= 6:
                raw_node_ids = tokens[3:6]
            else:
                continue

            try:
                node_ids = [int(v) for v in raw_node_ids]
            except ValueError:
                continue

            elements[eid] = {
                "type": card.keyword,
                "node_ids": node_ids,
            }
        return elements
