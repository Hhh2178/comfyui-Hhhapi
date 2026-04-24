import copy
import json
import os


BASE_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "hhhapi_config.json")

TASK_TYPES = ["text"]
TEXT_PROFILE_ID = "openai_chat"
TEXT_PROTOCOL = "openai_chat_completions"


DEFAULT_CONFIG = {
    "schema_version": "1.0",
    "default_provider_id": "openai_compatible",
    "providers": [
        {
            "id": "openai_compatible",
            "name": "OpenAI Compatible",
            "enabled": True,
            "base_urls": ["https://api.openai.com/v1"],
            "auth": {
                "type": "bearer",
                "header": "Authorization",
                "prefix": "Bearer ",
            },
            "profiles": [
                {
                    "id": "openai_chat",
                    "task_types": ["text"],
                    "protocol": "openai_chat_completions",
                    "path": "/chat/completions",
                    "method": "POST",
                },
            ],
            "models": [
                {
                    "id": "gpt-4.1",
                    "name": "gpt-4.1",
                    "task_types": ["text"],
                    "profile_id": "openai_chat",
                    "capabilities": ["text", "vision_input", "json_object"],
                },
            ],
        },
        {
            "id": "deepseek",
            "name": "DeepSeek Compatible",
            "enabled": True,
            "base_urls": ["https://api.deepseek.com"],
            "auth": {
                "type": "bearer",
                "header": "Authorization",
                "prefix": "Bearer ",
            },
            "profiles": [
                {
                    "id": "openai_chat",
                    "task_types": ["text"],
                    "protocol": "openai_chat_completions",
                    "path": "/chat/completions",
                    "method": "POST",
                }
            ],
            "models": [
                {
                    "id": "deepseek-chat",
                    "name": "deepseek-chat",
                    "task_types": ["text"],
                    "profile_id": "openai_chat",
                    "capabilities": ["text"],
                }
            ],
        },
        {
            "id": "qwen_compatible",
            "name": "Qwen Compatible",
            "enabled": True,
            "base_urls": ["https://dashscope.aliyuncs.com/compatible-mode/v1"],
            "auth": {
                "type": "bearer",
                "header": "Authorization",
                "prefix": "Bearer ",
            },
            "profiles": [
                {
                    "id": "openai_chat",
                    "task_types": ["text"],
                    "protocol": "openai_chat_completions",
                    "path": "/chat/completions",
                    "method": "POST",
                }
            ],
            "models": [
                {
                    "id": "qwen-plus",
                    "name": "qwen-plus",
                    "task_types": ["text"],
                    "profile_id": "openai_chat",
                    "capabilities": ["text"],
                },
                {
                    "id": "qwen-vl-plus",
                    "name": "qwen-vl-plus",
                    "task_types": ["text"],
                    "profile_id": "openai_chat",
                    "capabilities": ["text", "vision_input"],
                },
            ],
        },
        {
            "id": "doubao_compatible",
            "name": "Doubao Compatible",
            "enabled": True,
            "base_urls": ["https://ark.cn-beijing.volces.com/api/v3"],
            "auth": {
                "type": "bearer",
                "header": "Authorization",
                "prefix": "Bearer ",
            },
            "profiles": [
                {
                    "id": "openai_chat",
                    "task_types": ["text"],
                    "protocol": "openai_chat_completions",
                    "path": "/chat/completions",
                    "method": "POST",
                }
            ],
            "models": [
                {
                    "id": "doubao-seed-1-6",
                    "name": "doubao-seed-1-6",
                    "task_types": ["text"],
                    "profile_id": "openai_chat",
                    "capabilities": ["text"],
                }
            ],
        },
        {
            "id": "zhipu_compatible",
            "name": "Zhipu Compatible",
            "enabled": True,
            "base_urls": ["https://open.bigmodel.cn/api/paas/v4"],
            "auth": {
                "type": "bearer",
                "header": "Authorization",
                "prefix": "Bearer ",
            },
            "profiles": [
                {
                    "id": "openai_chat",
                    "task_types": ["text"],
                    "protocol": "openai_chat_completions",
                    "path": "/chat/completions",
                    "method": "POST",
                }
            ],
            "models": [
                {
                    "id": "glm-4.5",
                    "name": "glm-4.5",
                    "task_types": ["text"],
                    "profile_id": "openai_chat",
                    "capabilities": ["text"],
                }
            ],
        },
    ],
}


def default_text_profile(path="/chat/completions"):
    return {
        "id": TEXT_PROFILE_ID,
        "task_types": ["text"],
        "protocol": TEXT_PROTOCOL,
        "path": path or "/chat/completions",
        "method": "POST",
    }


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_config():
    if not os.path.exists(CONFIG_FILE):
        _write_json(CONFIG_FILE, DEFAULT_CONFIG)


def load_config():
    ensure_config()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("config root must be object")
        return migrate_text_only_config(data)
    except Exception:
        data = copy.deepcopy(DEFAULT_CONFIG)
        _write_json(CONFIG_FILE, data)
        return data


