from ...core.filesystem.paths import text_data_file
from ...core.io.serialization import load_single_jsonl
from ...core.observability.logger import get_logger
from .inputs import AnalysisInputs
from .parameter_analysis import ParameterAnalyzer

logger = get_logger(__name__)


def _text_rows():
    """Stream the text sidecar. Never materialized: it holds one object per
    scored image and each is consumed once per analysis pass."""
    return iter(load_single_jsonl(text_data_file))


def run_parameter_analysis(inputs: AnalysisInputs) -> int:
    if not inputs.scores:
        logger.error("No scores found. Run the build pipeline first.")
        return 1

    analyzer = ParameterAnalyzer(inputs, _text_rows)
    analyzer.analyze_all()
    logger.info("Parameter analysis report generated in output/analysis/")
    return 0