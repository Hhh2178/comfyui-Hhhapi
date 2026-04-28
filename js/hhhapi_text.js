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

function firstWidget(widgets, names) {
    for (const name of names) {
        if (widgets[name]) return widgets[name];
    }
    return null;
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
        ctx.font = "11px sans-serif";
        const paddingX = 7;
        const textWidth = ctx.measureText(label).width;
        const boxWidth = textWidth + 14;
        const x = Math.min(98, Math.max(8, (this.size?.[0] || 220) - boxWidth - 40));
        const y = 8;
        ctx.fillStyle = "rgba(34, 34, 34, 0.92)";
        ctx.fillRect(x, y - 9, boxWidth, 16);
        ctx.strokeStyle = "rgba(120, 120, 120, 0.65)";
        ctx.strokeRect(x, y - 9, boxWidth, 16);
        ctx.fillStyle = label.includes("识图") ? "#7dd3fc" : label.includes("视觉") ? "#c4b5fd" : "#cbd5e1";
        ctx.fillText(label, x + paddingX, y + 2);
        ctx.restore();
    };
}

function normalizeLegacyVisualModeWidgets(node, widgets) {
    const visualMode = widgets["视觉结果模式"];
    const temperature = widgets["温度"];
    const maxTokens = widgets["最大Token数"];
    const seed = widgets["随机种子"];
    const responseFormat = widgets["响应格式"];
    const timeout = widgets["超时秒数"];
    if (!visualMode || !temperature || !maxTokens || !seed || !responseFormat || !timeout) return;

    const visualOptions = visualMode.options?.values || [];
    const responseOptions = responseFormat.options?.values || [];
    const visualValid = visualOptions.includes(visualMode.value);
    const responseValid = responseOptions.includes(responseFormat.value);
    const legacyShifted = !visualValid
        && typeof visualMode.value === "number"
        && typeof temperature.value === "number"
        && typeof maxTokens.value === "number"
        && !responseValid
        && typeof responseFormat.value === "number";

    if (!legacyShifted) return;

    const oldVisualMode = visualMode.value;
    const oldTemperature = temperature.value;
    const oldMaxTokens = maxTokens.value;
    const oldResponseFormat = responseFormat.value;

    visualMode.value = "自动";
    temperature.value = Number.isFinite(oldVisualMode) ? oldVisualMode : 0.7;
    maxTokens.value = Number.isFinite(oldTemperature) ? Math.max(1, Math.trunc(oldTemperature)) : 50000;
    seed.value = Number.isFinite(oldMaxTokens) ? Math.trunc(oldMaxTokens) : -1;
    responseFormat.value = "文本";
    timeout.value = Number.isFinite(oldResponseFormat) ? Math.max(1, Math.trunc(oldResponseFormat)) : 120;

    node.properties = node.properties || {};
    node.properties.hhhapi_visual_mode_fixed = true;
    console.warn("[Hhhapi] 已自动修正旧版节点的视觉模式参数错位。");
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
        const fallbackProvider = firstWidget(w, ["输出为空时替代服务商", "失败时替代服务商"]);
        const fallbackModel = firstWidget(w, ["输出为空时替代模型", "失败时替代模型"]);
        const systemPrompt = w["系统提示词"];
        const userPrompt = w["用户提示词"];
        const visualMode = w["视觉结果模式"];
        if (!provider || !model) return;
        normalizeLegacyVisualModeWidgets(node, w);
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
                const current = models.find(x => x.id === modelId || x.name === modelId || x.label === modelId) || {};
                const caps = new Set(current.capabilities || []);
                const selectedVisualMode = visualMode?.value || "自动";
                if (hasImage && caps.has("minimax_understand_image")) {
                    node.__hhhapiChannelLabel = (selectedVisualMode === "二段式整理输出" || selectedVisualMode === "自动")
                        ? "MiniMax二段式通道"
                        : "MiniMax识图通道";
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
                if (fallbackProvider) {
                    const fallbackProviderChoices = ["", ...ids];
                    const preferredFallback = ids.find(id => id !== provider.value) || ids[0] || "";
                    const shouldRepair = !fallbackProvider.value || !fallbackProviderChoices.includes(fallbackProvider.value);
                    fallbackProvider.options.values = fallbackProviderChoices;
                    if (shouldRepair) fallbackProvider.value = preferredFallback;
                }
            }
        }

        async function refreshModels() {
            const models = await fetchJson(`${API_BASE}/models?provider_id=${encodeURIComponent(provider.value || "")}`);
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
            await updateChannelBadge();
            app.graph.setDirtyCanvas(true);
        }

        async function refreshFallbackModels() {
            if (!fallbackModel) return;
            const targetProvider = fallbackProvider?.value || "";
            if (!targetProvider) {
                fallbackModel.options.values = [""];
                fallbackModel.value = "";
                app.graph.setDirtyCanvas(true);
                return;
            }
            const models = await fetchJson(`${API_BASE}/models?provider_id=${encodeURIComponent(targetProvider)}`);
            const safeModels = Array.isArray(models) ? models.filter(Boolean) : [];
            const fallbackChoices = ["", ...safeModels];
            fallbackModel.options.values = fallbackChoices;
            if (!fallbackChoices.includes(fallbackModel.value)) fallbackModel.value = safeModels[0] || "";
            app.graph.setDirtyCanvas(true);
        }

        async function refreshAll() {
            try {
                await refreshProviders();
                await refreshModels();
                await refreshFallbackModels();
                await updateChannelBadge();
            } catch (err) {
                console.warn("[Hhhapi]", err);
            }
        }

        const oldProviderCallback = provider.callback;
        provider.callback = function(value) {
            if (oldProviderCallback) oldProviderCallback.call(this, value);
            if (fallbackProvider && (!fallbackProvider.value || fallbackProvider.value === value)) {
                const ids = (provider.options?.values || []).filter(Boolean);
                fallbackProvider.value = ids.find(id => id !== value) || value || "";
            }
            refreshModels();
            refreshFallbackModels();
        };

        if (fallbackProvider) {
            const oldFallbackProviderCallback = fallbackProvider.callback;
            fallbackProvider.callback = function(value) {
                fallbackProvider.value = value;
                if (oldFallbackProviderCallback) oldFallbackProviderCallback.call(this, value);
                fallbackProvider.value = value;
                refreshFallbackModels();
            };
        }

        const oldModelCallback = model.callback;
        model.callback = function(value) {
            if (oldModelCallback) oldModelCallback.call(this, value);
            if (fallbackProvider && fallbackModel && fallbackProvider.value === provider.value && (!fallbackModel.value || fallbackModel.value === value)) {
                fallbackModel.value = value;
            }
            updateChannelBadge();
        };

        if (visualMode) {
            const oldVisualModeCallback = visualMode.callback;
            visualMode.callback = function(value) {
                if (oldVisualModeCallback) oldVisualModeCallback.call(this, value);
                updateChannelBadge();
            };
        }

        const oldConnectionsChange = node.onConnectionsChange;
        node.onConnectionsChange = function(...args) {
            const result = oldConnectionsChange ? oldConnectionsChange.apply(this, args) : undefined;
            updateChannelBadge();
            return result;
        };

        await refreshAll();
    },
});
