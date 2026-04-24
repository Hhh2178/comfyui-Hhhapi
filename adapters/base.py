import requests


class BaseAdapter:
    protocol = ""

    def build_headers(self, config, api_key, content_type="application/json"):
        auth = config.get("auth", {})
        headers = {}
        if auth.get("type") == "bearer" and api_key:
            headers[auth.get("header", "Authorization")] = f"{auth.get('prefix', 'Bearer ')}{api_key}"
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def post_json(self, url, headers, payload, timeout):
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        return resp.json()

