class AnalyzeView {
    init(params) {
        this.container = document.getElementById("analyze-container");
        const logArea = this.container?.querySelector("#log-area");
        this.logger = FrontendLogger.create("external_modules.analyze.frontend.analyze", {
            target: () => logArea,
        });
        this.resultPanel = this.container?.querySelector("#result-panel");
        this.resultContent = this.container?.querySelector("#result-content");
        this.bindActions();
        this.refreshStats();
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
        const container = this.container;
        if (!container) return;

        container.querySelectorAll("[data-action]").forEach(btn => {
            btn.addEventListener("click", () => this.handleAction(btn.dataset.action));
        });

        const refreshBtn = container.querySelector("#refresh-stats-btn");
        if (refreshBtn) refreshBtn.addEventListener("click", () => this.refreshStats());

        const clearLogBtn = container.querySelector("#clear-log-btn");
        if (clearLogBtn) clearLogBtn.addEventListener("click", () => this.logger.clear());

        const clearResultBtn = container.querySelector("#clear-result-btn");
        if (clearResultBtn) clearResultBtn.addEventListener("click", () => this.clearResult());
    }

    showResult(html) {
        if (this.resultPanel) this.resultPanel.style.display = "block";
        if (this.resultContent) this.resultContent.innerHTML = html;
    }

    clearResult() {
        if (this.resultPanel) this.resultPanel.style.display = "none";
        if (this.resultContent) this.resultContent.innerHTML = "";
    }

    _renderResponse(res) {
        (res.log || []).forEach((line) => this.logger.info(line));
        this.showResult(`<pre class="text-xs text-green-400">${JSON.stringify(res.result ?? {}, null, 2)}</pre>`);
    }

    async refreshStats() {
        this.logger.info("Loading stats...");
        try {
            const data = await this._getStats();
            (data.log || []).forEach((line) => this.logger.info(line));
        } catch (e) {
            this.logger.error("Failed to load analysis stats", e);
        }
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