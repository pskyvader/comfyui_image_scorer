const STATS_FORMAT = new Intl.NumberFormat();

function formatNumber(value) {
    if (value === null || value === undefined) return "-";
    return STATS_FORMAT.format(Math.round(value * 10000) / 10000);
}

function formatTimestamp(value) {
    if (!value) return "-";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "-" : parsed.toLocaleString();
}

class AnalyzeView extends SectionView {
    constructor() {
        super("analyze-container", "external_modules.analyze.frontend.analyze");
    }

    afterInit() {
        this.resultPanel = this.container?.querySelector("#result-panel");
        this.resultContent = this.container?.querySelector("#result-content");
        this.refreshStats();
    }

    destroy() {
        super.destroy();
        this.resultPanel = null;
        this.resultContent = null;
    }

    async _getStats() {
        return api._get("/analyze/stats");
    }

    async _analyzeParameters() {
        return api._post("/analyze/analyze-parameters");
    }

    async _analyzeMatrix() {
        return api._post("/analyze/analyze-matrix");
    }

    bindActions() {
        super.bindActions();
        const container = this.container;
        if (!container) return;

        const refreshBtn = container.querySelector("#refresh-stats-btn");
        if (refreshBtn) refreshBtn.addEventListener("click", () => this.refreshStats());

        const clearResultBtn = container.querySelector("#clear-result-btn");
        if (clearResultBtn) clearResultBtn.addEventListener("click", () => this.clearResult());
    }

    showResult() {
        if (this.resultPanel) this.resultPanel.style.display = "block";
        if (this.resultContent) this.resultContent.innerHTML = "";
    }

    clearResult() {
        if (this.resultPanel) this.resultPanel.style.display = "none";
        if (this.resultContent) this.resultContent.innerHTML = "";
    }

    _renderResponse(res) {
        (res.log || []).forEach((line) => this.logger.info(line));
        if (!res.stats) {
            this.showResult();
            const pre = document.createElement("pre");
            pre.className = "text-xs text-green-400";
            pre.textContent = JSON.stringify(res.result ?? {}, null, 2);
            this.resultContent?.appendChild(pre);
            return;
        }
        this._renderStats(res.stats);
    }

    async refreshStats() {
        this.logger.info("Loading stats...");
        try {
            const data = await this._getStats();
            (data.log || []).forEach((line) => this.logger.info(line));
            if (data.stats) {
                this._renderStats(data.stats);
            } else {
                this.logger.error("Stats response carried no payload");
            }
        } catch (e) {
            this.logger.error("Failed to load analysis stats", e);
        }
    }

    _renderStats(stats) {
        this.showResult();
        if (!this.resultContent) return;
        this.resultContent.innerHTML = "";
        this._renderSummary(this.resultContent, stats);
        this._renderStructure(this.resultContent, stats);
        this._renderCharts(this.resultContent, stats);
        this._renderTables(this.resultContent, stats);
    }

    _renderCardGrid(root, cards) {
        const grid = document.createElement("div");
        grid.className = "stat-grid";
        cards.forEach((card) => {
            const box = document.createElement("div");
            box.className = "stat-card";
            const value = document.createElement("div");
            value.className = "stat-value";
            value.textContent = card.value;
            const label = document.createElement("div");
            label.className = "stat-label";
            label.textContent = card.label;
            box.appendChild(value);
            box.appendChild(label);
            grid.appendChild(box);
        });
        root.appendChild(grid);
    }

    _renderSummary(root, stats) {
        const total = stats.total_nodes || 0;
        const readyPercent = total ? ((stats.sigma_below_threshold || 0) / total) * 100 : 0;
        const cards = [
            { label: "Images", value: formatNumber(total) },
            { label: "Ranked", value: formatNumber(stats.ranked) },
            { label: "Unranked", value: formatNumber(stats.unranked) },
            { label: "Mean score", value: formatNumber(stats.score?.mean) },
            { label: "Ready (σ < thr)", value: formatNumber(stats.sigma_below_threshold) },
            { label: "Ready share", value: `${readyPercent.toFixed(1)}%` },
            { label: "Above threshold", value: formatNumber(stats.sigma_above_threshold) },
            { label: "σ threshold", value: formatNumber(stats.sigma_threshold) },
            { label: "Ready (wins+losses)", value: formatNumber(stats.ready_count) },
            { label: "Single win", value: formatNumber(stats.single_win_count) },
            { label: "Single loss", value: formatNumber(stats.single_loss_count) },
        ];
        this._renderCardGrid(root, cards);
    }

    _renderStructure(root, stats) {
        const structure = stats.structure;
        if (!structure) return;
        const cards = [
            { label: "Comparisons", value: formatNumber(structure.total_links) },
            { label: "Components", value: formatNumber(structure.total_components) },
            { label: "Chains", value: formatNumber(structure.total_chains) },
            { label: "Longest chain", value: formatNumber(structure.longest_chain_depth) },
            { label: "Top nodes", value: formatNumber(structure.top_nodes_count) },
            { label: "Bottom nodes", value: formatNumber(structure.bottom_nodes_count) },
            { label: "Graph built", value: formatTimestamp(structure.built_at) },
        ];
        this._renderCardGrid(root, cards);
    }

    _renderCharts(root, stats) {
        const grid = document.createElement("div");
        grid.className = "chart-grid";
        this._renderChart(grid, "Score distribution", stats.score, {});
        this._renderChart(grid, "Rating sigma distribution", stats.rating_sigma, {
            threshold: stats.sigma_threshold,
            thresholdLabel: `σ ${stats.sigma_threshold}`,
        });
        this._renderChart(grid, "Rating mu distribution", stats.rating_mu, {});
        this._renderChart(grid, "Link count distribution", stats.link_count, {});
        root.appendChild(grid);    }

