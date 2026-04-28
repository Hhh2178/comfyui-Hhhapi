import { app } from "../../scripts/app.js";

const API_BASE = "/api/hhhapi/v1";

async function fetchJson(url) {
    const resp = await fetch(url, { cache: "no-store" });
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    return await resp.json();
}

function byName(node) {
    const out = {};
    for (const widget of node.widgets || []) out[widget.name] = widget;
    return out;
}

function firstWidget(widgets, names) {
    for (const name of names) {
        if (widgets[name]) return widgets[name];
    }
    return null;
}

async function refreshFallbackWidgets(node, { forceDefault = false } = {}) {
    const widgets = byName(node);
    const provider = widgets["服务商"];
    const fallbackProvider = firstWidget(widgets, ["输出为空时替代服务商", "失败时替代服务商"]);
    const fallbackModel = firstWidget(widgets, ["输出为空时替代模型", "失败时替代模型"]);
    if (!provider || !fallbackProvider || !fallbackModel) return;

    const providers = await fetchJson(`${API_BASE}/providers`);
    const ids = providers.map(p => p.id).filter(Boolean);
    if (!ids.length) return;

    fallbackProvider.options.values = ["", ...ids];
    if (!fallbackProvider.value || !fallbackProvider.options.values.includes(fallbackProvider.value)) {
        fallbackProvider.value = ids.find(id => id !== provider.value) || ids[0] || "";
    }

    const targetProvider = fallbackProvider.value || "";
    if (!targetProvider) {
        fallbackModel.options.values = [""];
        fallbackModel.value = "";
        app.graph.setDirtyCanvas(true);
        return;
    }

    const models = await fetchJson(`${API_BASE}/models?provider_id=${encodeURIComponent(targetProvider)}`);
    const safeModels = Array.isArray(models) ? models.filter(Boolean) : [];
    fallbackModel.options.values = ["", ...safeModels];
    if (forceDefault || !fallbackModel.options.values.includes(fallbackModel.value)) {
        fallbackModel.value = safeModels[0] || "";
    }
    app.graph.setDirtyCanvas(true);
}

app.registerExtension({
    name: "Hhhapi.Text.FallbackFix",

    async nodeCreated(node) {
        if (node.comfyClass !== "HhhapiText") return;
        await new Promise(resolve => setTimeout(resolve, 250));

        const widgets = byName(node);
        const fallbackProvider = firstWidget(widgets, ["输出为空时替代服务商", "失败时替代服务商"]);
        if (!fallbackProvider || fallbackProvider.__hhhapiFallbackFixReady) return;
        fallbackProvider.__hhhapiFallbackFixReady = true;

        const oldFallbackProviderCallback = fallbackProvider.callback;
        fallbackProvider.callback = function(value) {
            fallbackProvider.value = value;
            if (oldFallbackProviderCallback) oldFallbackProviderCallback.call(this, value);
            fallbackProvider.value = value;
            refreshFallbackWidgets(node, { forceDefault: true }).catch(err => {
                console.warn("[Hhhapi] fallback model refresh", err);
            });
        };

        refreshFallbackWidgets(node).catch(err => {
            console.warn("[Hhhapi] fallback widget init", err);
        });
    },
});
