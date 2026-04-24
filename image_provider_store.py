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

DEFAULT_CONFIG = {
    "schema_version": "1.0-image",
    "platform": {
        "id": IMAGE_PROVIDER_ID,
        "name": "柏拉图AI图片",
        "base_url": "https://api.bltcy.ai/v1",
        "timeout": 120,
        "families": {
            "gpt": {
                "label": "GPT 图片",
                "models": DEFAULT_GPT_MODELS,
            },
            "nano": {
                "label": "Nano 图片",
                "models": DEFAULT_NANO_MODELS,
            },
        },
    },
}


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_config():
    if not os.path.exists(CONFIG_FILE):
        _write_json(CONFIG_FILE, DEFAULT_CONFIG)


def _normalize_base_url(base_url):
    base_url = (base_url or "").strip().rstrip("/")
    if not base_url:
        return "https://api.bltcy.ai/v1"
    if base_url.endswith("/v1"):
        return base_url
    return f"{base_url}/v1"


def migrate_config(config):
    if not isinstance(config, dict):
        config = copy.deepcopy(DEFAULT_CONFIG)
    platform = config.setdefault("platform", {})
    platform["id"] = IMAGE_PROVIDER_ID
    platform["name"] = platform.get("name") or "柏拉图AI图片"
    platform["base_url"] = _normalize_base_url(platform.get("base_url", "https://api.bltcy.ai/v1"))
    platform["timeout"] = int(platform.get("timeout") or 120)
    families = platform.setdefault("families", {})
    for family, default_models in (("gpt", DEFAULT_GPT_MODELS), ("nano", DEFAULT_NANO_MODELS)):
        current = families.setdefault(family, {})
        current["label"] = current.get("label") or ("GPT 图片" if family == "gpt" else "Nano 图片")
        models = current.get("models", [])
        if not isinstance(models, list):
            models = []
        current["models"] = [str(model).strip() for model in models if str(model).strip()] or list(default_models)
    config["schema_version"] = "1.0-image"
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


def get_platform():
    return load_config().get("platform", {})


def model_names(family):
    platform = get_platform()
    families = platform.get("families", {})
    models = families.get(family, {}).get("models", [])
    return [model for model in models if model] or list(DEFAULT_GPT_MODELS if family == "gpt" else DEFAULT_NANO_MODELS)


def update_platform(base_url, timeout, gpt_models, nano_models):
    config = load_config()
    platform = config.setdefault("platform", {})
    platform["base_url"] = _normalize_base_url(base_url)
    platform["timeout"] = int(timeout or 120)
    platform.setdefault("families", {})
    platform["families"]["gpt"] = {
        "label": "GPT 图片",
        "models": [model for model in gpt_models if model],
    }
    platform["families"]["nano"] = {
        "label": "Nano 图片",
        "models": [model for model in nano_models if model],
    }
    save_config(config)
    return get_platform()


def build_runtime_config(family, model, timeout=None):
    platform = get_platform()
    selected_timeout = int(timeout if timeout is not None else platform.get("timeout", 120))
    return {
        "schema_version": "1.0-image",
        "task_type": "image",
        "provider_id": IMAGE_PROVIDER_ID,
        "provider_name": platform.get("name", "柏拉图AI图片"),
        "family": family,
        "base_url": _normalize_base_url(platform.get("base_url", "https://api.bltcy.ai/v1")),
        "model": model,
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
