class TrainingView {
    init(params) {
        this.container = document.getElementById("training-container");
        const logArea = this.container?.querySelector("#log-area");
        this.logger = FrontendLogger.create("external_modules.training.frontend.training", {
            target: () => logArea,
        });
        this.bindActions();
    }

    async _trainingTrain() {
        return api._post("/training/train");
    }

    async _trainingHpo(body = {}) {
        return api._post("/training/hpo", body);
    }

    bindActions() {
        const container = this.container;
        if (!container) return;
        container.querySelectorAll("[data-action]").forEach((btn) => {
            btn.addEventListener("click", () => this.handleAction(btn.dataset.action));
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
                case "train-top":
                    result = await this._trainingTrain();
                    this._renderResponse(result);
                    return;
                case "hpo-cycle":
                    result = await this._trainingHpo();
                    this._renderResponse(result);
                    return;
                default:
                    this.logger.info(`Unknown action: ${action}`);
            }
        } catch (e) {
            this.logger.error("Training action error", e);
        }
    }
}

window.Sections = window.Sections || {};
window.Sections.training = TrainingView;