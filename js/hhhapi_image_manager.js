import { app } from "../../scripts/app.js";

const API_BASE = "/api/hhhapi/image/panel";

async function fetchJson(url, options) {
    const resp = await fetch(url, options);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.message || `${resp.status} ${resp.statusText}`);
    return data;
}

function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
        if (key === "class") node.className = value;
        else if (key === "text") node.textContent = value;
        else if (key === "html") node.innerHTML = value;
        else node.setAttribute(key, value);
    }
    for (const child of children) node.appendChild(child);
    return node;
}

function field(label, input) {
    return el("label", { class: "hhhapi-field" }, [
        el("span", { text: label }),
        input,
    ]);
}

function cssOnce() {
    if (document.getElementById("hhhapi-image-manager-style")) return;
    const style = el("style", { id: "hhhapi-image-manager-style" });
    style.textContent = `
        .hhhapi-modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;display:flex;align-items:center;justify-content:center}
        .hhhapi-modal{width:min(920px,94vw);max-height:88vh;overflow:auto;background:#262626;color:#ddd;border:1px solid #555;border-radius:8px;box-shadow:0 18px 60px rgba(0,0,0,.5);font:13px sans-serif}
        .hhhapi-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid #444}
        .hhhapi-title{font-size:16px;font-weight:700}
        .hhhapi-close,.hhhapi-btn{background:#3a3a3a;color:#eee;border:1px solid #666;border-radius:6px;padding:6px 10px;cursor:pointer}
        .hhhapi-close:hover,.hhhapi-btn:hover{background:#4a4a4a}
        .hhhapi-primary{border-color:#4d7fa8;background:#28506d}
        .hhhapi-body{padding:14px;display:grid;grid-template-columns:1fr 1fr;gap:14px}
        .hhhapi-form{display:grid;grid-template-columns:1fr 1fr;gap:10px}
        .hhhapi-field{display:flex;flex-direction:column;gap:5px}
        .hhhapi-field input,.hhhapi-field textarea{background:#191919;color:#eee;border:1px solid #555;border-radius:5px;padding:7px}
        .hhhapi-panel{border:1px solid #444;border-radius:6px;padding:12px;background:#222}
        .hhhapi-panel-title{font-weight:700;margin-bottom:10px}
        .hhhapi-model-row{display:grid;grid-template-columns:minmax(220px,1fr) auto;gap:8px;margin-bottom:8px;align-items:center}
        .hhhapi-wide{grid-column:1/-1}
        .hhhapi-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
        .hhhapi-muted{color:#aaa}
        .hhhapi-status{margin-top:10px;min-height:18px;color:#a8d59d}
    `;
    document.head.appendChild(style);
}

function createModelRow(model = "") {
    const input = el("input", { value: model, placeholder: "模型名" });
    const del = el("button", { class: "hhhapi-btn", text: "删除" });
    const row = el("div", { class: "hhhapi-model-row" }, [input, del]);
    del.onclick = () => row.remove();
    return row;
}

