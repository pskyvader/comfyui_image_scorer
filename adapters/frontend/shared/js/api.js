// Base API client - provides shared fetch utilities
class Api {
    constructor(baseUrl = "") {
        this.apiBase = `${baseUrl}/api`;
    }

    async _fetch(path, options = {}) {
        const response = await fetch(`${this.apiBase}${path}`, {
            ...options,
            headers: options.body ? { "Content-Type": "application/json" } : {},
        });
        if (!response.ok) {
            let detail = "";
            try { const e = await response.json(); detail = e.error || e.message || ""; } catch (err) { console.warn("Failed to parse error response:", err); }
            throw new Error(`${response.status}${detail ? ": " + detail : ""}`);
        }
        return await response.json();
    }

    async _get(path) { return this._fetch(path); }
    async _post(path, body = {}) { return this._fetch(path, { method: "POST", body: JSON.stringify(body) }); }
}

const api = new Api();
globalThis.api = api;
