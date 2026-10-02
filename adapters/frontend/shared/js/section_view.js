/* Base class for the section views (build, database, training, analyze).
   Owns the container lookup, the scoped logger, the data-action and clear-log
   wiring, and the log echo that every one of those sections repeats. */
class SectionView {
    constructor(containerId, loggerName) {
        this.containerId = containerId;
        this.loggerName = loggerName;
        this.container = null;
    }

    init(params) {
        this.container = document.getElementById(this.containerId);
        const logArea = this.container?.querySelector("#log-area");
        this.logger = FrontendLogger.create(this.loggerName, {
            target: () => logArea,
        });
        this.bindActions();
        this.afterInit(params);
    }

    /* Subclass hook for setup that needs the action buttons already wired. */
    afterInit(params) {}

    bindActions() {
        const container = this.container;
        if (!container) {
            return;
        }

        container.querySelectorAll("[data-action]").forEach((btn) => {
            btn.addEventListener("click", () => this.handleAction(btn.dataset.action));
        });

        const clearLogBtn = container.querySelector("#clear-log-btn");
        if (clearLogBtn) {
            clearLogBtn.addEventListener("click", () => this.logger.clear());
        }
    }

    _renderResponse(res) {
        (res.log || []).forEach((line) => this.logger.info(line));
        this.logger.info(`Result: ${JSON.stringify(res.result)}`);
    }

    destroy() {
        this.container = null;
    }
}