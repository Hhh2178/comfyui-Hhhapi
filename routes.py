import json
import traceback

from aiohttp import web

from . import provider_store
from . import image_provider_store
from .adapters import get_adapter
from .secret_store import provider_has_api_key, resolve_api_key, save_node_api_key, save_provider_api_key


def register_routes():
    try:
        from server import PromptServer
    except Exception:
        print("[Hhhapi] Cannot import PromptServer, skipping routes")
        return

    if not getattr(PromptServer, "instance", None):
        print("[Hhhapi] PromptServer not ready, skipping routes")
        return

    routes = PromptServer.instance.routes

    def ok(data, status=200):
        return web.Response(
            text=json.dumps(data, ensure_ascii=False),
            status=status,
            content_type="application/json",
        )

    def error_response(exc):
        traceback.print_exc()
        return ok({"ok": False, "message": str(exc)}, status=500)

    def providers_payload():
        return provider_store.list_providers("text")

    def provider_detail_payload(provider_id):
        provider = provider_store.get_provider(provider_id)
        if not provider:
            return {"ok": False, "message": "provider not found"}, 404
        return {
            "ok": True,
            "provider": provider,
            "has_api_key": provider_has_api_key(provider_id),
        }, 200

    def models_payload(request):
        provider_id = request.rel_url.query.get("provider_id", "")
        profile_id = request.rel_url.query.get("profile_id", "")
        return provider_store.model_names(provider_id or None, "text", profile_id or None)

    def image_config_payload():
        return {
            "ok": True,
            "config": image_provider_store.load_config(),
            "has_api_key": provider_has_api_key(image_provider_store.IMAGE_PROVIDER_ID),
        }

    @routes.get("/hhhapi/providers")
    async def providers(request):
        try:
            return ok(providers_payload())
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/providers/{provider_id}")
    async def provider_detail(request):
        try:
            payload, status = provider_detail_payload(request.match_info["provider_id"])
            return ok(payload, status=status)
        except Exception as exc:
            return error_response(exc)

    @routes.post("/hhhapi/providers")
    async def upsert_provider(request):
        data = await request.json()
        provider = provider_store.upsert_provider(data)
        return web.json_response({"ok": True, "provider": provider})

    @routes.post("/hhhapi/providers/quick_add_text")
    async def quick_add_text_provider(request):
        data = await request.json()
        provider = provider_store.make_text_provider(
            provider_id=data.get("id", ""),
            name=data.get("name", ""),
            base_url=data.get("base_url", ""),
            model_name=data.get("model", ""),
            api_path=data.get("api_path", "/chat/completions"),
        )
        saved = provider_store.upsert_provider(provider)
        api_key = data.get("api_key", "")
        if api_key:
            save_provider_api_key(saved.get("id", ""), api_key)
        return web.json_response({"ok": True, "provider": saved, "api_key_saved": bool(api_key)})

    @routes.delete("/hhhapi/providers/{provider_id}")
    async def delete_provider(request):
        provider_store.delete_provider(request.match_info["provider_id"])
        return web.json_response({"ok": True})

    @routes.get("/hhhapi/profiles")
    async def profiles(request):
        provider_id = request.rel_url.query.get("provider_id", "")
        return web.json_response(provider_store.profile_ids(provider_id, "text"))

    @routes.get("/hhhapi/base_urls")
    async def base_urls(request):
        provider_id = request.rel_url.query.get("provider_id", "")
        return web.json_response(provider_store.base_urls(provider_id))

    @routes.get("/hhhapi/models")
    async def models(request):
        try:
            return ok(models_payload(request))
        except Exception as exc:
            return error_response(exc)

    @routes.post("/hhhapi/models")
    async def upsert_model(request):
        data = await request.json()
        provider_id = data.get("provider_id", "")
        model = data.get("model", {})
        return web.json_response({"ok": True, "model": provider_store.upsert_model(provider_id, model)})

    @routes.post("/hhhapi/base_urls")
    async def add_base_url(request):
        data = await request.json()
        return web.json_response({
            "ok": True,
            "base_urls": provider_store.add_base_url(data.get("provider_id", ""), data.get("base_url", "")),
        })

    @routes.delete("/hhhapi/base_urls/{provider_id}")
    async def delete_base_url(request):
        data = await request.json()
        return web.json_response({
            "ok": True,
            "base_urls": provider_store.delete_base_url(request.match_info["provider_id"], data.get("base_url", "")),
        })

    @routes.delete("/hhhapi/models/{provider_id}/{model_id}")
    async def delete_model(request):
        provider_store.delete_model(request.match_info["provider_id"], request.match_info["model_id"])
        return web.json_response({"ok": True})

    @routes.post("/hhhapi/secrets/node/{node_id}")
    async def node_secret(request):
        data = await request.json()
        save_node_api_key(request.match_info["node_id"], data.get("provider_id", ""), data.get("api_key", ""))
        return web.json_response({"ok": True})

    @routes.post("/hhhapi/secrets/provider/{provider_id}")
    async def provider_secret(request):
        data = await request.json()
        save_provider_api_key(request.match_info["provider_id"], data.get("api_key", ""))
        return web.json_response({"ok": True})

    @routes.get("/hhhapi/export")
    async def export_config(request):
        return web.json_response(provider_store.load_config())

    @routes.get("/hhhapi/v1/providers")
    async def v1_providers(request):
        try:
            return ok(providers_payload())
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/v1/providers/{provider_id}")
    async def v1_provider_detail(request):
        try:
            payload, status = provider_detail_payload(request.match_info["provider_id"])
            return ok(payload, status=status)
        except Exception as exc:
            return error_response(exc)

    @routes.post("/hhhapi/v1/providers")
    async def v1_upsert_provider(request):
        try:
            data = await request.json()
            provider = provider_store.upsert_provider(data)
            return ok({"ok": True, "provider": provider})
        except Exception as exc:
            return error_response(exc)

    @routes.delete("/hhhapi/v1/providers/{provider_id}")
    async def v1_delete_provider(request):
        try:
            provider_store.delete_provider(request.match_info["provider_id"])
            return ok({"ok": True})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/v1/models")
    async def v1_models(request):
        try:
            return ok(models_payload(request))
        except Exception as exc:
            return error_response(exc)

    @routes.post("/hhhapi/v1/secrets/provider/{provider_id}")
    async def v1_provider_secret(request):
        try:
            data = await request.json()
            save_provider_api_key(request.match_info["provider_id"], data.get("api_key", ""))
            return ok({"ok": True})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/v1/provider")
    async def v1_provider_detail_query(request):
        try:
            provider_id = request.rel_url.query.get("provider_id", "")
            payload, status = provider_detail_payload(provider_id)
            return ok(payload, status=status)
        except Exception as exc:
            return error_response(exc)

    @routes.post("/hhhapi/v1/delete_provider")
    async def v1_delete_provider_body(request):
        try:
            data = await request.json()
            provider_store.delete_provider(data.get("provider_id", ""))
            return ok({"ok": True})
        except Exception as exc:
            return error_response(exc)

    @routes.post("/hhhapi/v1/provider_secret")
    async def v1_provider_secret_body(request):
        try:
            data = await request.json()
            save_provider_api_key(data.get("provider_id", ""), data.get("api_key", ""))
            return ok({"ok": True})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/v1/save_provider")
    async def v1_save_provider_query(request):
        try:
            raw = request.rel_url.query.get("data", "")
            data = json.loads(raw) if raw else {}
            provider = provider_store.upsert_provider(data)
            return ok({"ok": True, "provider": provider})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/v1/delete_provider_get")
    async def v1_delete_provider_query(request):
        try:
            provider_store.delete_provider(request.rel_url.query.get("provider_id", ""))
            return ok({"ok": True})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/v1/provider_secret_get")
    async def v1_provider_secret_query(request):
        try:
            provider_id = request.rel_url.query.get("provider_id", "")
            api_key = request.rel_url.query.get("api_key", "")
            save_provider_api_key(provider_id, api_key)
            return ok({"ok": True})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/v1/test_provider")
    async def v1_test_provider(request):
        try:
            provider_id = request.rel_url.query.get("provider_id", "")
            model = request.rel_url.query.get("model", "")
            prompt = request.rel_url.query.get("prompt", "你好")
            runtime = provider_store.build_text_runtime_config(provider_id, model, timeout=30)
            api_key = resolve_api_key(runtime)
            if not api_key:
                return ok({"ok": False, "message": "API密钥未保存"}, status=400)
            adapter = get_adapter(runtime.get("protocol", ""))
            result = adapter.call_text(
                runtime,
                api_key,
                "You are a concise API connectivity tester.",
                prompt,
                0.2,
                128,
                -1,
                "text",
            )
            return ok({"ok": True, "text": result.get("text", ""), "usage": result.get("usage", {})})
        except Exception as exc:
            return error_response(exc)

    # Dedicated management-panel routes. These avoid stale hot-reload collisions
    # observed on the older /v1/providers endpoints in some ComfyUI builds.
    @routes.get("/hhhapi/panel/providers_list")
    async def panel_providers_list(request):
        try:
            return ok(providers_payload())
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/panel/provider_detail")
    async def panel_provider_detail(request):
        try:
            provider_id = request.rel_url.query.get("provider_id", "")
            payload, status = provider_detail_payload(provider_id)
            return ok(payload, status=status)
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/panel/save_provider")
    async def panel_save_provider(request):
        try:
            raw = request.rel_url.query.get("data", "")
            data = json.loads(raw) if raw else {}
            provider = provider_store.upsert_provider(data)
            return ok({"ok": True, "provider": provider})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/panel/delete_provider")
    async def panel_delete_provider(request):
        try:
            provider_store.delete_provider(request.rel_url.query.get("provider_id", ""))
            return ok({"ok": True})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/panel/provider_secret")
    async def panel_provider_secret(request):
        try:
            provider_id = request.rel_url.query.get("provider_id", "")
            api_key = request.rel_url.query.get("api_key", "")
            save_provider_api_key(provider_id, api_key)
            return ok({"ok": True})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/panel/test_provider")
    async def panel_test_provider(request):
        try:
            provider_id = request.rel_url.query.get("provider_id", "")
            model = request.rel_url.query.get("model", "")
            prompt = request.rel_url.query.get("prompt", "你好")
            runtime = provider_store.build_text_runtime_config(provider_id, model, timeout=30)
            api_key = resolve_api_key(runtime)
            if not api_key:
                return ok({"ok": False, "message": "API密钥未保存"}, status=400)
            adapter = get_adapter(runtime.get("protocol", ""))
            result = adapter.call_text(
                runtime,
                api_key,
                "You are a concise API connectivity tester.",
                prompt,
                0.2,
                128,
                -1,
                "text",
            )
            return ok({"ok": True, "text": result.get("text", ""), "usage": result.get("usage", {})})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/image/panel/config")
    async def image_panel_config(request):
        try:
            return ok(image_config_payload())
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/image/panel/models")
    async def image_panel_models(request):
        try:
            family = request.rel_url.query.get("family", "gpt")
            return ok({"ok": True, "models": image_provider_store.model_names(family)})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/image/panel/save_config")
    async def image_panel_save_config(request):
        try:
            raw = request.rel_url.query.get("data", "")
            data = json.loads(raw) if raw else {}
            platform = data.get("platform", {})
            saved = image_provider_store.update_platform(
                base_url=platform.get("base_url", ""),
                timeout=platform.get("timeout", 120),
                gpt_models=platform.get("families", {}).get("gpt", {}).get("models", []),
                nano_models=platform.get("families", {}).get("nano", {}).get("models", []),
            )
            return ok({"ok": True, "platform": saved})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/image/panel/provider_secret")
    async def image_panel_provider_secret(request):
        try:
            api_key = request.rel_url.query.get("api_key", "")
            save_provider_api_key(image_provider_store.IMAGE_PROVIDER_ID, api_key)
            return ok({"ok": True})
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/image/v1/config")
    async def image_v1_config(request):
        try:
            return ok(image_config_payload())
        except Exception as exc:
            return error_response(exc)

    @routes.get("/hhhapi/image/v1/models")
    async def image_v1_models(request):
        try:
            family = request.rel_url.query.get("family", "gpt")
            return ok(image_provider_store.model_names(family))
        except Exception as exc:
            return error_response(exc)
