"""Matrix analysis runner.

The matrix is a co-occurrence table over *generation parameters*: steps, cfg
scale, sampler, scheduler, model, LoRA and clip skip. Its build is quadratic in
the parameter count, so the column set is an explicit whitelist rather than
"every field in the row". Two groups are deliberately excluded.

Prompt text (`positive_prompt`, `negative_prompt`) yields dozens of distinct
terms per image, which pushed the parameter set past the 10,000 limit and left
the build unable to finish. Term analysis belongs to `run_parameter_analysis`,
which reads the same prompts through the same extractor.

The remaining columns are per-image model predictions rather than generation
settings: `analysis` is a float distribution, `age`/`gender`/`race` are
probability maps, and the body-part columns are bbox dicts. Their values are
continuous, so nearly every row contributes parameters nobody has seen before
and the surviving cells are noise.
"""

from pathlib import Path
from typing import Any, Iterable, Iterator, cast

from ...core.filesystem.paths import analysis_dir, text_data_file
from ...core.io.serialization import load_single_jsonl, write_single_jsonl
from ...core.observability.logger import get_logger
from ...domain.training.matrix_analysis import MatrixAnalyzer
from .inputs import AnalysisInputs
from .row_fields import as_number, as_pairs, as_weight_map

logger = get_logger(__name__)

# Sampler, scheduler and model are one-hot columns; LoRA is a name/weight map.
WEIGHT_MAP_FIELDS: tuple[str, ...] = ("sampler", "scheduler", "model")
LORA_FIELD: str = "lora"
NUMERIC_FIELDS: tuple[str, ...] = ("steps", "cfg", "clip_skip")
PARAMETER_FIELDS: tuple[str, ...] = WEIGHT_MAP_FIELDS + NUMERIC_FIELDS + (LORA_FIELD,)


def scored_rows(
    inputs: AnalysisInputs,
    rows: Iterable[dict[str, Any]],
) -> Iterator[dict[str, Any]]:
    """Stream `{filename: payload}` rows as payload dicts, joined to a score.

    Public because it is the seam the analyzer tests drive: it is where the
    sidecar's one-key rows are unpacked into the payload shape
    `MatrixAnalyzer` expects, which is the defect this function exists to fix.
    Only rows whose filename has a score are yielded, so the matrix never
    carries a parameter value with no measurement behind it.
    """
    for row in rows:
        for filename, raw in row.items():
            if str(filename) not in inputs.scores:
                continue
            payload = cast("dict[str, Any]", raw)
            # Keep only the generation parameters, with their stringified forms
            # decoded: one-hot columns become pairs so the matrix emits
            # `sampler:euler_ancestral_1.0` rather than one opaque value per
            # row, and numbers come back as numbers.
            record: dict[str, Any] = {}
            for field in WEIGHT_MAP_FIELDS:
                weights = as_weight_map(payload.get(field))
                if weights:
                    record[field] = as_pairs(weights)
            for field in NUMERIC_FIELDS:
                number = as_number(payload.get(field))
                if number is not None:
                    record[field] = number
            # LoRA stays a real map: the analyzer reads its weight from the dict
            # values, which a repr string would flatten to a zero.
            lora = as_weight_map(payload.get(LORA_FIELD))
            if lora:
                record[LORA_FIELD] = lora
            yield record


def run_matrix_analysis(inputs: AnalysisInputs) -> int:
    if not inputs.scores:
        logger.error("No scores found. Run the build pipeline first.")
        return 1

    scores = [inputs.scores[key] for key in inputs.scores]
    records = list(scored_rows(inputs, load_single_jsonl(text_data_file)))
    if not records:
        logger.error("text_data.jsonl has no rows matching the scored images")
        return 1

    analyzer = MatrixAnalyzer(scores, records)
    analyzer.build_matrix()
    analyzer.calculate_statistics()

    output_path = str(Path(analysis_dir) / "matrix_analysis.jsonl")
    write_single_jsonl(output_path, analyzer.export_records())
    logger.info("Matrix analysis saved to %s", output_path)
    return 0