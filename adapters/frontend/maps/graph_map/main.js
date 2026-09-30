const mapsMainLogger = FrontendLogger.create("maps.graph_map.main");

globalThis.ChainMapUI = class {
    constructor() {
        this.rawData = null;
        this.renderer = null;
        this.selectedNodes = [];
        this._showMain = true;
        this._showSecondary = true;
        this._showRegular = false;
        this._showLabels = true;
        this._mainLinkPhysics = true;
        this._secondaryChainPhysics = true;
        this._buoyancyEnabled = true;
        this._repulsionEnabled = true;
        this._dampingEnabled = true;
        this._collisionsEnabled = true;
        this._activeForces = [];
        this._forceIndex = 0;
        this._tickSkipAccum = 0;
        this._forcesPerTick = 5;
        this._tickFrequency = 1.0;
        this._useWebGLPhysics = false;
        this._webglToastShown = false;
        this._webglPhysics = null;
        this._webglNeedsReinit = false;
        this._simNodes = [];
        this._simLinks = [];
        this._paused = true;
        this._simAlpha = 1;
        this._tickCount = 0;
        this._forceStats = {};
        this._statsCursor = 0;
        this._maxNodes = 0;
        this._nodePower = 0.5;
        this._physicsCfg = {
            baseLinkLength: globalThis.RENDER.physics.defaultBaseLinkLength,
            linkScoreMultiplier: 2,
            linkStrength: globalThis.RENDER.physics.defaultLinkStrength,
            secondaryLinkStrength: globalThis.RENDER.physics.defaultLinkStrength,
            buoyancyStrength: globalThis.RENDER.physics.defaultBuoyancyStrength,
            repulsionStrength: globalThis.RENDER.physics.defaultRepulsionStrength,
            repulsionRange: globalThis.RENDER.physics.defaultRepulsionRange,
            velocityDecay: globalThis.RENDER.physics.defaultVelocityDecay,
            nodeBaseSize: globalThis.RENDER.physics.defaultNodeBaseSize,
            alphaDecay: 0.0005,
            alphaMin: 0.02,
            minAreaPerNode: 40000,
            maxVelocity: 100,
        };
    }

    async init() {
        this.ce();
        if (!this.container) {
            return;
        }
        this.loadFiltersFromStorage();
        this._initActiveForces();
        this.setupRenderer();
        if (!this.renderer || !this.renderer.canvas) {
            globalThis.showError("WebGL unavailable");
            if (this.loader) {
                this.loader.classList.add("hidden");
            }
            return;
        }
        this.renderer.resize();
        window.addEventListener("resize", () => {
            if (this.renderer) {
                this.renderer.resize();
            }
        });
        document.addEventListener("visibilitychange", () => {
            if (document.hidden) {
                this._stopSim();
            } else if (!this._paused && this._simNodes.length && this._simAlpha > 0.001) {
                this._startSim();
            }
        });
        this._listen();
        await this.loadData();
    }

    _startSim() {
        if (!this._simNodes.length) {
            return;
        }
        this._simAlpha = 1;
        this.renderer.onSimulationEnd = () => {
            const pauseIcon = document.getElementById("pause-icon");
            const playIcon = document.getElementById("play-icon");
            if (pauseIcon) {
                pauseIcon.classList.add("hidden");
            }
            if (playIcon) {
                playIcon.classList.remove("hidden");
            }
            this._paused = true;
        };
        this.renderer.startLoop(() => this._tick());
    }

    _stopSim() {
        this.renderer.stopLoop();
    }

    _restartSim() {
        const wasPaused = this._paused;
        this._stopSim();
        this.applyFilters();
        if (!wasPaused && this._simNodes.length) {
            this._startSim();
        }
    }

    _tick() {
        const tickStartTime = performance.now();
        try {
            const simulationNodes = this._simNodes;
            if (this._useWebGLPhysics) {
                return this._tickWebGL(simulationNodes, tickStartTime);
            }
            if (!simulationNodes.length) {
                this._recordStat("_tick", performance.now() - tickStartTime);
                return false;
            }

            const totalForces = this._activeForces.length;

            let forcesToRun = 0;
            let shouldSkipTick = false;

            if (totalForces > 0) {
                forcesToRun = Math.min(this._forcesPerTick, totalForces);
                if (this._tickFrequency < 1) {
                    this._tickSkipAccum += (1 - this._tickFrequency);
                    if (this._tickSkipAccum >= 1) {
                        this._tickSkipAccum -= 1;
                        shouldSkipTick = true;
                    }
                }
            }

            this._tickCount++;
            if (this.statPhysics) {
                this.statPhysics.textContent = this._tickCount;
            }

            if (shouldSkipTick || forcesToRun === 0) {
                this._recordStat("_tick", performance.now() - tickStartTime);
                for (const forceName of this._activeForces) {
                    const chartHistory = this._chartHistory[forceName];
                    if (chartHistory) {
                        chartHistory.push(0);
                        if (chartHistory.length > 100) {
                            chartHistory.splice(0, chartHistory.length - 100);
                        }
                    }
                }
                return true;
            }

            for (const node of simulationNodes) {
                node.fx = 0;
                node.fy = 0;
            }

            for (let forceIndex = 0; forceIndex < forcesToRun; forceIndex++) {
                const forceName = this._activeForces[this._forceIndex % totalForces];
                this._forceIndex++;
                if (forceName && typeof this[forceName] === "function") {
                    const forceStartTime = performance.now();
                    this[forceName]();
                    this._recordStat(forceName, performance.now() - forceStartTime);
                }
            }
            this._updateStats();

            const physicsConfig = this._physicsCfg;
            const mapHalfSize = this._mapHalf || 0;
            const velocityDecayFactor = this._dampingEnabled ? (1 - physicsConfig.velocityDecay) : 1;
            const maxVelocity = this._dampingEnabled ? physicsConfig.maxVelocity : Infinity;
            for (const node of simulationNodes) {
                node.vx = (node.vx || 0) * velocityDecayFactor + node.fx;
                node.vy = (node.vy || 0) * velocityDecayFactor + node.fy;
                if (this._dampingEnabled) {
                    if (node.vx > maxVelocity) {
                        node.vx = maxVelocity;
                    } else if (node.vx < -maxVelocity) {
                        node.vx = -maxVelocity;
                    }
                    if (node.vy > maxVelocity) {
                        node.vy = maxVelocity;
                    } else if (node.vy < -maxVelocity) {
                        node.vy = -maxVelocity;
                    }
                }
                node.x += node.vx;
                node.y += node.vy;
                if (mapHalfSize > 0) {
                    if (node.x > mapHalfSize) {
                        node.x = mapHalfSize;
                        if (node.vx > 0) {
                            node.vx = 0;
                        }
                    } else if (node.x < -mapHalfSize) {
                        node.x = -mapHalfSize;
                        if (node.vx < 0) {
                            node.vx = 0;
                        }
                    }
                    if (node.y > mapHalfSize) {
                        node.y = mapHalfSize;
                        if (node.vy > 0) {
                            node.vy = 0;
                        }
                    } else if (node.y < -mapHalfSize) {
                        node.y = -mapHalfSize;
                        if (node.vy < 0) {
                            node.vy = 0;
                        }
                    }
                }
            }

            this._simAlpha *= (1 - this._physicsCfg.alphaDecay);
            if (this._simAlpha < this._physicsCfg.alphaMin) {
                this._simAlpha = this._physicsCfg.alphaMin;
            }

            this._recordStat("_tick", performance.now() - tickStartTime);
            return true;
        } catch (error) {
            mapsMainLogger.error("Physics tick error", error);
            return true;
        }
    }

    _sync() {
        const toggleIconVisibility = (onIconId, offIconId, show) => {
            const onIcon = document.getElementById(onIconId);
            const offIcon = document.getElementById(offIconId);
            if (onIcon) {
                onIcon.classList.toggle("hidden", !show);
            }
            if (offIcon) {
                offIcon.classList.toggle("hidden", show);
            }
        };
        toggleIconVisibility("tag-icon-on", "tag-icon-off", this._showLabels);
        if (this.renderer) {
            this.renderer.labelsVisible = this._showLabels;
        }
        toggleIconVisibility("main-chains-icon-on", "main-chains-icon-off", this._showMain);
        toggleIconVisibility("secondary-chains-icon-on", "secondary-chains-icon-off", this._showSecondary);
        toggleIconVisibility("regular-links-icon-on", "regular-links-icon-off", this._showRegular);
    }

    render(filteredNodes, filteredEdges, stats) {
        this._webglNeedsReinit = true;
        if (!filteredNodes.length) {
            this._setStats(0, 0, 0, 0);
            if (this.renderer) {
                this.renderer.render({
                    nodes: [],
                    links: [],
                    selectedIds: [],
                    world: { x: 0, y: 0, width: 800, height: 600 },
                    nodeBaseSize: this._physicsCfg.nodeBaseSize,
                });
            }
            if (this.loader) {
                this.loader.classList.add("hidden");
            }
            return;
        }

        const uniqueComponents = new Set(filteredNodes.map(node => String(node.component)));
        this._setStats(filteredNodes.length, filteredEdges.length, uniqueComponents.size, stats.total_chains || 0);

        const colorScale = globalThis.d3.scaleLinear()
            .domain(globalThis.RENDER.node.colorDomain)
            .range(globalThis.RENDER.node.colorRange);
        const componentSizes = {};
        if (this.rawData.components) {
            for (const [componentId, members] of Object.entries(this.rawData.components)) {
                componentSizes[componentId] = members.length;
            }
        }

        const simulationNodes = filteredNodes.map(nodeData => ({
            ...nodeData,
            _fill: colorScale(nodeData.score),
            _compSize: componentSizes[String(nodeData.component)],
            _chainPrev: null,
            _chainNext: null,
            _chainId: null,
            _allChains: null,
            vx: 0,
            vy: 0,
            fx: 0,
            fy: 0,
        }));

        const nodeMap = new Map(simulationNodes.map(node => [node.id, node]));
        const mainChainEdges = new Set();
        const chainInfoMap = new Map();

        if (this.rawData.chains) {
            for (const chain of this.rawData.chains) {
                for (let nodeIndex = 0; nodeIndex < chain.nodes.length; nodeIndex++) {
                    const nodeId = chain.nodes[nodeIndex][0];
                    const isMain = chain.nodes[nodeIndex][1];

                    const existingInfo = chainInfoMap.get(nodeId);
                    if (!existingInfo) {
                        chainInfoMap.set(nodeId, {
                            chainId: chain.id,
                            prev: nodeIndex > 0 ? chain.nodes[nodeIndex - 1][0] : null,
                            next: nodeIndex < chain.nodes.length - 1 ? chain.nodes[nodeIndex + 1][0] : null,
                            chainLen: chain.nodes.length,
                            allChains: [chain.id],
                        });
                    } else {
                        existingInfo.allChains.push(chain.id);
                        if (existingInfo.chainLen < chain.nodes.length) {
                            existingInfo.chainId = chain.id;
                            existingInfo.prev = nodeIndex > 0 ? chain.nodes[nodeIndex - 1][0] : null;
                            existingInfo.next = nodeIndex < chain.nodes.length - 1 ? chain.nodes[nodeIndex + 1][0] : null;
                            existingInfo.chainLen = chain.nodes.length;
                        }
                    }
                    if (nodeIndex < chain.nodes.length - 1) {
                        const nextNode = chain.nodes[nodeIndex + 1];
                        if (isMain && nextNode[1]) {
                            mainChainEdges.add(nodeId + "|" + nextNode[0]);
                            mainChainEdges.add(nextNode[0] + "|" + nodeId);
                        }
                    }
                }
            }
        }
        // console.log(mainChainEdges);
        for (const node of simulationNodes) {
            const chainInfo = chainInfoMap.get(node.id);
            if (chainInfo) {
                node._chainPrev = chainInfo.prev;
                node._chainNext = chainInfo.next;
                node._chainId = chainInfo.chainId;
                node._allChains = chainInfo.allChains;
            }
        }

        const simulationLinks = [];
        const existingLinks = new Set();
        for (const edge of filteredEdges) {
            const sourceNode = nodeMap.get(edge.source);
            const targetNode = nodeMap.get(edge.target);
            if (sourceNode && targetNode) {
                const isMainChain = mainChainEdges.has(edge.source + "|" + edge.target);
                simulationLinks.push({ source: sourceNode, target: targetNode, isMainChain });
                existingLinks.add(edge.source + "|" + edge.target);
                existingLinks.add(edge.target + "|" + edge.source);
            }
        }
        if (this.rawData.chains) {
            for (const chain of this.rawData.chains) {
                for (let nodeIndex = 0; nodeIndex < chain.nodes.length - 1; nodeIndex++) {
                    const sourceId = chain.nodes[nodeIndex][0];
                    const targetId = chain.nodes[nodeIndex + 1][0];
                    const isMain = chain.nodes[nodeIndex][1] && chain.nodes[nodeIndex + 1][1];
                    const sourceNode = nodeMap.get(sourceId);
                    const targetNode = nodeMap.get(targetId);
                    if (sourceNode && targetNode && !existingLinks.has(sourceId + "|" + targetId)) {
                        simulationLinks.push({ source: sourceNode, target: targetNode, isMainChain: isMain });
                        existingLinks.add(sourceId + "|" + targetId);
                        existingLinks.add(targetId + "|" + sourceId);
                    }
                }
            }
        }

        const nodeDegrees = new Map();
        for (const link of simulationLinks) {
            nodeDegrees.set(link.source.id, (nodeDegrees.get(link.source.id) || 0) + 1);
            nodeDegrees.set(link.target.id, (nodeDegrees.get(link.target.id) || 0) + 1);
        }
        const nodePower = this._nodePower;
        for (const node of simulationNodes) {
            const degree = nodeDegrees.get(node.id) || 0;
            node._deg = degree;
            node._radius = this._physicsCfg.nodeBaseSize + (nodePower === 0 ? 0 : Math.pow(degree, nodePower));
        }

        const oldPositionMap = new Map((this._simNodes || []).map(node => [node.id, node]));
        this._simNodes = simulationNodes;
        this._simLinks = simulationLinks;

        const mapSize = Math.sqrt(simulationNodes.length * this._physicsCfg.minAreaPerNode);
        for (const node of simulationNodes) {
            const oldNode = oldPositionMap.get(node.id);
            if (oldNode) {
                node.x = oldNode.x;
                node.y = oldNode.y;
                node.vx = oldNode.vx || 0;
                node.vy = oldNode.vy || 0;
            } else {
                node.x = (Math.random() - 0.5) * mapSize;
                node.y = (Math.random() - 0.5) * mapSize;
                node.vx = 0;
                node.vy = 0;
            }
        }
        this._mapHalf = mapSize / 2;

        const worldBounds = {
            x: -this._mapHalf - globalThis.RENDER.border.padding,
            y: -this._mapHalf - globalThis.RENDER.border.padding,
            width: mapSize + globalThis.RENDER.border.padding * 2,
            height: mapSize + globalThis.RENDER.border.padding * 2,
        };

        if (this.renderer) {
            this.renderer._showMainLinks = this._showMain;
            this.renderer._showRegularLinks = this._showRegular;
        }

        this.renderer.render({
            nodes: simulationNodes,
            links: simulationLinks,
            selectedIds: this.selectedNodes,
            world: worldBounds,
            nodeBaseSize: this._physicsCfg.nodeBaseSize,
        });
        if (this.loader) {
            this.loader.classList.add("hidden");
        }

        this._paused = true;
        this._simAlpha = 1;
        this._tickCount = 0;
        this._forceIndex = 0;
        this._tickSkipAccum = 0;
        this._sync();

        const pauseIcon = document.getElementById("pause-icon");
        const playIcon = document.getElementById("play-icon");
        if (pauseIcon) {
            pauseIcon.classList.add("hidden");
        }
        if (playIcon) {
            playIcon.classList.remove("hidden");
        }
    }

    _tickWebGL(simulationNodes, tickStartTime) {
        if (!simulationNodes.length) {
            this._recordStat("_tick", performance.now() - tickStartTime);
            return false;
        }

        const totalForces = this._activeForces.length;
        let shouldSkipTick = false;
        let forcesToUse = 0;

        if (totalForces > 0) {
            forcesToUse = Math.min(this._forcesPerTick, totalForces);
            if (this._tickFrequency < 1) {
                this._tickSkipAccum += (1 - this._tickFrequency);
                if (this._tickSkipAccum >= 1) {
                    this._tickSkipAccum -= 1;
                    shouldSkipTick = true;
                }
            }
        }

        this._tickCount++;
        if (this.statPhysics) {
            this.statPhysics.textContent = this._tickCount;
        }

        if (shouldSkipTick || forcesToUse === 0) {
            this._recordStat("_tick", performance.now() - tickStartTime);
            for (const forceName of this._activeForces) {
                const chartHistory = this._chartHistory[forceName];
                if (chartHistory) {
                    chartHistory.push(0);
                    if (chartHistory.length > 100) {
                        chartHistory.splice(0, chartHistory.length - 100);
                    }
                }
            }
            this._updateStats();
            return true;
        }

        if (!this._webglPhysics || this._webglNeedsReinit) {
            if (this._webglPhysics) {
                this._webglPhysics.destroy();
                this._webglPhysics = null;
            }
            const canvas = document.createElement("canvas");
            canvas.width = 1;
            canvas.height = 1;
            const glContext = canvas.getContext("webgl2", { alpha: false, antialias: false, premultipliedAlpha: false });
            if (!glContext) {
                if (!this._webglToastShown) {
                    this._webglToastShown = true;
                    globalThis.showError("WebGL 2.0 not available");
                }
                this._useWebGLPhysics = false;
                if (this._updateWebglBtn) {
                    this._updateWebglBtn(false);
                }
                this._tickSkipAccum = 0;
                return false;
            }
            this._webglPhysics = new globalThis.WebGLPhysics();
            if (!this._webglPhysics.init(glContext, simulationNodes, this._simLinks)) {
                if (!this._webglToastShown) {
                    this._webglToastShown = true;
                    globalThis.showError("WebGL: " + (this._webglPhysics._lastError || "init failed"));
                }
                this._webglPhysics = null;
                this._useWebGLPhysics = false;
                if (this._updateWebglBtn) {
                    this._updateWebglBtn(false);
                }
                this._tickSkipAccum = 0;
                return false;
            }
            this._webglNeedsReinit = false;
        }

        const enabledForces = this._activeForces.slice(0, forcesToUse);
        const forceTickStartTime = performance.now();
        this._webglPhysics.tick(this._simAlpha, this._physicsCfg, enabledForces, this._mapHalf, this._dampingEnabled);
        const forceTickDuration = performance.now() - forceTickStartTime;

        this._simAlpha *= (1 - this._physicsCfg.alphaDecay);
        if (this._simAlpha < this._physicsCfg.alphaMin) {
            this._simAlpha = this._physicsCfg.alphaMin;
        }

        this._webglPhysics.readback(simulationNodes);

        this._recordStat("_tick", performance.now() - tickStartTime);
        for (const forceName of enabledForces) {
            this._recordStat(forceName, forceTickDuration / enabledForces.length);
        }
        this._updateStats();
        return true;
    }

    _setStats(nodeCount, edgeCount, componentCount, chainCount) {
        if (this.statNodes) {
            this.statNodes.textContent = nodeCount.toLocaleString();
        }
        if (this.statComparisons) {
            this.statComparisons.textContent = edgeCount.toLocaleString();
        }
        if (this.statComponents) {
            this.statComponents.textContent = componentCount.toLocaleString();
        }
        if (this.statChains) {
            this.statChains.textContent = chainCount.toLocaleString();
        }
    }

    cleanup() {
        if (this.renderer) {
            this._stopSim();
            this.renderer.destroy();
            this.renderer = null;
        }
        if (this._webglPhysics) {
            this._webglPhysics.destroy();
            this._webglPhysics = null;
        }
        this.rawData = null;
        this.selectedNodes = [];
        this._simNodes = [];
        this._simLinks = [];
    }
};

window.chainMapUI = new globalThis.ChainMapUI();
window.Sections = window.Sections || {};
window.Sections.chains = globalThis.ChainMapUI;
