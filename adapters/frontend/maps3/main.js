/**
 * Maps3 — Score-Ranked Graph Visualization
 *
 * Same graph data as maps2 (`/api/maps/graph-data`), different layout: nodes
 * are sorted top-to-bottom by score (1.0 top, 0.0 bottom), equal scores spread
 * horizontally by rank within their score group, and components form
 * horizontal diamond-like bands. Vertical spring forces are near zero;
 * horizontal repulsion/attraction are active.
 */

const maps3Logger = FrontendLogger.create("maps3.main");

// Scores within this distance count as equal and share one horizontal row.
const SCORE_EPSILON = 0.005;

globalThis.ScoreMapUI = class {
    constructor() {
        this.rawData = null;
        this.canvas = null;
        this.ctx = null;
        this.nodes = [];
        this.links = [];
        this.rows = [];
        this.worldHalfWidth = 1000;
        this.worldHalfHeight = 1000;
        this._scale = 1;
        this._tx = 0;
        this._ty = 0;
        this._alpha = 1;
        this._rafId = null;
        this._dragging = false;
        this._dragStart = null;
        this._hoverNode = null;
        this._resizeObserver = null;
    }

    async init() {
        this.ce();
        if (!this.container || !this.canvas) {
            return;
        }
        this._bindControls();
        this._bindPointer();
        await this.loadData();
    }

    ce() {
        this.container = document.getElementById("maps3-container");
        this.canvas = document.getElementById("maps3-canvas");
        if (this.canvas) {
            this.ctx = this.canvas.getContext("2d");
        }
        this.loader = document.getElementById("maps3-loader");
        this.tooltip = document.getElementById("maps3-tooltip");
    }

    async loadData() {
        this.loader.classList.remove("hidden");
        try {
            this.rawData = await api._get("/maps/graph-data");
            this._layout();
            this._setStats();
            this._resetView();
            this._alpha = 1;
            this._startLoop();
        } catch (e) {
            maps3Logger.error("Failed to load graph data", e);
            globalThis.showError && globalThis.showError(String(e));
        } finally {
            this.loader.classList.add("hidden");
        }
    }

    _layout() {
        const data = this.rawData;
        if (!data) {
            return;
        }
        const chainPairs = new Set();
        for (const ch of data.chains || []) {
            for (let i = 0; i < ch.nodes.length - 1; i++) {
                chainPairs.add(ch.nodes[i] + "|" + ch.nodes[i + 1]);
                chainPairs.add(ch.nodes[i + 1] + "|" + ch.nodes[i]);
            }
        }

        const compOrder = new Map();
        const compIds = Object.keys(data.components || {}).sort();
        compIds.forEach((id, i) => compOrder.set(id, i));

        const nodes = (data.nodes || []).map(n => ({
            ...n,
            x: 0,
            y: 0,
            vx: 0,
            vy: 0,
            _compRank: n.component != null ? (compOrder.get(String(n.component)) ?? Number.MAX_SAFE_INTEGER) : Number.MAX_SAFE_INTEGER,
        }));

        // Group into rows of near-equal score, highest score first.
        const sorted = [...nodes].sort((a, b) => b.score - a.score);
        const rows = [];
        let current = [];
        for (const n of sorted) {
            if (current.length === 0 || Math.abs(current[0].score - n.score) <= SCORE_EPSILON) {
                current.push(n);
            } else {
                rows.push(current);
                current = [n];
            }
        }
        if (current.length > 0) {
            rows.push(current);
        }

        const maxRowSize = Math.max(1, ...rows.map(r => r.length));
        const heightPerUnit = Math.max(600, maxRowSize * 8);
        this.worldHalfHeight = heightPerUnit / 2 + 100;
        this.worldHalfWidth = Math.max(900, maxRowSize * 14);

        for (const row of rows) {
            // Components stay contiguous inside a row so they form horizontal
            // bands across rows; ties broken by filename for stable ranks.
            row.sort((a, b) => a._compRank - b._compRank || (a.id < b.id ? -1 : 1));
            const gap = (this.worldHalfWidth * 2) / (row.length + 1);
            row.forEach((n, i) => {
                n.x = -this.worldHalfWidth + gap * (i + 1);
                n.y = this.worldHalfHeight - n.score * heightPerUnit;
            });
        }
        this.rows = rows;
        this.nodeById = new Map(nodes.map(n => [n.id, n]));
        this.links = (data.edges || []).map(e => ({
            source: this.nodeById.get(e.source),
            target: this.nodeById.get(e.target),
            isMainChain: chainPairs.has(e.source + "|" + e.target),
        })).filter(l => l.source && l.target);
        this.nodes = nodes;
    }

    _setStats() {
        const s = this.rawData.stats || {};
        const put = (id, v) => {
            const el = document.getElementById(id);
            if (el) {
                el.textContent = Number(v).toLocaleString();
            }
        };
        put("maps3-stat-nodes", s.total_nodes ?? 0);
        put("maps3-stat-comparisons", s.total_edges ?? 0);
        put("maps3-stat-components", s.total_components ?? 0);
        put("maps3-stat-chains", s.total_chains ?? 0);
    }

    // ── Physics ──────────────────────────────────────────────────────

    _tick() {
        const nodes = this.nodes;
        const alpha = this._alpha;
        if (alpha <= 0.02) {
            this._stopLoop();
            return;
        }

        for (const n of nodes) {
            n.fx = 0;
        }

        // Horizontal repulsion between neighbours in the same score row.
        const minGap = 18;
        for (const row of this.rows) {
            for (let i = 0; i < row.length; i++) {
                const a = row[i];
                for (let j = i + 1; j < Math.min(i + 5, row.length); j++) {
                    const b = row[j];
                    const dx = b.x - a.x;
                    const dist = Math.abs(dx);
                    if (dist < minGap && dist > 0.001) {
                        const push = ((minGap - dist) / minGap) * 2.4 * alpha;
                        const dir = dx > 0 ? 1 : -1;
                        a.fx -= push * dir;
                        b.fx += push * dir;
                    } else if (dist <= 0.001) {
                        a.fx -= 0.6 * alpha;
                        b.fx += 0.6 * alpha;
                    }
                }
            }
        }

        // Horizontal attraction along links keeps connected images close.
        for (const l of this.links) {
            const dx = l.target.x - l.source.x;
            const f = dx * 0.0009 * alpha;
            l.source.fx += f;
            l.target.fx -= f;
        }

        for (const n of nodes) {
            n.vx = (n.vx + n.fx) * 0.85;
            n.x += n.vx;
            n.x = Math.max(-this.worldHalfWidth, Math.min(this.worldHalfWidth, n.x));
        }

        this._alpha *= 0.994;
    }

    // ── Rendering ────────────────────────────────────────────────────

    _startLoop() {
        if (this._rafId != null) {
            return;
        }
        const loop = () => {
            this._tick();
            this._draw();
            this._rafId = requestAnimationFrame(loop);
        };
        this._rafId = requestAnimationFrame(loop);
    }

    _stopLoop() {
        if (this._rafId != null) {
            cancelAnimationFrame(this._rafId);
            this._rafId = null;
        }
    }

    _resetView() {
        const rect = this.canvas.getBoundingClientRect();
        const sx = rect.width / (this.worldHalfWidth * 2);
        const sy = rect.height / (this.worldHalfHeight * 2);
        this._scale = Math.min(sx, sy) * 0.95;
        this._tx = 0;
        this._ty = 0;
    }

    _scoreColor(score) {
        const t = Math.max(0, Math.min(1, score));
        const r = Math.round(56 + (52 - 56) * t);
        const g = Math.round(189 - 60 * t);
        const b = Math.round(248 - 55 * t);
        return `rgb(${r},${g},${b})`;
    }

    _draw() {
        const ctx = this.ctx;
        if (!ctx) {
            return;
        }
        const rect = this.canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        if (this.canvas.width !== rect.width * dpr || this.canvas.height !== rect.height * dpr) {
            this.canvas.width = rect.width * dpr;
            this.canvas.height = rect.height * dpr;
        }
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, rect.width, rect.height);
        ctx.translate(rect.width / 2 + this._tx, rect.height / 2 + this._ty);
        ctx.scale(this._scale, this._scale);

        ctx.lineWidth = 1 / this._scale;
        for (const l of this.links) {
            ctx.beginPath();
            ctx.strokeStyle = l.isMainChain
                ? "rgba(103, 232, 249, 0.45)"
                : "rgba(107, 114, 128, 0.12)";
            if (!l.isMainChain) {
                ctx.setLineDash([4 / this._scale, 5 / this._scale]);
            }
            ctx.moveTo(l.source.x, l.source.y);
            ctx.lineTo(l.target.x, l.target.y);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        const radius = 5 / this._scale;
        for (const n of this.nodes) {
            ctx.beginPath();
            ctx.fillStyle = this._scoreColor(n.score);
            ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
            ctx.fill();
            if (n === this._hoverNode) {
                ctx.strokeStyle = "#f472b6";
                ctx.lineWidth = 2.5 / this._scale;
                ctx.stroke();
            }
        }
    }

    // ── Interaction ──────────────────────────────────────────────────

    _bindControls() {
        document.getElementById("maps3-refresh-btn")?.addEventListener("click", () => this.loadData());
        document.getElementById("maps3-reset-view-btn")?.addEventListener("click", () => this._resetView());

        this._resizeObserver = new ResizeObserver(() => this._draw());
        this._resizeObserver.observe(this.container);

        this.canvas.addEventListener("wheel", (e) => {
            e.preventDefault();
            const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
            const rect = this.canvas.getBoundingClientRect();
            const mx = e.clientX - rect.width / 2 - this._tx;
            const my = e.clientY - rect.height / 2 - this._ty;
            this._tx -= mx * (factor - 1);
            this._ty -= my * (factor - 1);
            this._scale *= factor;
            this._scale = Math.max(0.02, Math.min(20, this._scale));
        }, { passive: false });
    }

    _bindPointer() {
        this.canvas.addEventListener("mousedown", (e) => {
            this._dragging = true;
            this._dragStart = { x: e.clientX, y: e.clientY, tx: this._tx, ty: this._ty };
        });
        window.addEventListener("mousemove", (e) => {
            if (!this._dragging) {
                this._hitTest(e);
                return;
            }
            this._tx = this._dragStart.tx + (e.clientX - this._dragStart.x);
            this._ty = this._dragStart.ty + (e.clientY - this._dragStart.y);
        });
        window.addEventListener("mouseup", () => {
            this._dragging = false;
        });
    }

    _hitTest(e) {
        const rect = this.canvas.getBoundingClientRect();
        const wx = (e.clientX - rect.left - rect.width / 2 - this._tx) / this._scale;
        const wy = (e.clientY - rect.top - rect.height / 2 - this._ty) / this._scale;
        let best = null;
        let bestDist = 12 / this._scale;
        for (const n of this.nodes) {
            const dx = n.x - wx;
            const dy = n.y - wy;
            const d = Math.sqrt(dx * dx + dy * dy);
            if (d < bestDist) {
                best = n;
                bestDist = d;
            }
        }
        this._hoverNode = best;
        if (best) {
            this.tooltip.classList.remove("hidden");
            this.tooltip.style.left = `${e.clientX - rect.left + 14}px`;
            this.tooltip.style.top = `${e.clientY - rect.top + 14}px`;
            this.tooltip.innerHTML = `
                <div class="font-bold text-white text-[11px] mb-1 break-all">${best.id}</div>
                <div class="text-[10px] text-gray-300">Score: ${best.score}</div>
                <div class="text-[10px] text-gray-300">Comparisons: ${best.comparison_count}</div>
                <div class="text-[10px] text-gray-300">Component: ${best.component ?? "\u2014"}</div>
                <div class="text-[10px] text-gray-300">${best.is_top ? "Top" : best.is_bottom ? "Bottom" : ""}</div>
            `;
            this.canvas.style.cursor = "pointer";
        } else {
            this.tooltip.classList.add("hidden");
            this.canvas.style.cursor = this._dragging ? "grabbing" : "grab";
        }
    }

    destroy() {
        this._stopLoop();
        if (this._resizeObserver) {
            this._resizeObserver.disconnect();
            this._resizeObserver = null;
        }
        this.rawData = null;
        this.nodes = [];
        this.links = [];
        this.rows = [];
    }
};

window.Sections = window.Sections || {};
window.Sections.maps3 = globalThis.ScoreMapUI;
