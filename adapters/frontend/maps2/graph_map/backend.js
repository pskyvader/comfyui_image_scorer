const maps2BackendLogger = FrontendLogger.create("maps2.graph_map.backend");

globalThis.ChainMapUI.prototype.loadData = async function () {
    if (this.loader) {
        this.loader.classList.remove("hidden");
    }
    try {
        const data = await globalThis.api._get("/maps/graph-data");
        console.log("Backend: " + data.nodes.length + " nodes, " + data.edges.length + " edges, " + (data.chains ? data.chains.length : 0) + " chains");
        this.rawData = data;
        this.applyFilters();
    } catch (e) {
        maps2BackendLogger.error("Failed to load graph data", e);
        if (this.loader) {
            this.loader.classList.add("hidden");
        }
        throw e;
    }
};