def save_config(config):
    _write_json(CONFIG_FILE, migrate_text_only_config(config))


def migrate_text_only_config(config):
    if not isinstance(config, dict):
        config = copy.deepcopy(DEFAULT_CONFIG)
    providers = []
    for provider in config.get("providers", []):
        if not isinstance(provider, dict):
            continue
        profiles = [
            p for p in provider.get("profiles", [])
            if isinstance(p, dict) and "text" in p.get("task_types", []) and p.get("protocol") == TEXT_PROTOCOL
        ]
        if not profiles:
            profiles = [default_text_profile()]
        profile_ids_set = {p.get("id") for p in profiles}
        models = []
        for model in provider.get("models", []):
            if not isinstance(model, dict):
                continue
            if "text" not in model.get("task_types", []):
                continue
            if model.get("profile_id") not in profile_ids_set:
                model["profile_id"] = profiles[0].get("id", TEXT_PROFILE_ID)
            model["task_types"] = ["text"]
            capabilities = model.get("capabilities", [])
            model["capabilities"] = [
                c for c in capabilities
                if c in {"text", "vision_input", "json_object", "tools", "reasoning_output", "minimax_understand_image"}
            ] or ["text"]
            provider_id_lower = str(provider.get("id", "")).lower()
            model_name_lower = str(model.get("name") or model.get("id") or "").lower()
            if "minimax" in provider_id_lower or model_name_lower.startswith("minimax-"):
                if "reasoning_output" not in model["capabilities"]:
                    model["capabilities"].append("reasoning_output")
                if "minimax_understand_image" not in model["capabilities"]:
                    model["capabilities"].append("minimax_understand_image")
            if "minimax_understand_image" in model["capabilities"] and "vision_input" not in model["capabilities"]:
                model["capabilities"].append("vision_input")
            models.append(model)
        if not models:
            continue
        provider["profiles"] = profiles
        provider["models"] = models
        providers.append(provider)
    config["schema_version"] = "1.1-text"
    config["providers"] = providers or copy.deepcopy(DEFAULT_CONFIG["providers"])
    if config.get("default_provider_id") not in {p.get("id") for p in config["providers"]}:
        config["default_provider_id"] = config["providers"][0].get("id", "")
    return config


def list_providers(task_type=None):
    providers = []
    for provider in load_config().get("providers", []):
        if not provider.get("enabled", True):
            continue
        if task_type and not provider_supports_task(provider, task_type):
            continue
        providers.append(provider)
    return providers


def get_provider(provider_id):
    for provider in load_config().get("providers", []):
        if provider.get("id") == provider_id:
            return provider
    return None


def provider_ids(task_type=None):
    ids = [p.get("id", "") for p in list_providers(task_type)]
    return [i for i in ids if i] or [""]


def provider_supports_task(provider, task_type):
    for profile in provider.get("profiles", []):
        if task_type in profile.get("task_types", []):
            return True
    return False


def profile_ids(provider_id, task_type=None):
    provider = get_provider(provider_id)
    if not provider:
        return [""]
    out = []
    for profile in provider.get("profiles", []):
        if task_type and task_type not in profile.get("task_types", []):
            continue
        pid = profile.get("id", "")
        if pid:
            out.append(pid)
    return out or [""]


def model_names(provider_id=None, task_type=None, profile_id=None):
    providers = [get_provider(provider_id)] if provider_id else list_providers(task_type)
    out = []
    for provider in providers:
        if not provider:
            continue
        for model in provider.get("models", []):
            if task_type and task_type not in model.get("task_types", []):
                continue
            if profile_id and model.get("profile_id") != profile_id:
                continue
            name = model.get("name") or model.get("id")
            if name and name not in out:
                out.append(name)
    return out or [""]


def get_model(provider_id, model_name):
    provider = get_provider(provider_id)
    if not provider:
        return None
    for model in provider.get("models", []):
        name = model.get("name") or model.get("id")
        if name == model_name or model.get("id") == model_name:
            return model
    return None


def base_urls(provider_id):
    provider = get_provider(provider_id)
    urls = provider.get("base_urls", []) if provider else []
    return [u for u in urls if isinstance(u, str) and u.strip()] or [""]


def get_profile(provider, profile_id, task_type=None):
    for profile in provider.get("profiles", []):
        if profile_id and profile.get("id") != profile_id:
            continue
        if task_type and task_type not in profile.get("task_types", []):
            continue
        return profile
    return None


def build_runtime_config(task_type, provider_id, profile_id, base_url, model, node_id, timeout=120):
    provider = get_provider(provider_id)
    if not provider:
        raise ValueError(f"provider not found: {provider_id}")
    profile = get_profile(provider, profile_id, task_type)
    if not profile:
        raise ValueError(f"profile not found: {profile_id}")

    paths = {}
    if profile.get("path"):
        paths["chat"] = profile["path"]
    if profile.get("generate_path"):
        paths["generate"] = profile["generate_path"]
    if profile.get("edit_path"):
        paths["edit"] = profile["edit_path"]

    return {
        "schema_version": "1.0",
        "task_type": task_type,
        "provider_id": provider.get("id", ""),
        "provider_name": provider.get("name", ""),
        "profile_id": profile.get("id", ""),
        "protocol": profile.get("protocol", ""),
        "base_url": (base_url or "").strip().rstrip("/"),
        "model": model,
        "api_key_ref": {"scope": "node", "node_id": str(node_id or "")},
        "auth": provider.get("auth", {}),
        "paths": paths,
        "timeout": int(timeout or 120),
    }