async function openManager() {
    cssOnce();
    const backdrop = el("div", { class: "hhhapi-modal-backdrop" });
    const modal = el("div", { class: "hhhapi-modal" });
    const status = el("div", { class: "hhhapi-status" });

    const baseUrl = el("input", { autocomplete: "off", spellcheck: "false", inputmode: "url" });
    const timeout = el("input", { type: "number", value: "120", min: "1", max: "3600", step: "1" });
    const apiKey = el("input", { type: "password", placeholder: "留空则不修改已保存密钥", autocomplete: "new-password", spellcheck: "false" });

    const gptModelsBox = el("div");
    const nanoModelsBox = el("div");

    function setStatus(text, isError = false) {
        status.textContent = text;
        status.style.color = isError ? "#ffb0a8" : "#a8d59d";
    }

    function fillModelRows(box, models = []) {
        box.innerHTML = "";
        for (const model of models) {
            box.appendChild(createModelRow(model));
        }
    }

    function readModels(box) {
        return Array.from(box.querySelectorAll(".hhhapi-model-row input"))
            .map(input => input.value.trim())
            .filter(Boolean);
    }

    function fill(config, hasKey = false) {
        const platform = config?.platform || {};
        const families = platform.families || {};
        baseUrl.value = platform.base_url || "https://api.bltcy.ai/v1";
        timeout.value = String(platform.timeout || 120);
        apiKey.value = "";
        apiKey.placeholder = hasKey ? "已保存密钥，留空不修改" : "请输入 API Key";
        fillModelRows(gptModelsBox, families.gpt?.models || []);
        fillModelRows(nanoModelsBox, families.nano?.models || []);
    }

    async function loadConfig() {
        const result = await fetchJson(`${API_BASE}/config`);
        fill(result.config, result.has_api_key);
    }

    async function saveConfig() {
        const payload = {
            platform: {
                base_url: baseUrl.value.trim(),
                timeout: Number(timeout.value || 120),
                families: {
                    gpt: { models: readModels(gptModelsBox) },
                    nano: { models: readModels(nanoModelsBox) },
                },
            },
        };
        if (!payload.platform.families.gpt.models.length) return setStatus("GPT 模型至少需要一个", true);
        if (!payload.platform.families.nano.models.length) return setStatus("Nano 模型至少需要一个", true);
        await fetchJson(`${API_BASE}/save_config?data=${encodeURIComponent(JSON.stringify(payload))}`);
        if (apiKey.value.trim()) {
            await fetchJson(`${API_BASE}/provider_secret?api_key=${encodeURIComponent(apiKey.value.trim())}`);
            apiKey.value = "";
            apiKey.placeholder = "已保存密钥，留空不修改";
        }
        setStatus("已保存柏拉图图片配置");
        await loadConfig();
    }

    const addGptModel = el("button", { class: "hhhapi-btn", text: "新增 GPT 模型" });
    addGptModel.onclick = () => gptModelsBox.appendChild(createModelRow(""));

    const addNanoModel = el("button", { class: "hhhapi-btn", text: "新增 Nano 模型" });
    addNanoModel.onclick = () => nanoModelsBox.appendChild(createModelRow(""));

    const save = el("button", { class: "hhhapi-btn hhhapi-primary", text: "保存" });
    save.onclick = () => saveConfig().catch(e => setStatus(e.message, true));

    modal.appendChild(el("div", { class: "hhhapi-head" }, [
        el("div", { class: "hhhapi-title", text: "Hhh 柏拉图图片API管理" }),
        el("button", { class: "hhhapi-close", text: "关闭" }),
    ]));
    modal.querySelector(".hhhapi-close").onclick = () => backdrop.remove();

    modal.appendChild(el("div", { class: "hhhapi-body" }, [
        el("div", { class: "hhhapi-panel" }, [
            el("div", { class: "hhhapi-panel-title", text: "基础配置" }),
            el("div", { class: "hhhapi-form" }, [
                field("接口地址", baseUrl),
                field("超时秒数", timeout),
                field("API密钥", apiKey),
                el("div"),
            ]),
            el("div", { class: "hhhapi-muted", text: "节点中不会暴露 API Key，统一从这里维护。" }),
        ]),
        el("div", { class: "hhhapi-panel" }, [
            el("div", { class: "hhhapi-panel-title", text: "GPT 模型列表" }),
            gptModelsBox,
            el("div", { class: "hhhapi-actions" }, [addGptModel]),
        ]),
        el("div", { class: "hhhapi-panel" }, [
            el("div", { class: "hhhapi-panel-title", text: "Nano 模型列表" }),
            nanoModelsBox,
            el("div", { class: "hhhapi-actions" }, [addNanoModel]),
        ]),
        el("div", { class: "hhhapi-panel" }, [
            el("div", { class: "hhhapi-panel-title", text: "保存" }),
            el("div", { class: "hhhapi-muted", text: "这里保存的是柏拉图图片平台配置，不会影响现有文本服务商。" }),
            el("div", { class: "hhhapi-actions" }, [save]),
            status,
        ]),
    ]));

    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);

    try {
        await loadConfig();
    } catch (e) {
        setStatus(e.message, true);
    }
}

app.registerExtension({
    name: "Hhhapi.ImageManager",
    async nodeCreated(node) {
        if (node.comfyClass !== "HhhapiBltcyImageManager") return;
        if (node.__hhhapiImageManagerButtonAdded) return;
        node.__hhhapiImageManagerButtonAdded = true;
        node.addWidget("button", "打开管理面板", null, () => openManager());
        node.setSize([Math.max(node.size?.[0] || 260, 300), Math.max(node.size?.[1] || 100, 130)]);
    },
    setup() {
        const originalGetExtraMenuOptions = app.getExtraMenuOptions;
        app.getExtraMenuOptions = function(canvas, options) {
            originalGetExtraMenuOptions?.apply(this, arguments);
            options.push(null);
            options.push({
                content: "Hhh 柏拉图图片API管理",
                callback: openManager,
            });
        };
    },
});
