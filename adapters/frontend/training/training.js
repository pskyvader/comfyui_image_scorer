class TrainingView extends SectionView {
    constructor() {
        super("training-container", "external_modules.training.frontend.training");
    }

    async _trainingTrain() {
        return api._post("/training/train");
    }

    async _trainingHpo(body = {}) {
        return api._post("/training/hpo", body);
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