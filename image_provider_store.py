import copy
import json
import os


BASE_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "hhhapi_image_config.json")
IMAGE_PROVIDER_ID = "bltcy_image"

DEFAULT_GPT_MODELS = [
    "gpt-image-2",
    "gpt-image-1.5",
    "gpt-image-1",
]

DEFAULT_NANO_MODELS = [
    "nano-banana",
    "nano-banana-hd",
    "nano-banana-pro",
    "nano-banana-pro-2k",
    "nano-banana-pro-4k",
    "nano-banana-2",
    "nano-banana-2-2k",
    "nano-banana-2-4k",
]


def _clean_text(value):
    return str(value or "").strip()


def _normalize_base_url(base_url):
    base_url = _clean_text(base_url).rstrip("/")
    if not base_url:
        return "https://api.bltcy.ai/v1"
    if base_url.endswith("/v1"):
        return base_url
    return f"{base_url}/v1"


def _normalize_model_entry(entry):
    if isinstance(entry, str):
        name = _clean_text(entry)
        if not name:
            return None
        return {"id": name, "name": name, "label": name}
    if not isinstance(entry, dict):
        return None
    name = _clean_text(entry.get("name") or entry.get("id") or entry.get("model"))
    if not name:
        return None
    return {
        "id": _clean_text(entry.get("id") or name),
        "name": name,
        "label": _clean_text(entry.get("label") or entry.get("display_name") or entry.get("alias") or name) or name,
    }


def _default_model_entries(models):
    out = []
    for model in models:
        entry = _normalize_model_entry(model)
        if entry:
            out.append(entry)
    return out


def _display_name(entry):
    return _clean_text((entry or {}).get("label") or (entry or {}).get("name") or (entry or {}).get("id"))


def _default_provider():
    return {
        "id": IMAGE_PROVIDER_ID,
        "name": "柏拉图AI图片",
        "enabled": True,
        "base_url": "https://api.bltcy.ai/v1",
        "timeout": 120,
        "families": {
            "gpt": {
                "label": "GPT 图片",
                "models": _default_model_entries(DEFAULT_GPT_MODELS),
            },
            "nano": {
                "label": "Nano 图片",
                "models": _default_model_entries(DEFAULT_NANO_MODELS),
            },
        },
    }


DEFAULT_CONFIG = {
    "schema_version": "2.0-image",
    "default_provider_id": IMAGE_PROVIDER_ID,
    "providers": [_default_provider()],
}


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_config():
    if not os.path.exists(CONFIG_FILE):
        _write_json(CONFIG_FILE, DEFAULT_CONFIG)


def _normalize_provider(provider):
    if not isinstance(provider, dict):
        provider = {}
    default = _default_provider()
    normalized = {
        "id": _clean_text(provider.get("id") or default["id"]),
        "name": _clean_text(provider.get("name") or default["name"]) or default["name"],
        "enabled": bool(provider.get("enabled", True)),
        "base_url": _normalize_base_url(provider.get("base_url", default["base_url"])),
        "timeout": int(provider.get("timeout") or default["timeout"]),
        "families": {},
    }
    families = provider.get("families", {})
    if not isinstance(families, dict):
        families = {}
    for family, default_models in (("gpt", DEFAULT_GPT_MODELS), ("nano", DEFAULT_NANO_MODELS)):
        current = families.get(family, {})
        if not isinstance(current, dict):
            current = {}
        models = current.get("models", [])
        if not isinstance(models, list):
            models = []
        normalized_models = []
        for model in models:
            entry = _normalize_model_entry(model)
            if entry:
                normalized_models.append(entry)
        normalized["families"][family] = {
            "label": _clean_text(current.get("label") or ("GPT 图片" if family == "gpt" else "Nano 图片")) or ("GPT 图片" if family == "gpt" else "Nano 图片"),
            "models": normalized_models or _default_model_entries(default_models),
        }
    return normalized


def migrate_config(config):
    if not isinstance(config, dict):
        config = copy.deepcopy(DEFAULT_CONFIG)
    if "platform" in config and "providers" not in config:
        platform = config.get("platform", {})
        config = {
            "schema_version": "2.0-image",
            "default_provider_id": _clean_text(platform.get("id") or IMAGE_PROVIDER_ID) or IMAGE_PROVIDER_ID,
            "providers": [
                {
                    "id": _clean_text(platform.get("id") or IMAGE_PROVIDER_ID) or IMAGE_PROVIDER_ID,
                    "name": _clean_text(platform.get("name") or "柏拉图AI图片") or "柏拉图AI图片",
                    "enabled": True,
                    "base_url": platform.get("base_url", "https://api.bltcy.ai/v1"),
                    "timeout": platform.get("timeout", 120),
                    "families": platform.get("families", {}),
                }
            ],
        }
    providers = []
    for provider in config.get("providers", []):
        normalized = _normalize_provider(provider)
        if normalized.get("id"):
            providers.append(normalized)
    if not providers:
        providers = [_default_provider()]
    config["schema_version"] = "2.0-image"
    config["providers"] = providers
    default_provider_id = _clean_text(config.get("default_provider_id"))
    valid_ids = {provider.get("id") for provider in providers}
    config["default_provider_id"] = default_provider_id if default_provider_id in valid_ids else providers[0].get("id", IMAGE_PROVIDER_ID)
    return config


