"""Tests for the parameter and matrix analyzers.

The failure these guard against is silent: both analyzers previously read a
schema the pipeline stopped writing, so every measurement defaulted to zero
instead of raising. The row shape is therefore asserted directly rather than
only through the outputs.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from .. import parameter_analysis as parameter_analysis_module
from .. import run_matrix_analysis, run_parameter_analysis
from ..inputs import AnalysisInputs, collect_analysis_inputs
from ..row_fields import as_number, as_pairs, as_weight_map, strongest

# The real text_data.jsonl payload keys. Keeping them here means a change to the
# writer that renames or drops one shows up as a failing assertion rather than as
# silently empty statistics. The values reproduce what `join_text_data` actually
# writes: numbers stringified, and one-hot columns as Python repr of a dict.
TEXT_ROWS: list[dict[str, Any]] = [
    {
        "a.png": {
            "steps": "30",
            "cfg": "7.5",
            "sampler": "{'euler': 1.0}",
            "scheduler": "{'normal': 1.0}",
            "model": "{'sdxl': 1.0}",
            "lora": "{'detail': 0.8}",
            "clip_skip": "-2",
            "positive_prompt": "smile, (hair:1.2)",
            "negative_prompt": "blurry",
        }
    },
    {
        "b.png": {
            "steps": "20",
            "cfg": "5.0",
            "sampler": "{'dpmpp': 1.0}",
            "scheduler": "{'karras': 1.0}",
            "model": "{'sdxl': 1.0}",
            "lora": "{}",
            "clip_skip": "2",
            "positive_prompt": "frown",
            "negative_prompt": "smile",
        }
    },
]


def _inputs(**overrides: Any) -> AnalysisInputs:
    scores = {"a.png": 0.8, "b.png": 0.2}
    prompt_tags: dict[str, str] = {}
    if "scores" in overrides:
        scores = overrides.pop("scores")
    prompt_tags = overrides.pop("prompt_tags", prompt_tags)
    return AnalysisInputs(scores=scores, prompt_tags=prompt_tags)


def _rows(rows: list[dict[str, Any]] | None = None) -> Any:
    data = TEXT_ROWS if rows is None else rows
    return lambda: iter(list(data))


def _terms(group: dict[str, Any]) -> set[str]:
    return {term for term, _ in group["top_terms"]}


def test_rows_are_single_key_filename_objects() -> None:
    """The sidecar keys each line by filename; the analyzers must unpack it."""
    for row in TEXT_ROWS:
        assert len(row) == 1
        filename, payload = next(iter(row.items()))
        assert filename.endswith(".png")
        # Generation parameters live at the top level, not under
        # generation_params, and the prompt is raw text rather than terms.
        assert "steps" in payload
        assert "generation_params" not in payload
        assert isinstance(payload["positive_prompt"], str)
        # The writer stringifies every column.
        assert isinstance(payload["steps"], str)


def test_stringified_columns_are_parsed() -> None:
    """Numbers arrive as strings and one-hot columns as Python repr strings."""
    assert as_number("30") == pytest.approx(30.0)
    assert as_number("") is None
    assert as_number("not a number") is None
    assert as_number({"a": 1}) is None
    # Booleans are not measurements even though they subclass int.
    assert as_number(True) is None

    assert as_weight_map("{'euler': 1.0}") == {"euler": 1.0}
    assert as_weight_map("{}") == {}
    assert as_weight_map("{'broken': ") == {}
    assert as_weight_map("plain text") == {}
    assert as_weight_map({"euler": 1.0}) == {"euler": 1.0}
    assert strongest(as_weight_map("{'euler': 0.4, 'dpmpp': 0.9}")) == ("dpmpp", 0.9)
    assert strongest({}) == ("", 0.0)


def test_parameter_analysis_pairs_each_row_with_its_own_score(tmp_path: Path) -> None:
    analyzer = parameter_analysis_module.ParameterAnalyzer(
        _inputs(), _rows(), output_dir=str(tmp_path)
    )
    analyzer.analyze_all()

    sampler = json.loads((tmp_path / "sampler_stats.json").read_text())
    # euler belongs to a.png (0.8) and dpmpp to b.png (0.2). A positional zip
    # would have swapped or averaged these.
    assert sampler["euler"]["avg_score"] == pytest.approx(0.8)
    assert sampler["dpmpp"]["avg_score"] == pytest.approx(0.2)

    steps = json.loads((tmp_path / "steps_stats.json").read_text())
    assert steps["count"] == 2


def test_parameter_analysis_writes_the_stats_that_were_never_written(
    tmp_path: Path,
) -> None:
    analyzer = parameter_analysis_module.ParameterAnalyzer(
        _inputs(), _rows(), output_dir=str(tmp_path)
    )
    analyzer.analyze_parameter_pairs()

    for name in (
        "steps_stats.json",
        "cfg_stats.json",
        "lora_stats.json",
        "sampler_stats.json",
        "scheduler_stats.json",
        "model_stats.json",
    ):
        assert (tmp_path / name).exists(), name

    # Only a.png carries a LoRA, and it is a single weighted entry.
    lora = json.loads((tmp_path / "lora_stats.json").read_text())
    assert lora["count"] == 1
    assert lora["max"] == pytest.approx(0.8)


def test_terms_are_weighted_and_groups_are_separate(tmp_path: Path) -> None:
    analyzer = parameter_analysis_module.ParameterAnalyzer(
        _inputs(), _rows(), output_dir=str(tmp_path)
    )
    analyzer.analyze_term_correlations()

    payload = json.loads((tmp_path / "term_correlations.json").read_text())
    positive = payload["positive"]
    negative = payload["negative"]

    positive_terms = _terms(positive)
    negative_terms = _terms(negative)

    # extract_terms strips the weighting syntax, so "hair" survives without the
    # parentheses and colon rather than as the raw "(hair:1.2)" text.
    assert "hair" in positive_terms
    assert "(hair:1.2)" not in positive_terms

    # A negative-only term stays out of the positive group.
    assert "blurry" in negative_terms
    assert "blurry" not in positive_terms

    # "smile" appears in both groups, from a.png's positive prompt and b.png's
    # negative prompt. Separate groups means both lists report it rather than
    # the two being blended or inverted into one ranking.
    assert "smile" in negative_terms
    assert "smile" in positive_terms

    assert payload["rows_analyzed"] == 2


def test_prompt_tags_take_priority_over_the_sidecar_prompt(tmp_path: Path) -> None:
    inputs = _inputs(prompt_tags={"a.png": "from_database", "b.png": "other_tag"})
    analyzer = parameter_analysis_module.ParameterAnalyzer(
        inputs, _rows(), output_dir=str(tmp_path)
    )
    analyzer.analyze_term_correlations()

    payload = json.loads((tmp_path / "term_correlations.json").read_text())
    terms = _terms(payload["positive"])
    assert "from_database" in terms
    assert "other_tag" in terms
    assert "smile" not in terms


def test_rows_without_a_score_are_skipped(tmp_path: Path) -> None:
    analyzer = parameter_analysis_module.ParameterAnalyzer(
        _inputs(scores={"a.png": 0.5}), _rows(), output_dir=str(tmp_path)
    )
    analyzer.analyze_parameter_pairs()

    sampler = json.loads((tmp_path / "sampler_stats.json").read_text())
    assert "dpmpp" not in sampler


def test_matrix_rows_keep_only_generation_parameters() -> None:
    records = list(run_matrix_analysis.scored_rows(_inputs(), TEXT_ROWS))

    assert len(records) == 2
    first = records[0]
    # Prompts and the per-image prediction columns (analysis, age, gender, race,
    # body-part bboxes) are not generation parameters. Their values are
    # continuous, so keeping them filled the parameter set with unseen values.
    assert set(first) <= set(run_matrix_analysis.PARAMETER_FIELDS)
    assert "positive_prompt" not in first
    assert "analysis" not in first

    # One-hot columns become pairs.
    assert first["sampler"] == [("euler", pytest.approx(1.0))]
    # Numbers are parsed back out of the writer's strings.
    assert first["steps"] == pytest.approx(30.0)
    assert first["cfg"] == pytest.approx(7.5)
    assert first["clip_skip"] == pytest.approx(-2.0)
    # LoRA stays a real map so the analyzer reads its weight rather than 0.
    assert first["lora"] == {"detail": pytest.approx(0.8)}


def test_matrix_rows_drop_prediction_columns_present_in_the_payload() -> None:
    rows = [
        {
            "a.png": {
                "steps": "30",
                "sampler": "{'euler': 1.0}",
                "analysis": "{'contrast': 0.4, 'noise_score': 0.7}",
                "age": "[{'young': 0.8, 'old': 0.2}]",
                "left_heel": "[{'x': 0.75, 'y': 0.82}]",
                "positive_prompt": "smile",
                "negative_prompt": "blurry",
                "nsfw_score": "0.9",
            }
        }
    ]
    record = next(iter(run_matrix_analysis.scored_rows(_inputs(), rows)))

    assert set(record) == {"sampler", "steps"}
    assert record["sampler"] == [("euler", pytest.approx(1.0))]


def test_as_pairs_drops_empty_names() -> None:
    assert as_pairs({"a": 1.0}) == [("a", 1.0)]
    assert as_pairs({"": 1.0}) == []


def test_matrix_rows_skip_entries_without_a_score() -> None:
    records = list(
        run_matrix_analysis.scored_rows(_inputs(scores={"a.png": 0.5}), TEXT_ROWS)
    )
    assert len(records) == 1
    assert records[0]["sampler"] == [("euler", pytest.approx(1.0))]


def test_no_analysis_module_references_the_vectors_file() -> None:
    """vectors.jsonl holds embeddings and no score, so no analyzer may read it."""
    for module in (
        parameter_analysis_module,
        run_parameter_analysis,
        run_matrix_analysis,
    ):
        source = inspect.getsource(module)
        assert "vectors_file" not in source, module.__name__


def test_runners_report_failure_without_scores() -> None:
    assert run_parameter_analysis.run_parameter_analysis(_inputs(scores={})) == 1
    assert run_matrix_analysis.run_matrix_analysis(_inputs(scores={})) == 1


def test_collect_analysis_inputs_reads_scores_and_skips_missing_tags() -> None:
    nodes = [
        SimpleNamespace(filename="a.png", prompt_tags="tag_a"),
        SimpleNamespace(filename="b.png", prompt_tags=None),
    ]
    graph = cast("CrystalGraphPort", SimpleNamespace(get_all_nodes=lambda: nodes))
    loader = cast("TrainingLoader", SimpleNamespace(load_scores=lambda: {"a.png": 0.5}))

    inputs = collect_analysis_inputs(graph, loader)

    assert inputs.scores == {"a.png": 0.5}
    assert inputs.prompt_tags == {"a.png": "tag_a"}