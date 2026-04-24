import json

from . import provider_store
from .secret_store import save_node_api_key, save_provider_api_key
from .utils.response import dumps

TASK_TYPE_LABELS = {
    "文本": "text",
    "text": "text",
}


class HhhapiProvider:
    @classmethod
    def INPUT_TYPES(cls):
        providers = provider_store.provider_ids()
        provider_id = providers[0]
        profiles = provider_store.profile_ids(provider_id)
        profile_id = profiles[0]
        bases = provider_store.base_urls(provider_id)
        models = provider_store.model_names(provider_id=provider_id, profile_id=profile_id)
        return {
            "required": {
                "任务类型": (["文本"], {"default": "文本"}),
                "服务商": (providers, {"default": provider_id}),
                "接口配置": (profiles, {"default": profile_id}),
                "接口地址": (bases, {"default": bases[0]}),
                "模型": (models, {"default": models[0]}),
                "API密钥": ("STRING", {"default": ""}),
                "超时秒数": ("INT", {"default": 120, "min": 1, "max": 3600, "step": 1}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("服务商配置", "服务商ID", "模型")
    FUNCTION = "build_config"
    CATEGORY = "Hhh/文本API"

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def build_config(self, 任务类型="文本", 服务商="", 接口配置="", **kwargs):
        base_url = kwargs.get("接口地址", kwargs.get("Base URL", kwargs.get("base_url", "")))
        model = kwargs.get("模型", kwargs.get("model", ""))
        api_key = kwargs.get("API密钥", kwargs.get("api_key", ""))
        timeout = kwargs.get("超时秒数", kwargs.get("timeout", 120))
        task_type = TASK_TYPE_LABELS.get(任务类型, 任务类型)
        plain_key = (api_key or "").strip()
        if plain_key and "•" not in plain_key:
            save_node_api_key(kwargs.get("unique_id"), 服务商, plain_key)
        config = provider_store.build_runtime_config(
            task_type=task_type,
            provider_id=服务商,
            profile_id=接口配置,
            base_url=base_url,
            model=model,
            node_id=kwargs.get("unique_id"),
            timeout=timeout,
        )
        return (dumps(config), 服务商, model)


class HhhapiProviderManager:
    ACTION_LABELS = {
        "列出服务商": "list_providers",
        "快速新增文本服务商": "quick_add_text_provider",
        "保存完整服务商JSON": "upsert_provider",
        "删除服务商": "delete_provider",
        "保存模型JSON": "upsert_model",
        "删除模型": "delete_model",
        "新增Base URL": "add_base_url",
        "删除Base URL": "delete_base_url",
        "保存API密钥": "save_provider_api_key",
        "导出配置": "export_config",
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "操作": (["打开管理面板提示", "导出配置"], {"default": "打开管理面板提示"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("结果JSON",)
    FUNCTION = "manage"
    CATEGORY = "Hhh/文本API"

    def manage(self, 操作="列出服务商", **kwargs):
        if 操作 == "打开管理面板提示":
            return (dumps({
                "ok": True,
                "message": "请在画布右键菜单或设置按钮中打开「Hhh 文本API服务商管理」面板。",
            }),)
        if 操作 == "导出配置":
            return (dumps({"ok": True, "config": provider_store.load_config()}),)

        provider_id = kwargs.get("服务商ID", kwargs.get("provider_id", ""))
        model_id = kwargs.get("模型ID", kwargs.get("model_id", ""))
        base_url = kwargs.get("接口地址", kwargs.get("Base URL", kwargs.get("base_url", "")))
        api_key = kwargs.get("API密钥", kwargs.get("api_key", ""))
        json_payload = kwargs.get("JSON内容", kwargs.get("json_payload", ""))
        action = self.ACTION_LABELS.get(操作, 操作)
        try:
            if action == "list_providers":
                return (dumps({"ok": True, "providers": provider_store.list_providers("text")}),)
            if action == "export_config":
                return (dumps({"ok": True, "config": provider_store.load_config()}),)
            if action == "upsert_provider":
                provider = json.loads(json_payload)
                return (dumps({"ok": True, "provider": provider_store.upsert_provider(provider)}),)
            if action == "quick_add_text_provider":
                data = json.loads(json_payload)
                provider = provider_store.make_text_provider(
                    provider_id=provider_id or data.get("id", ""),
                    name=data.get("name", ""),
                    base_url=base_url or data.get("base_url", ""),
                    model_name=model_id or data.get("model", ""),
                    api_path=data.get("api_path", "/chat/completions"),
                )
                saved_provider = provider_store.upsert_provider(provider)
                if api_key:
                    save_provider_api_key(saved_provider.get("id", ""), api_key)
                return (dumps({"ok": True, "provider": saved_provider, "api_key_saved": bool(api_key)}),)
            if action == "delete_provider":
                provider_store.delete_provider(provider_id)
                return (dumps({"ok": True}),)
            if action == "upsert_model":
                model = json.loads(json_payload)
                return (dumps({"ok": True, "model": provider_store.upsert_model(provider_id, model)}),)
            if action == "delete_model":
                provider_store.delete_model(provider_id, model_id)
                return (dumps({"ok": True}),)
            if action == "add_base_url":
                return (dumps({"ok": True, "base_urls": provider_store.add_base_url(provider_id, base_url)}),)
            if action == "delete_base_url":
                return (dumps({"ok": True, "base_urls": provider_store.delete_base_url(provider_id, base_url)}),)
            if action == "save_provider_api_key":
                save_provider_api_key(provider_id, api_key)
                return (dumps({"ok": True, "message": "API key saved"}),)
            return (dumps({"ok": False, "message": f"unknown action: {action}"}),)
        except Exception as exc:
            return (dumps({"ok": False, "message": str(exc)}),)