    _renderChart(root, title, distribution, options) {
        const d3 = globalThis.d3;
        const box = document.createElement("div");

        const heading = document.createElement("div");
        heading.className = "chart-title";
        heading.textContent = title;
        box.appendChild(heading);

        const buckets = distribution?.buckets || [];
        if (!d3 || !buckets.length) {
            const empty = document.createElement("div");
            empty.className = "chart-empty";
            empty.textContent = "No data.";
            box.appendChild(empty);
            root.appendChild(box);
            return;
        }

        const width = 280;
        const height = 160;
        const margin = { top: 10, right: 6, bottom: 26, left: 44 };
        const innerWidth = width - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;

        const svg = d3.select(box).append("svg")
            .attr("class", "chart-svg")
            .attr("viewBox", `0 0 ${width} ${height}`)
            .attr("preserveAspectRatio", "xMidYMid meet")
            .style("width", "100%")
            .style("height", `${height}px`);

        const plot = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);
        const maxCount = d3.max(buckets, (b) => b.count) || 1;
        const x = d3.scaleBand().range([0, innerWidth]).padding(0.18);
        x.domain(buckets.map((_, i) => i));
        const y = d3.scaleLinear().domain([0, maxCount]).nice().range([innerHeight, 0]);

        plot.append("g")
            .attr("class", "grid")
            .call(d3.axisLeft(y).ticks(4).tickSize(-innerWidth).tickFormat(""))
            .call((g) => g.select(".domain").remove());

        plot.append("g")
            .attr("class", "axis")
            .call(d3.axisLeft(y).ticks(4).tickFormat(d3.format("~s")))
            .call((g) => g.select(".domain").remove());

        plot.append("g")
            .attr("class", "axis")
            .attr("transform", `translate(0,${innerHeight})`)
            .call(d3.axisBottom(x).tickFormat((i) => {
                const bucket = buckets[i];
                const mid = (bucket.lower + bucket.upper) / 2;
                return Number.isInteger(mid) ? String(mid) : mid.toFixed(Math.abs(mid) < 10 ? 2 : 1);
            }))
            .call((g) => g.select(".domain").remove());

        plot.selectAll("rect.bar")
            .data(buckets)
            .join("rect")
            .attr("class", "bar")
            .attr("x", (_, i) => x(i))
            .attr("y", (b) => y(b.count))
            .attr("width", x.bandwidth())
            .attr("height", (b) => innerHeight - y(b.count))
            .append("title")
            .text((b) => `${b.lower.toFixed(3)} – ${b.upper.toFixed(3)}: ${STATS_FORMAT.format(b.count)}`);

        if (options.threshold !== undefined && options.threshold !== null) {
            const span = distribution.max - distribution.min;
            if (span > 0) {
                const tx = x((options.threshold - distribution.min) / span * (buckets.length - 1));
                plot.append("line")
                    .attr("class", "threshold")
                    .attr("x1", tx).attr("x2", tx)
                    .attr("y1", 0).attr("y2", innerHeight);
                plot.append("text")
                    .attr("class", "threshold-label")
                    .attr("x", tx).attr("y", -2)
                    .attr("text-anchor", "middle")
                    .text(options.thresholdLabel);
            }
        }

        root.appendChild(box);
    }

    _renderTables(root, stats) {
        this._renderTable(root, "Highest scoring", stats.top);
        this._renderTable(root, "Lowest scoring", stats.bottom);
    }

    _renderTable(root, title, rows) {
        const box = document.createElement("div");

        const heading = document.createElement("div");
        heading.className = "chart-title";
        heading.textContent = title;
        box.appendChild(heading);

        if (!rows?.length) {
            const empty = document.createElement("div");
            empty.className = "chart-empty";
            empty.textContent = "No data.";
            box.appendChild(empty);
            root.appendChild(box);
            return;
        }

        const table = document.createElement("table");
        table.className = "data-table";
        table.innerHTML = "<thead><tr><th>File</th><th>Score</th><th>μ</th><th>σ</th><th>Comps</th></tr></thead>";
        const body = document.createElement("tbody");
        rows.forEach((row) => {
            const tr = document.createElement("tr");
            const cells = [
                { text: row.filename, className: "filename" },
                { text: row.score.toFixed(4), className: "num" },
                { text: row.rating_mu.toFixed(2), className: "num" },
                { text: row.rating_sigma.toFixed(2), className: "num" },
                { text: String(row.link_count), className: "num" },
            ];
            cells.forEach((cell) => {
                const td = document.createElement("td");
                td.className = cell.className;
                td.textContent = cell.text;
                td.title = cell.text;
                tr.appendChild(td);
            });
            body.appendChild(tr);
        });
        table.appendChild(body);
        box.appendChild(table);
        root.appendChild(box);
    }

    async handleAction(action) {
        this.logger.info(`Starting: ${action}...`);
        try {
            let result;
            switch (action) {
                case "analyze-parameters":
                    result = await this._analyzeParameters();
                    this._renderResponse(result);
                    return;
                case "analyze-matrix":
                    result = await this._analyzeMatrix();
                    this._renderResponse(result);
                    return;
                default:
                    this.logger.info(`Unknown action: ${action}`);
            }
        } catch (e) {
            this.logger.error("Analysis action error", e);
        }
    }
}

window.Sections = window.Sections || {};
window.Sections.analyze = AnalyzeView;