def load_config():
    ensure_config()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return migrate_config(data)
    except Exception:
        data = copy.deepcopy(DEFAULT_CONFIG)
        _write_json(CONFIG_FILE, data)
        return data


def save_config(config):
    _write_json(CONFIG_FILE, migrate_config(config))


def provider_ids():
    providers = [provider.get("id", "") for provider in load_config().get("providers", []) if provider.get("enabled", True)]
    return [provider_id for provider_id in providers if provider_id] or [IMAGE_PROVIDER_ID]


def get_provider(provider_id=None):
    config = load_config()
    target_id = _clean_text(provider_id or config.get("default_provider_id"))
    for provider in config.get("providers", []):
        if provider.get("id") == target_id:
            return provider
    return config.get("providers", [{}])[0]


def get_platform():
    return get_provider()


def model_names(family, provider_id=None):
    provider = get_provider(provider_id)
    families = provider.get("families", {})
    models = families.get(family, {}).get("models", [])
    names = [_display_name(model) for model in models if _display_name(model)]
    if names:
        return names
    defaults = DEFAULT_GPT_MODELS if family == "gpt" else DEFAULT_NANO_MODELS
    return [_display_name(model) for model in _default_model_entries(defaults)]


def get_model_entry(family, selected_model, provider_id=None):
    provider = get_provider(provider_id)
    families = provider.get("families", {})
    models = families.get(family, {}).get("models", [])
    normalized_models = []
    for model in models:
        entry = _normalize_model_entry(model)
        if entry:
            normalized_models.append(entry)
    if not normalized_models:
        defaults = DEFAULT_GPT_MODELS if family == "gpt" else DEFAULT_NANO_MODELS
        normalized_models = _default_model_entries(defaults)
    selected = _clean_text(selected_model)
    for entry in normalized_models:
        if selected in {_display_name(entry), _clean_text(entry.get("name")), _clean_text(entry.get("id"))}:
            return entry
    return normalized_models[0] if normalized_models else None


def update_provider(provider_id, base_url, timeout, gpt_models, nano_models, name=None):
    config = load_config()
    providers = config.setdefault("providers", [])
    provider_id = _clean_text(provider_id or config.get("default_provider_id") or IMAGE_PROVIDER_ID) or IMAGE_PROVIDER_ID
    target = None
    for provider in providers:
        if provider.get("id") == provider_id:
            target = provider
            break
    if target is None:
        target = {"id": provider_id}
        providers.append(target)
    target["id"] = provider_id
    target["name"] = _clean_text(name or target.get("name") or provider_id) or provider_id
    target["enabled"] = True
    target["base_url"] = _normalize_base_url(base_url)
    target["timeout"] = int(timeout or 120)
    target["families"] = {
        "gpt": {
            "label": "GPT 图片",
            "models": [entry for entry in (_normalize_model_entry(model) for model in gpt_models) if entry],
        },
        "nano": {
            "label": "Nano 图片",
            "models": [entry for entry in (_normalize_model_entry(model) for model in nano_models) if entry],
        },
    }
    save_config(config)
    return get_provider(provider_id)


def build_runtime_config(family, model, timeout=None, provider_id=None):
    provider = get_provider(provider_id)
    selected_timeout = int(timeout if timeout is not None else provider.get("timeout", 120))
    model_entry = get_model_entry(family, model, provider.get("id")) or {"name": _clean_text(model), "label": _clean_text(model)}
    actual_model = _clean_text(model_entry.get("name") or model_entry.get("id"))
    model_label = _display_name(model_entry) or actual_model
    return {
        "schema_version": "2.0-image",
        "task_type": "image",
        "provider_id": provider.get("id", IMAGE_PROVIDER_ID),
        "provider_name": provider.get("name", "柏拉图AI图片"),
        "family": family,
        "base_url": _normalize_base_url(provider.get("base_url", "https://api.bltcy.ai/v1")),
        "model": actual_model,
        "model_label": model_label,
        "requested_model": model,
        "auth": {
            "type": "bearer",
            "header": "Authorization",
            "prefix": "Bearer ",
        },
        "paths": {
            "generate": "/images/generations",
            "edit": "/images/edits",
        },
        "timeout": selected_timeout,
    }
