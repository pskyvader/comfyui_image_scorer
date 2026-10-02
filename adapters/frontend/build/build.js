class BuildView {
    init(params) {
        this.container = document.getElementById("build-container");
        const logArea = this.container?.querySelector("#log-area");
        this.logger = FrontendLogger.create("external_modules.build.frontend.build", {
            target: () => logArea,
        });
        this.limitDisplay = this.container?.querySelector("#prepare-limit-display");
        this.batchToggle = this.container?.querySelector("#batch-toggle");
        this.currentLimit = 100;
        if (this.limitDisplay) {
            this.limitDisplay.textContent = `Current: ${this.currentLimit}`;
        }
        this.bindActions();
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
        const container = this.container;
        if (!container) {
            return;
        }

        container.querySelectorAll("[data-action]")
            .forEach((btn) => {
                btn.addEventListener("click", () => this.handleAction(btn.dataset.action));
            });

        container.querySelectorAll("[data-prepare-limit]")
            .forEach((btn) => {
                btn.addEventListener("click", () => {
                    this.currentLimit = parseInt(btn.dataset.prepareLimit, 10);
                    if (this.limitDisplay) {
                        this.limitDisplay.textContent = `Current: ${this.currentLimit === 0 ? "All" : this.currentLimit}`;
                    }
                });
            });

        const clearBtn = container.querySelector("#clear-log-btn");
        if (clearBtn) {
            clearBtn.addEventListener("click", () => this.logger.clear());
        }
    }

    _renderResponse(res) {
        (res.log || []).forEach((line) => this.logger.info(line));
        this.logger.info(`Result: ${JSON.stringify(res.result)}`);
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