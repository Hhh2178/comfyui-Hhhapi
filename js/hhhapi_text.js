import { app } from "../../scripts/app.js";

const API_BASE = "/api/hhhapi/v1";

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

function getInputLinked(node, name) {
    const input = (node.inputs || []).find(x => x.name === name);
    return !!input?.link;
}

function ensureChannelBadge(node) {
    if (node.__hhhapiChannelBadgeReady) return;
    node.__hhhapiChannelBadgeReady = true;
    node.__hhhapiChannelLabel = "文本通道";

    const originalDrawForeground = node.onDrawForeground;
    node.onDrawForeground = function(ctx) {
        if (originalDrawForeground) originalDrawForeground.call(this, ctx);
        const label = this.__hhhapiChannelLabel;
        if (!label || this.flags?.collapsed) return;
        ctx.save();
        ctx.font = "12px sans-serif";
        const paddingX = 8;
        const textWidth = ctx.measureText(label).width;
        const boxWidth = textWidth + 14;
        const x = Math.max(8, (this.size?.[0] || 220) - boxWidth - 12);
        const y = 28;
        ctx.fillStyle = "rgba(32, 32, 32, 0.88)";
        ctx.fillRect(x, y - 12, boxWidth, 18);
        ctx.strokeStyle = "rgba(120, 120, 120, 0.8)";
        ctx.strokeRect(x, y - 12, boxWidth, 18);
        ctx.fillStyle = label.includes("识图") ? "#7dd3fc" : label.includes("视觉") ? "#c4b5fd" : "#cbd5e1";
        ctx.fillText(label, x + paddingX, y + 1);
        ctx.restore();
    };
}

function bindPromptPersistence(node, systemWidget, userWidget) {
    node.properties = node.properties || {};
    const saved = node.properties.hhhapi_prompts || {};
    if (typeof saved.system === "string") systemWidget.value = saved.system;
    if (typeof saved.user === "string") userWidget.value = saved.user;

    const persist = () => {
        node.properties.hhhapi_prompts = {
            system: systemWidget.value || "",
            user: userWidget.value || "",
        };
    };

    const oldSystemSerialize = systemWidget.serializeValue?.bind(systemWidget);
    systemWidget.serializeValue = () => {
        persist();
        return oldSystemSerialize ? oldSystemSerialize() : systemWidget.value;
    };

    const oldUserSerialize = userWidget.serializeValue?.bind(userWidget);
    userWidget.serializeValue = () => {
        persist();
        return oldUserSerialize ? oldUserSerialize() : userWidget.value;
    };

    const oldSystemCallback = systemWidget.callback;
    systemWidget.callback = function(value) {
        if (oldSystemCallback) oldSystemCallback.call(this, value);
        persist();
    };

    const oldUserCallback = userWidget.callback;
    userWidget.callback = function(value) {
        if (oldUserCallback) oldUserCallback.call(this, value);
        persist();
    };

    persist();
}

app.registerExtension({
    name: "Hhhapi.Text",

    async nodeCreated(node) {
        if (node.comfyClass !== "HhhapiText") return;
        await new Promise(resolve => setTimeout(resolve, 100));

        const w = byName(node);
        const provider = w["服务商"];
        const model = w["模型"];
        const systemPrompt = w["系统提示词"];
        const userPrompt = w["用户提示词"];
        if (!provider || !model) return;
        ensureChannelBadge(node);
        if (systemPrompt && userPrompt) bindPromptPersistence(node, systemPrompt, userPrompt);

        async function updateChannelBadge() {
            try {
                const providerId = provider.value || "";
                const modelId = model.value || "";
                const hasImage = getInputLinked(node, "参考图片");
                if (!providerId || !modelId) {
                    node.__hhhapiChannelLabel = hasImage ? "视觉文本通道" : "文本通道";
                    app.graph.setDirtyCanvas(true);
                    return;
                }
                const detail = await fetchJson(`${API_BASE}/provider?provider_id=${encodeURIComponent(providerId)}`);
                const models = detail?.provider?.models || [];
                const current = models.find(x => x.id === modelId || x.name === modelId) || {};
                const caps = new Set(current.capabilities || []);
                if (hasImage && caps.has("minimax_understand_image")) {
                    node.__hhhapiChannelLabel = "MiniMax识图通道";
                } else if (hasImage) {
                    node.__hhhapiChannelLabel = "视觉文本通道";
                } else {
                    node.__hhhapiChannelLabel = "文本通道";
                }
                app.graph.setDirtyCanvas(true);
            } catch (err) {
                console.warn("[Hhhapi] channel badge", err);
            }
        }

        async function refreshProviders() {
            const providers = await fetchJson(`${API_BASE}/providers`);
            const ids = providers.map(p => p.id).filter(Boolean);
            if (ids.length) {
                provider.options.values = ids;
                if (!ids.includes(provider.value)) provider.value = ids[0];
            }
        }

        async function refreshModels() {
            const models = await fetchJson(`${API_BASE}/models?provider_id=${encodeURIComponent(provider.value || "")}`);
            if (Array.isArray(models) && models.length) {
                model.options.values = models;
                if (!models.includes(model.value)) model.value = models[0];
            }
            await updateChannelBadge();
            app.graph.setDirtyCanvas(true);
        }

        async function refreshAll() {
            try {
                await refreshProviders();
                await refreshModels();
                await updateChannelBadge();
            } catch (err) {
                console.warn("[Hhhapi]", err);
            }
        }

        const oldProviderCallback = provider.callback;
        provider.callback = function(value) {
            if (oldProviderCallback) oldProviderCallback.call(this, value);
            refreshModels();
        };

        const oldModelCallback = model.callback;
        model.callback = function(value) {
            if (oldModelCallback) oldModelCallback.call(this, value);
            updateChannelBadge();
        };

        const oldConnectionsChange = node.onConnectionsChange;
        node.onConnectionsChange = function(...args) {
            const result = oldConnectionsChange ? oldConnectionsChange.apply(this, args) : undefined;
            updateChannelBadge();
            return result;
        };

        await refreshAll();
    },
});
