import json
import os


BASE_DIR = os.path.dirname(os.path.realpath(__file__))
SECRETS_FILE = os.path.join(BASE_DIR, "hhhapi_secrets.json")


def _default():
    return {"schema_version": "1.0", "provider_secrets": {}, "node_secrets": {}}


def _write(data):
    with open(SECRETS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_secrets():
    if not os.path.exists(SECRETS_FILE):
        data = _default()
        _write(data)
        return data
    try:
        with open(SECRETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("secrets root must be object")
        data.setdefault("provider_secrets", {})
        data.setdefault("node_secrets", {})
        return data
    except Exception:
        data = _default()
        _write(data)
        return data


def save_node_api_key(node_id, provider_id, api_key):
    node_id = str(node_id or "").strip()
    if not node_id:
        return
    data = load_secrets()
    current = data.setdefault("node_secrets", {}).setdefault(node_id, {})
    current["provider_id"] = provider_id
    if api_key:
        current["api_key"] = api_key
    _write(data)


def save_provider_api_key(provider_id, api_key):
    if not provider_id:
        return
    data = load_secrets()
    current = data.setdefault("provider_secrets", {}).setdefault(provider_id, {})
    current["api_key"] = api_key or ""
    _write(data)


def provider_has_api_key(provider_id):
    data = load_secrets()
    api_key = data.get("provider_secrets", {}).get(provider_id, {}).get("api_key", "")
    return bool(api_key)


def resolve_api_key(config):
    data = load_secrets()
    provider_id = config.get("provider_id", "")
    ref = config.get("api_key_ref", {})
    node_id = str(ref.get("node_id", "")).strip()
    if node_id:
        node_secret = data.get("node_secrets", {}).get(node_id, {})
        api_key = node_secret.get("api_key", "")
        if api_key:
            return api_key
    provider_secret = data.get("provider_secrets", {}).get(provider_id, {})
    return provider_secret.get("api_key", "")
