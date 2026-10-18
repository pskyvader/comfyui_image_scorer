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
from ....domain.ports.graph import CrystalGraphPort
from ....domain.ports.loading import TrainingLoader

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


def _terms(summary: parameter_analysis_module.TermCorrelationSummary) -> set[str]:
    return {str(record["term"]) for record in summary.terms}


def _corpus(prefix: str, terms: list[str], count: int) -> list[dict[str, Any]]:
    """Distinctly named rows that all carry the same terms.

    Filenames have to differ: the analyzers join on filename, so repeated keys
    would collapse into one scored image.
    """
    return [
        {
            f"{prefix}{index}.png": {
                "positive_prompt": ", ".join(terms),
                "negative_prompt": "",
            }
        }
        for index in range(count)
    ]


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


def test_terms_are_weighted_and_groups_are_separate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two images cannot clear the production floor, and most terms here appear
    # once, so this test drops the floor to 1. It checks which terms are
    # recognised and kept apart, not which ones survive on real data.
    monkeypatch.setattr(parameter_analysis_module, "MIN_TERM_IMAGES", 1)
    analyzer = parameter_analysis_module.ParameterAnalyzer(
        _inputs(), _rows(), output_dir=str(tmp_path)
    )
    summaries = analyzer.analyze_term_correlations()

    payload = json.loads((tmp_path / "term_correlations.json").read_text())
    assert payload["min_term_images"] == 1

    positive_terms = _terms(summaries["positive"])
    negative_terms = _terms(summaries["negative"])

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
    assert summaries["positive"].rows_analyzed == 2


def test_prompt_tags_take_priority_over_the_sidecar_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(parameter_analysis_module, "MIN_TERM_IMAGES", 1)
    inputs = _inputs(prompt_tags={"a.png": "from_database", "b.png": "other_tag"})
    analyzer = parameter_analysis_module.ParameterAnalyzer(
        inputs, _rows(), output_dir=str(tmp_path)
    )
    summaries = analyzer.analyze_term_correlations()

    terms = _terms(summaries["positive"])
    assert "from_database" in terms
    assert "other_tag" in terms
    assert "smile" not in terms


def test_terms_below_the_floor_are_counted_not_ranked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(parameter_analysis_module, "MIN_TERM_IMAGES", 100)
    analyzer = parameter_analysis_module.ParameterAnalyzer(
        _inputs(), _rows(), output_dir=str(tmp_path)
    )
    summaries = analyzer.analyze_term_correlations()

    positive = summaries["positive"]
    # The terms exist but two images cannot support a ranking.
    assert positive.unique_terms > 0
    assert positive.kept_terms == 0
    assert positive.dropped_below_floor == positive.unique_terms
    assert positive.terms == []


def test_a_kept_term_reports_both_presence_figures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(parameter_analysis_module, "MIN_TERM_IMAGES", 3)
    rows = _corpus("in", ["smile", "hair"], 4) + _corpus("out", ["hair"], 1)
    scores = {
        **{f"in{index}.png": 0.9 for index in range(4)},
        "out0.png": 0.1,
    }
    analyzer = parameter_analysis_module.ParameterAnalyzer(
        _inputs(scores=scores), _rows(rows), output_dir=str(tmp_path)
    )
    summaries = analyzer.analyze_term_correlations()

    records = {str(record["term"]): record for record in summaries["positive"].terms}
    assert set(records) == {"smile", "hair"}

    smile = records["smile"]
    # The weighted mean is a separate figure from the plain presence mean, so a
    # term used with an explicit weight cannot masquerade as a strong effect.
    assert smile["count"] == 4
    assert smile["avg_score"] == pytest.approx(0.9)
    assert smile["weighted_avg_score"] == pytest.approx(0.9)
    assert smile["baseline_avg_score"] == pytest.approx(0.1)
    assert smile["delta"] == pytest.approx(0.8)
    assert 0.0 <= smile["p_value"] <= 1.0
    assert smile["cliffs_delta"] == pytest.approx(1.0)

    # "hair" is in every image, so there is nothing to compare it against and
    # the baseline falls back to the group's own mean.
    hair = records["hair"]
    assert hair["count"] == 5
    assert hair["delta"] == pytest.approx(0.0)


def test_term_records_are_ordered_by_delta_and_corrected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(parameter_analysis_module, "MIN_TERM_IMAGES", 4)
    rows = _corpus("good", ["good"], 6) + _corpus("bad", ["bad"], 6)
    scores = {f"good{index}.png": 0.8 for index in range(6)}
    scores.update({f"bad{index}.png": 0.2 for index in range(6)})
    analyzer = parameter_analysis_module.ParameterAnalyzer(
        _inputs(scores=scores), _rows(rows), output_dir=str(tmp_path)
    )
    summaries = analyzer.analyze_term_correlations()

    terms = summaries["positive"].terms
    assert [str(record["term"]) for record in terms] == ["bad", "good"]
    assert all(0.0 <= float(record["q_value"]) <= 1.0 for record in terms)
    # Both terms have the same separation here, so they share a raw p-value. The
    # largest scaled value is p * 2/1 and the smallest p * 2/2, and the
    # monotonicity step pulls the smallest down to the largest-rank figure.
    raw = [float(record["p_value"]) for record in terms]
    assert raw[0] == pytest.approx(raw[1])
    assert terms[0]["q_value"] == pytest.approx(raw[0])
    assert terms[1]["q_value"] == pytest.approx(raw[1])
    assert all(
        float(record["q_value"]) >= float(record["p_value"]) for record in terms
    )


def test_negative_prompt_terms_are_reported_separately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(parameter_analysis_module, "MIN_TERM_IMAGES", 4)
    rows = [
        {
            f"img{index}.png": {"positive_prompt": "smile", "negative_prompt": "blurry"}
        }
        for index in range(5)
    ]
    # Distinct filenames per row: the analyzers join on filename, so repeated
    # keys would collapse into a single scored image.
    analyzer = parameter_analysis_module.ParameterAnalyzer(
        _inputs(scores={f"img{index}.png": 0.5 for index in range(5)}),
        _rows(rows),
        output_dir=str(tmp_path),
    )
    summaries = analyzer.analyze_term_correlations()

    assert _terms(summaries["negative"]) == {"blurry"}
    assert _terms(summaries["positive"]) == {"smile"}


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