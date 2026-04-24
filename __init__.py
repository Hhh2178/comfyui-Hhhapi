from .nodes_provider import HhhapiProviderManager
from .nodes_text import HhhapiText
from .nodes_bltcy_image_manager import HhhapiBltcyImageManager
from .nodes_bltcy_gpt_image import HhhapiBltcyGPTImage
from .nodes_bltcy_nano_image import HhhapiBltcyNanoImage

try:
    from .routes import register_routes
    register_routes()
except Exception as exc:
    print(f"[Hhhapi] route registration skipped: {exc}")


NODE_CLASS_MAPPINGS = {
    "HhhapiText": HhhapiText,
    "HhhapiProviderManager": HhhapiProviderManager,
    "HhhapiBltcyImageManager": HhhapiBltcyImageManager,
    "HhhapiBltcyGPTImage": HhhapiBltcyGPTImage,
    "HhhapiBltcyNanoImage": HhhapiBltcyNanoImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HhhapiText": "Hhh 文本API",
    "HhhapiProviderManager": "Hhh 文本API服务商管理",
    "HhhapiBltcyImageManager": "Hhh 柏拉图图片API管理",
    "HhhapiBltcyGPTImage": "Hhh 柏拉图 GPT-Image",
    "HhhapiBltcyNanoImage": "Hhh 柏拉图 Nano",
}

WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
