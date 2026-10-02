class BuildView extends SectionView {
    constructor() {
        super("build-container", "external_modules.build.frontend.build");
    }

    afterInit() {
        this.limitDisplay = this.container?.querySelector("#prepare-limit-display");
        this.batchToggle = this.container?.querySelector("#batch-toggle");
        this.currentLimit = 100;
        if (this.limitDisplay) {
            this.limitDisplay.textContent = `Current: ${this.currentLimit}`;
        }
    }

    destroy() {
        super.destroy();
        this.limitDisplay = null;
        this.batchToggle = null;
    }

    _getBatch() {
        return this.batchToggle ? this.batchToggle.checked : false;
    }

    async _buildPrepare(body) {
        return api._post("/build/prepare", body);
    }

    async _deleteVectors() {
        return api._post("/build/delete-vectors");
    }

    bindActions() {
        super.bindActions();
        const container = this.container;
        if (!container) {
            return;
        }

        container.querySelectorAll("[data-prepare-limit]")
            .forEach((btn) => {
                btn.addEventListener("click", () => {
                    this.currentLimit = parseInt(btn.dataset.prepareLimit, 10);
                    if (this.limitDisplay) {
                        this.limitDisplay.textContent = `Current: ${this.currentLimit === 0 ? "All" : this.currentLimit}`;
                    }
                });
            });
    }

    async handleAction(action) {
        this.logger.info(`Starting: ${action}...`);
        try {
            let result;
            switch (action) {
                case "prepare-split":
                    result = await this._buildPrepare({ mode: "split", limit: this.currentLimit, batch: this._getBatch() });
                    this._renderResponse(result);
                    return;
                case "prepare-full":
                    result = await this._buildPrepare({ mode: "full" });
                    this._renderResponse(result);
                    return;
                case "prepare-all":
                    result = await this._buildPrepare({ mode: "all", limit: this.currentLimit, batch: this._getBatch() });
                    this._renderResponse(result);
                    return;
                case "delete-vectors":
                    if (!confirm("This will DELETE the full vector files, the vector maps, and every split category except image/ from disk. Recovery requires re-analysis. This cannot be undone. Continue?")) {
                        this.logger.info("Delete vectors cancelled by user.");
                        return;
                    }
                    result = await this._deleteVectors();
                    this._renderResponse(result);
                    return;
                default:
                    this.logger.info(`Unknown action: ${action}`);
            }
        } catch (e) {
            this.logger.error("Build action error", e);
        }
    }
}

window.Sections = window.Sections || {};
window.Sections.build = BuildView;