def build_text_runtime_config(provider_id, model, timeout=120):
    provider = get_provider(provider_id)
    if not provider:
        raise ValueError(f"provider not found: {provider_id}")
    model_info = get_model(provider_id, model)
    if not model_info:
        raise ValueError(f"model not found: {model}")
    profile_id = model_info.get("profile_id") or TEXT_PROFILE_ID
    profile = get_profile(provider, profile_id, "text")
    if not profile:
        raise ValueError(f"profile not found: {profile_id}")
    base_url = base_urls(provider_id)[0]
    paths = {}
    if profile.get("path"):
        paths["chat"] = profile["path"]
    return {
        "schema_version": "1.1-text",
        "task_type": "text",
        "provider_id": provider.get("id", ""),
        "provider_name": provider.get("name", ""),
        "profile_id": profile.get("id", ""),
        "protocol": profile.get("protocol", ""),
        "base_url": (base_url or "").strip().rstrip("/"),
        "model": model,
        "model_id": model_info.get("id", ""),
        "model_name": model_info.get("name", "") or model_info.get("id", ""),
        "capabilities": list(model_info.get("capabilities", [])),
        "api_key_ref": {"scope": "provider", "provider_id": provider.get("id", "")},
        "auth": provider.get("auth", {}),
        "paths": paths,
        "timeout": int(timeout or 120),
    }


def upsert_provider(provider):
    if not isinstance(provider, dict) or not provider.get("id"):
        raise ValueError("provider.id is required")
    config = load_config()
    providers = config.setdefault("providers", [])
    for idx, current in enumerate(providers):
        if current.get("id") == provider["id"]:
            providers[idx] = provider
            save_config(config)
            return provider
    providers.append(provider)
    save_config(config)
    return provider


def delete_provider(provider_id):
    config = load_config()
    providers = config.get("providers", [])
    config["providers"] = [p for p in providers if p.get("id") != provider_id]
    save_config(config)


def add_base_url(provider_id, base_url):
    url = (base_url or "").strip().rstrip("/")
    if not url:
        raise ValueError("base_url is required")
    config = load_config()
    for provider in config.get("providers", []):
        if provider.get("id") == provider_id:
            urls = provider.setdefault("base_urls", [])
            if url not in urls:
                urls.append(url)
            save_config(config)
            return urls
    raise ValueError(f"provider not found: {provider_id}")


def delete_base_url(provider_id, base_url):
    url = (base_url or "").strip().rstrip("/")
    config = load_config()
    for provider in config.get("providers", []):
        if provider.get("id") == provider_id:
            provider["base_urls"] = [u for u in provider.get("base_urls", []) if u != url]
            if not provider["base_urls"]:
                provider["base_urls"] = [""]
            save_config(config)
            return provider["base_urls"]
    raise ValueError(f"provider not found: {provider_id}")


def make_text_provider(provider_id, name, base_url, model_name, api_path="/chat/completions"):
    provider_id = (provider_id or "").strip()
    model_name = (model_name or "").strip()
    if not provider_id:
        raise ValueError("provider_id is required")
    if not model_name:
        raise ValueError("model_name is required")
    return {
        "id": provider_id,
        "name": (name or provider_id).strip(),
        "enabled": True,
        "base_urls": [(base_url or "").strip().rstrip("/")],
        "auth": {
            "type": "bearer",
            "header": "Authorization",
            "prefix": "Bearer ",
        },
        "profiles": [default_text_profile(api_path)],
        "models": [
            {
                "id": model_name,
                "name": model_name,
                "task_types": ["text"],
                "profile_id": TEXT_PROFILE_ID,
                "capabilities": ["text"],
            }
        ],
    }


def upsert_model(provider_id, model):
    if not isinstance(model, dict) or not model.get("id"):
        raise ValueError("model.id is required")
    config = load_config()
    for provider in config.get("providers", []):
        if provider.get("id") != provider_id:
            continue
        models = provider.setdefault("models", [])
        for idx, current in enumerate(models):
            if current.get("id") == model["id"]:
                models[idx] = model
                save_config(config)
                return model
        models.append(model)
        save_config(config)
        return model
    raise ValueError(f"provider not found: {provider_id}")


def delete_model(provider_id, model_id):
    config = load_config()
    for provider in config.get("providers", []):
        if provider.get("id") == provider_id:
            provider["models"] = [m for m in provider.get("models", []) if m.get("id") != model_id]
            save_config(config)
            return
    raise ValueError(f"provider not found: {provider_id}")
