globalThis.ChainMapUI.prototype.updateHUD = function ({ k }) {
    if (this.zoomScaleEl) {
        this.zoomScaleEl.textContent = (k || 1).toFixed(2) + "x";
    }
    if (this.viewCoordsEl && this.renderer && this.renderer.controls) {
        const t = this.renderer.controls.target;
        this.viewCoordsEl.textContent = "X: " + Math.round(t.x) + ", Y: " + Math.round(t.y);
    }
};

globalThis.ChainMapUI.prototype._updateStatsView = function () {
    const tbody = this.perfStatsBody;
    if (!tbody) {
        return;
    }
    const forces = globalThis.FORCE_METRICS.filter(([fn]) => fn !== "_tick");
    const fmt = (v) => v < 0.001 ? (v * 1000).toFixed(2) + "µs" : v.toFixed(3) + "ms";
    let html = "";
    for (const [fn, , color] of forces) {
        const s = this._forceStats[fn];
        if (!s) {
            continue;
        }
        const active = this._activeForces.includes(fn);
        const opacity = active ? "" : "opacity-40";
        html += `<tr class="${opacity}">
            <td class="text-left py-0.5 pr-2 text-gray-300"><span class="inline-block w-1.5 h-1.5 rounded-full align-middle mr-1" style="background:${color}"></span><span class="align-middle">${s.label}</span></td>
            <td class="text-right py-0.5 px-2 text-cyan-300">${fmt(s.live)}</td>
            <td class="text-right py-0.5 px-2 text-green-300">${fmt(s.avg10s)}</td>
            <td class="text-right py-0.5 px-2 text-yellow-300">${fmt(s.avg60s)}</td>
        </tr>`;
    }
    const tick = this._forceStats["_tick"];
    if (tick) {
        html += `<tr class="border-t border-white/10">
            <td class="text-left py-0.5 pr-2 text-white font-bold">${tick.label}</td>
            <td class="text-right py-0.5 px-2 text-cyan-300 font-bold">${fmt(tick.live)}</td>
            <td class="text-right py-0.5 px-2 text-green-300 font-bold">${fmt(tick.avg10s)}</td>
            <td class="text-right py-0.5 px-2 text-yellow-300 font-bold">${fmt(tick.avg60s)}</td>
        </tr>`;
    }
    tbody.innerHTML = html;
    this._drawPerfChart();
};

globalThis.ChainMapUI.prototype._drawPerfChart = function () {
    const canvas = this.perfChart;
    if (!canvas) {
        return;
    }
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    const PL = 34;
    const PR = 4;
    const PT = 4;
    const PB = 4;
    const plotW = W - PL - PR;
    const plotH = H - PT - PB;

    ctx.clearRect(0, 0, W, H);

    // The HUD plots the five forces; the tick total is a row in the table, not a series.
    const plotted = globalThis.FORCE_METRICS.filter(([fn]) => fn !== "_tick");
    const order = plotted.map(([fn]) => fn);
    const colors = plotted.map(([, , color]) => color);

    let maxDur = 0.5;
    const series = [];
    for (const fn of order) {
        const pts = this._chartHistory[fn];
        if (pts && pts.length > 0) {
            for (const d of pts) {
                if (d > maxDur) {
                    maxDur = d;
                }
            }
            series.push(pts);
        } else {
            series.push(null);
        }
    }
    if (maxDur <= 0) {
        maxDur = 1;
    }
    maxDur *= 1.15;
    const fmtAxis = (v) => v < 0.001 ? (v * 1000).toFixed(1) + "µ" : v.toFixed(2) + "m";

    const grids = 4;
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 0.5;
    ctx.fillStyle = "rgba(255,255,255,0.3)";
    ctx.font = "8px monospace";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let i = 0; i <= grids; i++) {
        const y = PT + (i / grids) * plotH;
        ctx.beginPath();
        ctx.moveTo(PL, y);
        ctx.lineTo(W - PR, y);
        ctx.stroke();
        const label = fmtAxis(maxDur * (1 - i / grids));
        ctx.fillText(label, PL - 3, y);
    }

    for (let si = 0; si < order.length; si++) {
        const pts = series[si];
        if (!pts || pts.length < 2) {
            continue;
        }
        ctx.strokeStyle = colors[si];
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        const n = pts.length;
        for (let i = 0; i < n; i++) {
            const x = PL + (i / (n - 1)) * plotW;
            const y = PT + plotH - (pts[i] / maxDur) * plotH;
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        ctx.stroke();
    }
};

globalThis.ChainMapUI.prototype.updateSelectionUI = function () {
    const c = this.selectedNodes.length;
    if (this.selectedCountEl) {
        this.selectedCountEl.textContent = c;
    }
    if (this.compareSelectedBtn) {
        this.compareSelectedBtn.classList.toggle("hidden", c < 2);
    }
};
