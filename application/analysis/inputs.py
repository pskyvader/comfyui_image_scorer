"""Inputs shared by the parameter and matrix analyzers.

Both artifacts are keyed by filename, so the analyzers join on that key instead
of on row position. Scores come from the training loader's own three-tier
resolver, and prompt text comes from the ranked database, which is more complete
than the text sidecar: `prompt_tags` covers more images than
`text_data.jsonl`'s `positive_prompt`, and the two do not fully agree. The
sidecar remains the fallback for images with no stored prompt tag.
"""

from dataclasses import dataclass

from ...domain.ports.graph import CrystalGraphPort
from ...domain.ports.loading import TrainingLoader


@dataclass(frozen=True)
class AnalysisInputs:
    """Filename-keyed scores and prompt text for one analysis run."""

    scores: dict[str, float]
    prompt_tags: dict[str, str]


def collect_analysis_inputs(
    graph: CrystalGraphPort,
    loader: TrainingLoader,
) -> AnalysisInputs:
    """Read the scores and prompt tags an analysis run needs.

    ``vectors.jsonl`` is deliberately not consulted. It holds one embedding per
    row and no score, so the analyzers have no reason to read a file several
    gigabytes wide.
    """
    prompt_tags: dict[str, str] = {}
    for node in graph.get_all_nodes():
        tags = node.prompt_tags
        if tags:
            prompt_tags[node.filename] = tags
    return AnalysisInputs(scores=dict(loader.load_scores()), prompt_tags=prompt_tags)