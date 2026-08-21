from ...core.io.serialization import load_single_jsonl
from ...core.filesystem.paths import vectors_file, text_data_file
from ...core.observability.logger import get_logger
from ...domain.training.parameter_analysis import ParameterAnalyzer

logger = get_logger(__name__)


def run_parameter_analysis() -> int:
    vectors = list(load_single_jsonl(vectors_file))
    text_data = list(load_single_jsonl(text_data_file))

    if not vectors or not text_data:
        logger.error("vectors.jsonl or text_data.jsonl is empty — run build pipeline first")
        return 1

    analyzer = ParameterAnalyzer(vectors, text_data)
    analyzer.analyze_all()
    logger.info("Parameter analysis report generated in output/analysis/")
    return 0
