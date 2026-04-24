import { app } from "../../scripts/app.js";

const API_BASE = "/api/hhhapi/panel";

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
    if (document.getElementById("hhhapi-manager-style")) return;
    const style = el("style", { id: "hhhapi-manager-style" });
    style.textContent = `
        .hhhapi-modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;display:flex;align-items:center;justify-content:center}
        .hhhapi-modal{width:min(900px,92vw);max-height:88vh;overflow:auto;background:#262626;color:#ddd;border:1px solid #555;border-radius:8px;box-shadow:0 18px 60px rgba(0,0,0,.5);font:13px sans-serif}
        .hhhapi-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid #444}
        .hhhapi-title{font-size:16px;font-weight:700}
        .hhhapi-close,.hhhapi-btn{background:#3a3a3a;color:#eee;border:1px solid #666;border-radius:6px;padding:6px 10px;cursor:pointer}
        .hhhapi-close:hover,.hhhapi-btn:hover{background:#4a4a4a}
        .hhhapi-danger{border-color:#985252;background:#583232}
        .hhhapi-primary{border-color:#4d7fa8;background:#28506d}
        .hhhapi-body{display:grid;grid-template-columns:220px 1fr;gap:14px;padding:14px}
        .hhhapi-list{border:1px solid #444;border-radius:6px;overflow:hidden}
        .hhhapi-item{padding:9px 10px;border-bottom:1px solid #3a3a3a;cursor:pointer}
        .hhhapi-item:hover,.hhhapi-item.active{background:#3a4b59}
        .hhhapi-form{display:grid;grid-template-columns:1fr 1fr;gap:10px}
        .hhhapi-field{display:flex;flex-direction:column;gap:5px}
        .hhhapi-field input,.hhhapi-field textarea{background:#191919;color:#eee;border:1px solid #555;border-radius:5px;padding:7px}
        .hhhapi-wide{grid-column:1/-1}
        .hhhapi-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
        .hhhapi-model-row{display:grid;grid-template-columns:minmax(220px,1fr) auto;gap:8px;margin-bottom:8px;align-items:start}
        .hhhapi-model-meta{display:flex;flex-direction:column;gap:8px}
        .hhhapi-model-caps{display:flex;gap:10px;flex-wrap:wrap}
        .hhhapi-check{display:flex;align-items:center;gap:6px;color:#bbb}
        .hhhapi-check input{accent-color:#6aa7d8}
        .hhhapi-muted{color:#aaa}
        .hhhapi-status{margin-top:10px;min-height:18px;color:#a8d59d}
    `;
    document.head.appendChild(style);
}

function capabilityCheckbox(label, cls, checked = false) {
    const input = el("input", { type: "checkbox" });
    input.checked = checked;
    return el("label", { class: `hhhapi-check ${cls}` }, [input, el("span", { text: label })]);
}

function createModelRow(model = {}) {
    const nameInput = el("input", { value: model.name || model.id || "", placeholder: "模型名" });
    const caps = new Set(model.capabilities || []);
    const vision = capabilityCheckbox("视觉", "cap-vision", caps.has("vision_input"));
    const json = capabilityCheckbox("JSON", "cap-json", caps.has("json_object"));
    const reasoning = capabilityCheckbox("思考链", "cap-reasoning", caps.has("reasoning_output"));
    const minimaxVision = capabilityCheckbox("MiniMax识图", "cap-minimax-vision", caps.has("minimax_understand_image"));
    minimaxVision.querySelector("input").onchange = () => {
        if (minimaxVision.querySelector("input").checked) {
            vision.querySelector("input").checked = true;
        }
    };
    const del = el("button", { class: "hhhapi-btn hhhapi-danger", text: "删除" });
    del.onclick = () => row.remove();
    const meta = el("div", { class: "hhhapi-model-meta" }, [
        nameInput,
        el("div", { class: "hhhapi-model-caps" }, [vision, json, reasoning, minimaxVision]),
    ]);
    const row = el("div", { class: "hhhapi-model-row" }, [meta, del]);
    return row;
}

