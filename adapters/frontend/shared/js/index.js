const routerLogger = FrontendLogger.create("external_modules.server.frontend.js.index");

/* Sections that offer the shared Compare Selected control. */
const COMPARE_SELECTED_SECTIONS = new Set(["gallery", "chains"]);

const router = {
    routes: {
        compare: {
            template: "/static/comparison/compare.html",
            section: "compare",
        },
        gallery: {
            template: "/static/gallery/gallery.html",
            section: "gallery",
        },
        chains: {
            template: "/static/maps/maps.html",
            section: "chains",
        },
        database: {
            template: "/static/database/database.html",
            section: "database",
        },
        build: {
            template: "/static/build/build.html",
            section: "build",
        },
        training: {
            template: "/static/training/training.html",
            section: "training",
        },
        analyze: {
            template: "/static/analyze/analyze.html",
            section: "analyze",
        },
    },

    _currentInstance: null,
    _currentSection: null,

    /* Compare Selected lives in the shell rather than in each section, so the
       router owns its visibility and delegates the click to the current
       instance. Sections report their selection through setSelectedCount. */
    setSelectedCount(count) {
        this._selectedCount = count;
        const btn = document.getElementById("compare-selected-btn");
        const label = document.getElementById("selected-count");
        if (label) {
            label.textContent = count;
        }
        if (btn) {
            btn.classList.toggle("hidden", count < 2);
        }
    },

    _updateCompareSelectedVisibility() {
        const wrap = document.getElementById("compare-selected-wrap");
        if (!wrap) {
            return;
        }
        const active = COMPARE_SELECTED_SECTIONS.has(this._currentSection);
        wrap.classList.toggle("hidden", !active);
        if (active) {
            this.setSelectedCount(this._selectedCount ?? 0);
        }
    },

    compareSelected() {
        const instance = this._currentInstance;
        if (instance && typeof instance.compareSelected === "function") {
            instance.compareSelected();
        } else {
            routerLogger.warn("Compare Selected is unavailable in this section");
        }
    },

    async init() {
        window.addEventListener("hashchange", () => this.handleRoute());

        if (!window.location.hash || window.location.hash === "#") {
            window.location.hash = "#compare";
        } else {
            this.handleRoute();
        }
    },

    async handleRoute() {
        const hash = window.location.hash.substring(1) || "compare";
        const [routeName, queryStr] = hash.split("?");
        const params = new URLSearchParams(queryStr);

        if (this.routes[routeName]) {
            await this.loadRoute(routeName, params);
        } else {
            routerLogger.warn(`Route not found: ${routeName}`);
            window.location.hash = "#compare";
        }
    },

    async loadRoute(routeName, params) {
        const route = this.routes[routeName];
        const contentArea = document.getElementById("app-content");

        contentArea.innerHTML = `
            <div class="flex flex-col items-center justify-center min-h-[400px]">
                <div class="w-12 h-12 border-4 border-purple-500/20 border-t-purple-500 rounded-full animate-spin mb-4"></div>
                <p class="text-gray-500 animate-pulse">Switching to ${routeName}...</p>
            </div>
        `;

        try {
            const response = await fetch(route.template);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const html = await response.text();

            this._destroyCurrentInstance();

            contentArea.innerHTML = html;

            this.updateNavUI(routeName);

            requestAnimationFrame(() => {
                this._createSectionInstance(route.section, params);
            });
        } catch (e) {
            routerLogger.error("Router error", e);
            contentArea.innerHTML = `
                <div class="p-12 glass rounded-2xl text-center">
                    <h2 class="text-2xl font-bold text-red-400 mb-2">Navigation Error</h2>
                    <p class="text-gray-400 mb-6">${e.message}</p>
                    <button onclick="window.location.reload()" class="px-6 py-2 bg-purple-600 rounded-lg font-bold">Reload App</button>
                </div>
            `;
        }
    },

    _destroyCurrentInstance() {
        if (this._currentInstance && typeof this._currentInstance.destroy === "function") {
            this._currentInstance.destroy();
        }
        this._currentInstance = null;
        this._currentSection = null;
    },

    _createSectionInstance(sectionName, params) {
        const Cls = window.Sections && window.Sections[sectionName];
        if (!Cls) {
            routerLogger.error(`Section class not found: ${sectionName}`);
            return;
        }
        // The maps section registers its own shared instance rather than a class,
        // so its lifecycle is driven by the instance it installs on window.
        const instance = typeof Cls === "function" ? new Cls() : Cls;
        if (typeof instance.init === "function") {
            instance.init(params);
        }
        this._currentInstance = instance;
        this._currentSection = sectionName;
        this._updateCompareSelectedVisibility();
    },

    updateNavUI(routeName) {
        document.querySelectorAll("nav a, .mobile-nav-menu a")
            .forEach((link) => {
                const href = link.getAttribute("href");
                if (!href) {
                    return;
                }
                const isMatch = href === `#${routeName}`;

                if (isMatch) {
                    link.classList.add("nav-link-active");
                } else {
                    link.classList.remove("nav-link-active");
                }
            });
    },
};

function initMobileNav() {
    const toggle = document.getElementById("nav-toggle-btn");
    const menu = document.getElementById("mobile-nav-menu");
    if (!toggle || !menu) {
        return;
    }
    toggle.addEventListener("click", () => {
        menu.classList.toggle("open");
    });
    menu.querySelectorAll("a")
        .forEach((link) => {
            link.addEventListener("click", () => menu.classList.remove("open"));
        });
}

document.addEventListener("DOMContentLoaded", () => {
    router.init();
    initMobileNav();
});
