from functools import partial

from ...core.filesystem.paths import text_data_file
from ...core.io.serialization import load_single_jsonl
from ...core.observability.logger import get_logger
from .inputs import AnalysisInputs
from .parameter_analysis import ParameterAnalyzer

logger = get_logger(__name__)


def run_parameter_analysis(inputs: AnalysisInputs) -> int:
    if not inputs.scores:
        logger.error("No scores found. Run the build pipeline first.")
        return 1

    # Streamed rather than materialized: one object per scored image, each
    # consumed once per analysis pass.
    analyzer = ParameterAnalyzer(inputs, partial(load_single_jsonl, text_data_file))
    analyzer.analyze_all()
    logger.info("Parameter analysis report generated in output/analysis/")
    return 0