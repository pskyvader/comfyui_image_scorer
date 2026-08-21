from pathlib import Path

from ...core.io.serialization import load_single_jsonl
from ...core.filesystem.paths import vectors_file, text_data_file, maps_dir
from ...core.observability.logger import get_logger
from ...domain.training.matrix_analysis import MatrixAnalyzer

logger = get_logger(__name__)


def run_matrix_analysis() -> int:
    vectors = list(load_single_jsonl(vectors_file))
    text_data = list(load_single_jsonl(text_data_file))

    if not vectors or not text_data:
        logger.error("vectors.jsonl or text_data.jsonl is empty — run build pipeline first")
        return 1

    scores = [v.get("score", 0) for v in vectors]
    analyzer = MatrixAnalyzer(scores, text_data)
    analyzer.build_matrix()
    analyzer.calculate_statistics()

    output_path = str(Path(maps_dir) / "matrix_analysis.json")
    analyzer.export_to_json(output_path)
    logger.info("Matrix analysis saved to %s", output_path)
    return 0
