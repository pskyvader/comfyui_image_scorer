"""Maps API - endpoints for chain visualizations (graph data)."""

import time

from flask import Blueprint, jsonify

from ....core.observability.logger import get_logger, ModuleLogger
from ..deps import ServerDeps, get_server_deps

maps_bp = Blueprint("maps_v2", __name__, url_prefix="/api/maps")
logger: ModuleLogger = get_logger(__name__)


@maps_bp.route("/graph-data", methods=["GET"])
def get_graph_data():
    _start = time.perf_counter()
    try:
        deps = get_server_deps()
        if deps.graph.is_cache_stale():
            deps.graph.rebuild_from_database()

        stats = deps.graph.get_graph_stats()
        node_to_height: dict[str, int] = {}
        for proxy, _node_list in deps.graph.get_all_chains():
            for node_proxy in proxy.nodes:
                filename = node_proxy.filename
                if (
                    filename not in node_to_height
                    or proxy.length > node_to_height[filename]
                ):
                    node_to_height[filename] = proxy.length

        img_dict = {img["filename"]: img for img in deps.image_repo.get_all_images()}
        nodes = []
        for node in deps.graph.get_all_nodes():
            filename = node.filename
            img_data = img_dict.get(filename)
            comp = node.get_component()
            nodes.append(
                {
                    "id": filename,
                    "score": round(float(img_data["score"]), 4) if img_data else 0.5,
                    "height": node_to_height.get(filename, 0),
                    "component": comp.id if comp else None,
                    "comparison_count": (
                        int(img_data["comparison_count"]) if img_data else 0
                    ),
                    "is_top": node.is_top(),
                    "is_bottom": node.is_bottom(),
                }
            )

        edges = [
            {"source": winner, "target": loser, "weight": 1.0}
            for winner, loser in deps.graph.get_all_links()
        ]
        all_components = deps.graph.get_all_components()
        component_members = {
            comp.id: [n.filename for n in comp.nodes] for comp in all_components
        }
        chains = []
        for chain_proxy, _ in deps.graph.get_all_chains():
            comp = chain_proxy.get_component()
            chains.append(
                {
                    "id": chain_proxy.id,
                    "component": comp.id if comp else None,
                    "nodes": [n.filename for n in chain_proxy.nodes],
                }
            )

        result = jsonify(
            {
                "nodes": nodes,
                "edges": edges,
                "components": component_members,
                "chains": chains,
                "stats": {
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                    "total_components": len(all_components),
                    "total_chains": stats.get("total_chains", 0),
                },
            }
        )
        return result
    except Exception as exc:
        logger.error("Error in get_graph_data: %s", exc, exc_info=True)
        result = jsonify({"error": str(exc)}), 500
        return result


def register_maps_routes(app, deps: ServerDeps) -> None:
    app.extensions["server_deps"] = deps
    app.register_blueprint(maps_bp)
