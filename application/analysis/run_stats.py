"""Print the whole-graph ranking summary.

The measurements come from ``describe_graph`` so the CLI text, the analyze
endpoint payload, and the comparison pair payload all report one set of
numbers. Callers that already hold the payload use ``print_stats`` directly
instead of collecting it twice.
"""

from ...domain.comparison.algorithm.view import (
    describe_graph,
    Distribution,
    GraphStats,
    RankedExtremes,
)
from ...domain.ports.graph import CrystalGraphPort


def _print_distribution(title: str, distribution: Distribution) -> None:
    print(f"{title}:")
    print(
        f"  min={distribution['min']:.4f}  max={distribution['max']:.4f}  "
        f"mean={distribution['mean']:.4f}"
    )
    for bucket in distribution["buckets"]:
        print(f"  {bucket['lower']:.3f}-{bucket['upper']:.3f}: {bucket['count']}")


def _print_extremes(title: str, rows: list[RankedExtremes]) -> None:
    print(f"{title}:")
    for row in rows:
        print(
            f"  {row['filename']:<40s} score={row['score']:.4f}  "
            f"mu={row['rating_mu']:.2f}  sigma={row['rating_sigma']:.2f}  "
            f"links={row['link_count']}"
        )


def print_stats(stats: GraphStats) -> None:
    print("=" * 60)
    print("Image Scoring System — Stats")
    print("=" * 60)
    print(f"Total nodes:         {stats['total_nodes']}")
    print(f"Ranked images:      {stats['ranked']}")
    print(f"Unranked images:    {stats['unranked']}")
    print(
        f"Sigma threshold:    {stats['sigma_threshold']:.2f} "
        f"({stats['sigma_below_threshold']} ready, {stats['sigma_above_threshold']} above)"
    )
    print()
    _print_distribution("Score distribution", stats["score"])
    print()
    _print_distribution("Rating mu distribution", stats["rating_mu"])
    print()
    _print_distribution("Rating sigma distribution", stats["rating_sigma"])
    print()
    _print_distribution("Link count distribution", stats["link_count"])
    print()
    _print_extremes("Top 10 images", stats["top"])
    print()
    _print_extremes("Bottom 10 images", stats["bottom"])


def run_stats(graph: CrystalGraphPort) -> int:
    print_stats(describe_graph(graph))
    return 0
