import json


def dumps(data):
    return json.dumps(data, ensure_ascii=False)


def mask_secret(text, secret):
    if not secret:
        return text
    return str(text).replace(secret, "***")


def error_payload(code, message, config=None, raw=None):
    config = config or {}
    return {
        "ok": False,
        "code": code,
        "message": message,
        "provider_id": config.get("provider_id", ""),
        "model": config.get("model", ""),
        "model_label": config.get("model_label", config.get("requested_model", config.get("model", ""))),
        "raw": raw or {},
    }
