from .nodes_provider import HhhapiProviderManager
from .nodes_text import HhhapiText

try:
    from .routes import register_routes
    register_routes()
except Exception as exc:
    print(f"[Hhhapi] route registration skipped: {exc}")


NODE_CLASS_MAPPINGS = {
    "HhhapiText": HhhapiText,
    "HhhapiProviderManager": HhhapiProviderManager,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HhhapiText": "Hhh 文本API",
    "HhhapiProviderManager": "Hhh 文本API服务商管理",
}

WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
