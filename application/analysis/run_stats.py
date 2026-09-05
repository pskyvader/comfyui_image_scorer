from typing import Any

from ...core.observability.logger import get_logger

logger = get_logger(__name__)


def _distribute(values: list[float], bins: int) -> dict[str, int]:
    if not values:
        return {}
    mn, mx = min(values), max(values)
    if mx == mn:
        return {f"{mn:.3f}": len(values)}
    step = (mx - mn) / bins
    buckets: dict[str, int] = {}
    for i in range(bins):
        lo = mn + i * step
        hi = lo + step
        label = f"{lo:.3f}-{hi:.3f}"
        if i == bins - 1:
            buckets[label] = sum(1 for v in values if lo <= v <= hi)
        else:
            buckets[label] = sum(1 for v in values if lo <= v < hi)
    return buckets


def run_stats(graph: Any) -> int:
    images = [node.data for node in graph.get_all_nodes()]
    comparisons = [link.data for link in graph.get_all_links()]

    scores = [img.get("score", 0) for img in images]
    mus = [img.get("rating_mu", 0) for img in images]
    sigmas = [img.get("rating_sigma", 0) for img in images]
    comp_counts = [img.get("comparison_count", 0) for img in images]

    score_buckets = _distribute(scores, 10)
    mu_buckets = _distribute(mus, 10)
    sigma_buckets = _distribute(sigmas, 10)
    comp_buckets = _distribute(comp_counts, 10)

    top = sorted(images, key=lambda x: x.get("score", 0), reverse=True)[:10]
    bottom = sorted(images, key=lambda x: x.get("score", 0))[:10]

    print("=" * 60)
    print("Image Scoring System — Stats")
    print("=" * 60)
    print(f"Total images:       {len(images)}")
    print(f"Total comparisons:  {len(comparisons)}")
    print(f"Score range:        {min(scores):.4f} – {max(scores):.4f}")
    print(f"Mean score:         {sum(scores) / len(scores) if scores else 0:.4f}")
    print()
    print("Score distribution:")
    for bucket, count in sorted(score_buckets.items()):
        print(f"  {bucket}: {count}")
    print()
    print("Rating mu distribution:")
    for bucket, count in sorted(mu_buckets.items()):
        print(f"  {bucket}: {count}")
    print()
    print("Rating sigma distribution:")
    for bucket, count in sorted(sigma_buckets.items()):
        print(f"  {bucket}: {count}")
    print()
    print("Comparison count distribution:")
    for bucket, count in sorted(comp_buckets.items()):
        print(f"  {bucket}: {count}")
    print()
    print("Top 10 images:")
    for img in top:
        print(
            f"  {img['filename']:<40s} score={img.get('score', 0):.4f}  "
            f"mu={img.get('rating_mu', 0):.2f}  sigma={img.get('rating_sigma', 0):.2f}  "
            f"comps={img.get('comparison_count', 0)}"
        )
    print()
    print("Bottom 10 images:")
    for img in bottom:
        print(
            f"  {img['filename']:<40s} score={img.get('score', 0):.4f}  "
            f"mu={img.get('rating_mu', 0):.2f}  sigma={img.get('rating_sigma', 0):.2f}  "
            f"comps={img.get('comparison_count', 0)}"
        )

    return 0
