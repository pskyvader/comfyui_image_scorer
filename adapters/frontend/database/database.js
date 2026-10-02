class DatabaseView extends SectionView {
    constructor() {
        super("database-container", "external_modules.database.frontend.database");
    }

    async _dbAction(action, body) {
        const actions = {
            "rebuild-db": "rebuild-db",
            "recalculate": "recalculate",
            "cleanup": "cleanup",
        };
        const path = actions[action];
        if (!path) throw new Error(`Unknown action: ${action}`);
        return api._post(`/database/${path}`, body);
    }

    async _fileAction(action, body) {
        const actions = {
            "remove-generated-models": "remove-generated-models",
            "remove-vector-maps": "remove-vector-maps",
            "remove-downloaded-models": "remove-downloaded-models",
            "download-models": "download-models",
            "cleanup-files": "cleanup",
        };
        const path = actions[action];
        if (!path) throw new Error(`Unknown action: ${action}`);
        return api._post(`/files/${path}`, body);
    }

    async handleAction(action) {
        this.logger.info(`Starting: ${action}...`);
        try {
            let result;
            switch (action) {
                case "rebuild-db":
                    result = await this._dbAction("rebuild-db");
                    this._renderResponse(result);
                    return;
                case "recalculate":
                    result = await this._dbAction("recalculate");
                    this._renderResponse(result);
                    return;
                case "cleanup":
                    result = await this._dbAction("cleanup");
                    this._renderResponse(result);
                    return;
                case "remove-generated-models":
                case "remove-vector-maps":
                case "remove-downloaded-models":
                case "download-models":
                    result = await this._fileAction(action);
                    this._renderResponse(result);
                    return;
                case "cleanup-files": {
                    const limit = parseInt(this.container.querySelector("#files-limit")?.value || "0", 10);
                    result = await this._fileAction("cleanup-files", { limit });
                    this._renderResponse(result);
                    return;
                }
                default:
                    this.logger.info(`Unknown action: ${action}`);
            }
        } catch (e) {
            this.logger.error("Database action error", e);
        }
    }
}

window.Sections = window.Sections || {};
window.Sections.database = DatabaseView;