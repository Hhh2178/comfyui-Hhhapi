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
    const model = widgets["模型"];
    if (!model) return;

    ensureBadge(node, familyLabel);

    async function refreshModels() {
        try {
            const models = await fetchJson(`${API_BASE}/models?family=${encodeURIComponent(family)}`);
            if (Array.isArray(models) && models.length) {
                model.options.values = models;
                if (!models.includes(model.value)) model.value = models[0];
            }
            app.graph.setDirtyCanvas(true);
        } catch (err) {
            console.warn("[Hhhapi.Image]", err);
        }
    }

    await refreshModels();
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
