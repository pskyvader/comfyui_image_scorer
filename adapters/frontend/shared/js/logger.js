class ScopedFrontendLogger {
    constructor(sourceName, options = {}) {
        this.sourceName = sourceName;
        this.options = { ...options };
    }

    debug(message, ...details) {
        FrontendLogger.log(this.sourceName, "debug", message, this.options, details);
    }

    info(message, ...details) {
        FrontendLogger.log(this.sourceName, "info", message, this.options, details);
    }

    warn(message, ...details) {
        FrontendLogger.log(this.sourceName, "warn", message, this.options, details);
    }

    error(message, ...details) {
        FrontendLogger.log(this.sourceName, "error", message, this.options, details);
    }

    success(message, ...details) {
        FrontendLogger.log(this.sourceName, "info", message, this.options, details);
        Utils.showToast(message, "success");
    }

    clear() {
        const target = FrontendLogger.resolveTarget(this.options.target);
        if (target) {
            target.innerHTML = "";
        }
    }
}

class FrontendLogger {
    static consoleLevel = "debug";
    static defaultMaxEntries = 100;
    static progressIndicators = ["%", "|", "img/s", "items/s", "[00:", "it/s"];

    static create(sourceName, options = {}) {
        return new ScopedFrontendLogger(sourceName, options);
    }

    static log(sourceName, level, message, options = {}, details = []) {
        const targetMessage = details.length > 0
            ? `${message} ${details.map((detail) => this.serializeDetail(detail)).join(" ")}`
            : message;
        this.writeConsole(sourceName, level, message, details);
        this.writeTarget(sourceName, level, targetMessage, options);

        if (level === "error") {
            Utils.showToast(message, "error");
        } else if (level === "warn" || level === "info") {
            Utils.showToast(message, "info");
        }
    }

    static serializeDetail(detail) {
        if (detail instanceof Error) {
            return detail.stack || detail.message;
        }
        if (typeof detail === "string") {
            return detail;
        }
        try {
            return JSON.stringify(detail);
        } catch {
            return String(detail);
        }
    }

    static writeConsole(sourceName, level, renderedMessage, details) {
        if (this.levelValue(level) < this.levelValue(this.consoleLevel)) {
            return;
        }

        const consoleMethod = this.consoleMethod(level);
        consoleMethod(`[${sourceName}] ${renderedMessage}`, ...details);
    }

    static writeTarget(sourceName, level, renderedMessage, options) {
        const target = this.resolveTarget(options.target);
        if (!target) {
            return;
        }

        const isProgress = options.replaceProgress === true && this.isProgressMessage(renderedMessage);
        const displayMessage = `[${new Date().toLocaleTimeString()}] [${sourceName}] ${renderedMessage}`;
        const lastChild = target.lastElementChild;

        if (isProgress && lastChild && lastChild.dataset?.isProgress === "true") {
            lastChild.textContent = displayMessage;
        } else {
            const line = document.createElement("div");
            line.textContent = displayMessage;
            line.dataset.isProgress = isProgress ? "true" : "false";
            target.appendChild(line);
        }

        const maxEntries = Number.isInteger(options.maxEntries)
            ? options.maxEntries
            : this.defaultMaxEntries;
        while (target.children.length > maxEntries) {
            target.removeChild(target.firstElementChild);
        }

        target.scrollTop = target.scrollHeight;
    }

    static resolveTarget(target) {
        if (typeof target === "function") {
            return target();
        }
        return target || null;
    }

    static isProgressMessage(message) {
        return this.progressIndicators.some((indicator) => message.includes(indicator));
    }

    static levelValue(level) {
        const values = {
            debug: 10,
            info: 20,
            warn: 30,
            error: 40,
        };
        return values[level] ?? values.info;
    }

    static consoleMethod(level) {
        const methods = {
            debug: console.debug ? console.debug.bind(console) : console.log.bind(console),
            info: console.info ? console.info.bind(console) : console.log.bind(console),
            warn: console.warn ? console.warn.bind(console) : console.log.bind(console),
            error: console.error ? console.error.bind(console) : console.log.bind(console),
        };
        return methods[level] ?? console.log.bind(console);
    }
}

window.FrontendLogger = FrontendLogger;
