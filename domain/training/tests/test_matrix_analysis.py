"""Tests for the matrix analyzer's record export.

`export_records` replaced a method that wrote the same rows to disk. The row
shape is the contract the analysis notebooks chart, so it is asserted directly
rather than only through the JSONL artifact.
"""

from __future__ import annotations

import pytest

from ..matrix_analysis import MatrixAnalyzer


def _analyzer(
    scores: list[float], records: list[dict[str, object]], min_count: int = 100
) -> MatrixAnalyzer:
    analyzer = MatrixAnalyzer(scores, records)
    analyzer.build_matrix()
    analyzer.calculate_statistics(min_count=min_count)
    return analyzer


@pytest.fixture
def built() -> MatrixAnalyzer:
    scores = [0.9, 0.9, 0.9, 0.1, 0.1, 0.1]
    high: dict[str, object] = {"steps": 30, "sampler": [("euler", 1.0)], "lora": {"a": 1.0, "b": 0.5}}
    low: dict[str, object] = {"steps": 20, "sampler": [("dpmpp", 1.0)], "lora": {}}
    records: list[dict[str, object]] = [high] * 3 + [low] * 3
    # The default min_count of 100 would discard every cell of a six-row fixture.
    return _analyzer(scores, records, min_count=1)


def test_export_records_returns_one_row_per_kept_cell(built: MatrixAnalyzer) -> None:
    records = built.export_records()
    # Off-diagonal cells are mirrored into both triangles but exported once, so
    # the row count is derived from cell_stats plus the diagonal counted back in.
    diagonal = sum(1 for cell in built.cell_stats if cell[0] == cell[1])
    kept = (len(built.cell_stats) + diagonal) // 2
    assert len(records) == kept
    assert 0 < len(records) <= (len(built.param_list) * (len(built.param_list) + 1)) // 2


def test_export_records_keys_each_row_by_its_parameter_pair(built: MatrixAnalyzer) -> None:
    for record in built.export_records():
        first, second = str(record["parameters"]).split("|")
        assert first in built.param_list
        assert second in built.param_list


def test_export_records_keeps_the_diagonal_once(built: MatrixAnalyzer) -> None:
    pairs = [str(record["parameters"]) for record in built.export_records()]
    for name in built.param_list:
        assert pairs.count(f"{name}|{name}") == 1
        assert pairs.count(f"{name}|{name}") == 1


def test_export_records_is_upper_triangular_only(built: MatrixAnalyzer) -> None:
    # Every pair appears in sorted order, so no cell is reported twice.
    for record in built.export_records():
        first, second = str(record["parameters"]).split("|")
        assert built.param_id_map[first] <= built.param_id_map[second]


def test_export_records_carries_the_cell_statistics(built: MatrixAnalyzer) -> None:
    stats_keys = {
        "count",
        "mean",
        "std",
        "min",
        "max",
        "median",
        "mode",
        "q1",
        "q3",
        "iqr",
        "cv",
        "range",
    }
    for record in built.export_records():
        assert set(record) == {"parameters"} | stats_keys
        assert float(str(record["count"])) >= 1


def test_export_records_of_an_empty_matrix_is_empty() -> None:
    analyzer = MatrixAnalyzer([], [])
    analyzer.build_matrix()
    analyzer.calculate_statistics()
    assert analyzer.export_records() == []


def test_cells_below_the_minimum_count_are_not_reported() -> None:
    scores = [0.9, 0.1]
    records: list[dict[str, object]] = [
        {"steps": 30, "sampler": [("euler", 1.0)]},
        {"steps": 20, "sampler": [("dpmpp", 1.0)]},
    ]
    analyzer = _analyzer(scores, records, min_count=100)
    assert analyzer.cell_stats == {}
    assert analyzer.export_records() == []


def test_export_records_is_stable_across_calls(built: MatrixAnalyzer) -> None:
    assert built.export_records() == built.export_records()