async function openManager() {
    cssOnce();
    const backdrop = el("div", { class: "hhhapi-modal-backdrop" });
    const modal = el("div", { class: "hhhapi-modal" });
    const list = el("div", { class: "hhhapi-list" });
    const status = el("div", { class: "hhhapi-status" });

    const providerId = el("input", { autocomplete: "off", spellcheck: "false" });
    const providerName = el("input", { autocomplete: "off", spellcheck: "false" });
    const baseUrl = el("input", { autocomplete: "off", spellcheck: "false", inputmode: "url" });
    const apiKey = el("input", { type: "password", placeholder: "留空则不修改已保存密钥", autocomplete: "new-password", spellcheck: "false" });
    const apiPath = el("input", { value: "/chat/completions", autocomplete: "off", spellcheck: "false" });
    const modelsBox = el("div", { class: "hhhapi-wide" });

    let providers = [];
    let current = null;

    function setStatus(text, isError = false) {
        status.textContent = text;
        status.style.color = isError ? "#ffb0a8" : "#a8d59d";
    }

    function modelRows(models = []) {
        modelsBox.innerHTML = "";
        modelsBox.appendChild(el("div", { class: "hhhapi-muted", text: "模型列表" }));
        for (const model of models) {
            modelsBox.appendChild(createModelRow(model));
        }
    }

    function readModels() {
        return Array.from(modelsBox.querySelectorAll(".hhhapi-model-row"))
            .map(row => {
                const name = row.querySelector(".hhhapi-model-meta > input")?.value?.trim() || "";
                if (!name) return null;
                const capabilities = ["text"];
                if (row.querySelector(".cap-vision input")?.checked) capabilities.push("vision_input");
                if (row.querySelector(".cap-json input")?.checked) capabilities.push("json_object");
                if (row.querySelector(".cap-reasoning input")?.checked) capabilities.push("reasoning_output");
                if (row.querySelector(".cap-minimax-vision input")?.checked) {
                    capabilities.push("minimax_understand_image");
                    if (!capabilities.includes("vision_input")) capabilities.push("vision_input");
                }
                return {
                id: name,
                name,
                task_types: ["text"],
                profile_id: "openai_chat",
                capabilities,
            };
            })
            .filter(Boolean);
    }

    function firstModelName() {
        const input = modelsBox.querySelector(".hhhapi-model-meta > input");
        return input?.value?.trim() || "";
    }

    function fill(provider, hasKey = false) {
        current = provider || null;
        providerId.value = provider?.id || "";
        providerName.value = provider?.name || "";
        baseUrl.value = provider?.base_urls?.[0] || "";
        apiPath.value = provider?.profiles?.[0]?.path || "/chat/completions";
        apiKey.value = "";
        apiKey.placeholder = hasKey ? "已保存密钥，留空不修改" : "请输入 API Key";
        modelRows(provider?.models || []);
    }

    async function loadProviders(selectId = "") {
        providers = await fetchJson(`${API_BASE}/providers_list`);
        list.innerHTML = "";
        for (const provider of providers) {
            const item = el("div", { class: "hhhapi-item", text: `${provider.name || provider.id} (${provider.id})` });
            item.onclick = async () => {
                Array.from(list.children).forEach(x => x.classList.remove("active"));
                item.classList.add("active");
                const detail = await fetchJson(`${API_BASE}/provider_detail?provider_id=${encodeURIComponent(provider.id)}`);
                fill(detail.provider, detail.has_api_key);
            };
            list.appendChild(item);
            if (provider.id === selectId) setTimeout(() => item.click(), 0);
        }
        if (!selectId && list.firstChild) list.firstChild.click();
    }

    async function saveProvider() {
        const id = providerId.value.trim();
        if (!id) return setStatus("服务商ID不能为空", true);
        const models = readModels();
        if (!models.length) return setStatus("至少需要一个模型", true);
        const provider = {
            id,
            name: providerName.value.trim() || id,
            enabled: true,
            base_urls: [baseUrl.value.trim().replace(/\/+$/, "")],
            auth: { type: "bearer", header: "Authorization", prefix: "Bearer " },
            profiles: [{
                id: "openai_chat",
                task_types: ["text"],
                protocol: "openai_chat_completions",
                path: apiPath.value.trim() || "/chat/completions",
                method: "POST",
            }],
            models,
        };
        const saved = await fetchJson(`${API_BASE}/save_provider?data=${encodeURIComponent(JSON.stringify(provider))}`);
        if (apiKey.value.trim()) {
            await fetchJson(`${API_BASE}/provider_secret?provider_id=${encodeURIComponent(id)}&api_key=${encodeURIComponent(apiKey.value.trim())}`);
            apiKey.value = "";
            apiKey.placeholder = "已保存密钥，留空不修改";
        }
        setStatus("已保存服务商配置");
        await loadProviders(saved.provider.id);
    }

    async function deleteProvider() {
        const id = providerId.value.trim();
        if (!id) return;
        if (!confirm(`确定删除服务商 ${id}？`)) return;
        await fetchJson(`${API_BASE}/delete_provider?provider_id=${encodeURIComponent(id)}`);
        setStatus("已删除服务商");
        fill(null);
        await loadProviders();
    }

    const addModel = el("button", { class: "hhhapi-btn", text: "新增模型" });
    addModel.onclick = () => {
        modelsBox.appendChild(createModelRow({}));
    };

    const newProvider = el("button", { class: "hhhapi-btn", text: "新建服务商" });
    newProvider.onclick = () => fill({
        id: "",
        name: "",
        base_urls: [""],
        profiles: [{ path: "/chat/completions" }],
        models: [],
    }, false);

    const save = el("button", { class: "hhhapi-btn hhhapi-primary", text: "保存" });
    save.onclick = () => saveProvider().catch(e => setStatus(e.message, true));

    const delProvider = el("button", { class: "hhhapi-btn hhhapi-danger", text: "删除服务商" });
    delProvider.onclick = () => deleteProvider().catch(e => setStatus(e.message, true));

    const testProvider = el("button", { class: "hhhapi-btn", text: "测试连接" });
    testProvider.onclick = async () => {
        try {
            const id = providerId.value.trim();
            const model = firstModelName();
            if (!id) return setStatus("服务商ID不能为空", true);
            if (!model) return setStatus("至少需要一个模型", true);
            setStatus("正在测试连接...");
            const result = await fetchJson(`${API_BASE}/test_provider?provider_id=${encodeURIComponent(id)}&model=${encodeURIComponent(model)}&prompt=${encodeURIComponent("请回复：连接成功")}`);
            if (!result.ok) return setStatus(result.message || "测试失败", true);
            setStatus(`测试成功：${String(result.text || "").slice(0, 80)}`);
        } catch (e) {
            setStatus(e.message, true);
        }
    };

    modal.appendChild(el("div", { class: "hhhapi-head" }, [
        el("div", { class: "hhhapi-title", text: "Hhh 文本API服务商管理" }),
        el("button", { class: "hhhapi-close", text: "关闭" }),
    ]));
    modal.querySelector(".hhhapi-close").onclick = () => backdrop.remove();

    modal.appendChild(el("div", { class: "hhhapi-body" }, [
        el("div", {}, [list, el("div", { class: "hhhapi-actions" }, [newProvider])]),
        el("div", { class: "hhhapi-form" }, [
            field("服务商ID", providerId),
            field("显示名称", providerName),
            field("接口地址", baseUrl),
            field("API密钥", apiKey),
            field("接口路径", apiPath),
            el("div"),
            modelsBox,
            el("div", { class: "hhhapi-actions hhhapi-wide" }, [addModel, save, testProvider, delProvider]),
            status,
        ]),
    ]));
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);

    try {
        await loadProviders();
    } catch (e) {
        setStatus(e.message, true);
    }
}

app.registerExtension({
    name: "Hhhapi.Manager",
    async nodeCreated(node) {
        if (node.comfyClass !== "HhhapiProviderManager") return;
        if (node.__hhhapiManagerButtonAdded) return;
        node.__hhhapiManagerButtonAdded = true;
        node.addWidget("button", "打开管理面板", null, () => openManager());
        node.setSize([Math.max(node.size?.[0] || 260, 300), Math.max(node.size?.[1] || 100, 130)]);
    },
    setup() {
        const originalGetExtraMenuOptions = app.getExtraMenuOptions;
        app.getExtraMenuOptions = function(canvas, options) {
            originalGetExtraMenuOptions?.apply(this, arguments);
            options.push(null);
            options.push({
                content: "Hhh 文本API服务商管理",
                callback: openManager,
            });
        };
    },
});
