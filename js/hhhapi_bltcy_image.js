import { app } from "../../scripts/app.js";

const API_BASE = "/api/hhhapi/image/v1";

async function fetchJson(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    return await resp.json();
}

function byName(node) {
    const out = {};
    for (const widget of node.widgets || []) out[widget.name] = widget;
    return out;
}

function ensureBadge(node, familyLabel) {
    if (node.__hhhapiImageBadgeReady) return;
    node.__hhhapiImageBadgeReady = true;
    node.__hhhapiImageLabel = familyLabel;

    const originalDrawForeground = node.onDrawForeground;
    node.onDrawForeground = function(ctx) {
        if (originalDrawForeground) originalDrawForeground.call(this, ctx);
        const label = this.__hhhapiImageLabel;
        if (!label || this.flags?.collapsed) return;
        ctx.save();
        ctx.font = "11px sans-serif";
        const boxWidth = ctx.measureText(label).width + 14;
        const x = Math.min(104, Math.max(8, (this.size?.[0] || 220) - boxWidth - 36));
        const y = 8;
        ctx.fillStyle = "rgba(34, 34, 34, 0.92)";
        ctx.fillRect(x, y - 9, boxWidth, 16);
        ctx.strokeStyle = "rgba(120, 120, 120, 0.65)";
        ctx.strokeRect(x, y - 9, boxWidth, 16);
        ctx.fillStyle = label.includes("Nano") ? "#fcd34d" : "#93c5fd";
        ctx.fillText(label, x + 7, y + 2);
        ctx.restore();
    };
}

async function bindModelRefresh(node, family, familyLabel) {
    await new Promise(resolve => setTimeout(resolve, 100));
    const widgets = byName(node);
    const provider = widgets["服务商"];
    const model = widgets["模型"];
    const fallbackProvider = widgets["失败时替代服务商"];
    const fallbackModel = widgets["失败时替代模型"];
    if (!provider || !model) return;

    ensureBadge(node, familyLabel);

    async function refreshModels() {
        try {
            const models = await fetchJson(`${API_BASE}/models?family=${encodeURIComponent(family)}&provider_id=${encodeURIComponent(provider.value || "")}`);
            const safeModels = Array.isArray(models) ? models.filter(Boolean) : [];
            if (safeModels.length) {
                const previousPrimary = model.value;
                model.options.values = safeModels;
                if (!safeModels.includes(model.value)) model.value = safeModels[0];
                if (fallbackProvider && fallbackModel && fallbackProvider.value === provider.value && (!fallbackModel.value || fallbackModel.value === previousPrimary)) {
                    fallbackModel.options.values = ["", ...safeModels];
                    fallbackModel.value = model.value;
                }
            } else {
                model.options.values = [""];
                model.value = "";
            }
            app.graph.setDirtyCanvas(true);
        } catch (err) {
            console.warn("[Hhhapi.Image]", err);
        }
    }

    async function refreshProvidersAndModels() {
        try {
            const config = await fetchJson(`${API_BASE}/config`);
            const providerIds = Array.isArray(config?.config?.providers) ? config.config.providers.map(x => x.id).filter(Boolean) : [];
            if (providerIds.length) {
                provider.options.values = providerIds;
                if (!providerIds.includes(provider.value)) provider.value = providerIds[0];
                if (fallbackProvider) {
                    const fallbackProviderChoices = ["", ...providerIds];
                    const shouldFollow = !fallbackProvider.value || fallbackProvider.value === provider.value || !fallbackProviderChoices.includes(fallbackProvider.value);
                    fallbackProvider.options.values = fallbackProviderChoices;
                    if (shouldFollow) fallbackProvider.value = provider.value;
                }
            }
            await refreshModels();
            await refreshFallbackModels();
        } catch (err) {
            console.warn("[Hhhapi.Image]", err);
        }
    }

    async function refreshFallbackModels() {
        if (!fallbackModel || !fallbackProvider) return;
        try {
            const targetProvider = fallbackProvider.value || "";
            if (!targetProvider) {
                fallbackModel.options.values = [""];
                fallbackModel.value = "";
                app.graph.setDirtyCanvas(true);
                return;
            }
            const models = await fetchJson(`${API_BASE}/models?family=${encodeURIComponent(family)}&provider_id=${encodeURIComponent(targetProvider)}`);
            const safeModels = Array.isArray(models) ? models.filter(Boolean) : [];
            const fallbackChoices = ["", ...safeModels];
            fallbackModel.options.values = fallbackChoices;
            if (!fallbackChoices.includes(fallbackModel.value)) fallbackModel.value = safeModels[0] || "";
            app.graph.setDirtyCanvas(true);
        } catch (err) {
            console.warn("[Hhhapi.Image]", err);
        }
    }

    const oldProviderCallback = provider.callback;
    provider.callback = function(value) {
        if (oldProviderCallback) oldProviderCallback.call(this, value);
        if (fallbackProvider && (!fallbackProvider.value || fallbackProvider.value === value)) {
            fallbackProvider.value = value;
        }
        refreshModels();
        refreshFallbackModels();
    };

    if (fallbackProvider) {
        const oldFallbackProviderCallback = fallbackProvider.callback;
        fallbackProvider.callback = function(value) {
            if (oldFallbackProviderCallback) oldFallbackProviderCallback.call(this, value);
            if (!value) fallbackProvider.value = provider.value;
            refreshFallbackModels();
        };
    }

    const oldModelCallback = model.callback;
    model.callback = function(value) {
        if (oldModelCallback) oldModelCallback.call(this, value);
        if (fallbackProvider && fallbackModel && fallbackProvider.value === provider.value && (!fallbackModel.value || fallbackModel.value === value)) {
            fallbackModel.value = value;
        }
        app.graph.setDirtyCanvas(true);
    };

    await refreshProvidersAndModels();
}

app.registerExtension({
    name: "Hhhapi.BltcyImage",
    async nodeCreated(node) {
        if (node.comfyClass === "HhhapiBltcyGPTImage") {
            await bindModelRefresh(node, "gpt", "柏拉图 GPT");
        }
        if (node.comfyClass === "HhhapiBltcyNanoImage") {
            await bindModelRefresh(node, "nano", "柏拉图 Nano");
        }
    },
});
