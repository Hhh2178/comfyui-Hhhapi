try:
    from comfy_execution.graph_utils import ExecutionBlocker
except Exception:
    class ExecutionBlocker:
        def __init__(self, value):
            self.value = value

from . import image_provider_store
from .adapters.bltcy_images import BltcyImagesAdapter
from .secret_store import resolve_api_key
from .utils.image import pil_list_to_batch
from .utils.response import dumps, error_payload


GPT_ASPECT_RATIOS = ["auto", "1:1", "4:3", "3:2", "16:9", "21:9", "2:3", "3:4", "9:16", "9:21"]
GPT_QUALITIES = ["low", "medium", "high", "auto"]
GPT_FORMATS = ["png", "jpeg", "webp"]
GPT_INPUT_FIDELITY = ["low", "high"]
GPT_SIZE_BY_RATIO = {
    "1:1": "1024x1024",
    "4:3": "1024x768",
    "3:2": "1024x682",
    "16:9": "1280x720",
    "21:9": "1680x720",
    "2:3": "768x1152",
    "3:4": "768x1024",
    "9:16": "768x1365",
    "9:21": "720x1680",
}


class HhhapiBltcyGPTImage:
    @classmethod
    def INPUT_TYPES(cls):
        models = image_provider_store.model_names("gpt")
        return {
            "required": {
                "模型": (models, {"default": models[0]}),
                "提示词": ("STRING", {"default": "", "multiline": True}),
                "质量": (GPT_QUALITIES, {"default": "medium"}),
                "画幅比例": (GPT_ASPECT_RATIOS, {"default": "auto"}),
                "生成数量": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1}),
                "随机种子": ("INT", {"default": -1, "min": -1, "max": 2147483647, "step": 1}),
                "超时秒数": ("INT", {"default": 120, "min": 1, "max": 3600, "step": 1}),
            },
            "optional": {
                "输出格式": (GPT_FORMATS, {"default": "png"}),
                "保真度": (GPT_INPUT_FIDELITY, {"default": "high"}),
                "参考图1": ("IMAGE",),
                "参考图2": ("IMAGE",),
                "参考图3": ("IMAGE",),
                "参考图4": ("IMAGE",),
                "参考图5": ("IMAGE",),
                "遮罩": ("MASK",),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "response_json", "image_url")
    FUNCTION = "run"
    CATEGORY = "Hhh/柏拉图图片API"

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def run(
        self,
        模型="",
        提示词="",
        质量="medium",
        画幅比例="auto",
        生成数量=1,
        随机种子=-1,
        超时秒数=120,
        输出格式="png",
        保真度="high",
        参考图1=None,
        参考图2=None,
        参考图3=None,
        参考图4=None,
        参考图5=None,
        遮罩=None,
    ):
        config = {}
        try:
            if not (提示词 or "").strip():
                raise ValueError("提示词不能为空")
            config = image_provider_store.build_runtime_config("gpt", 模型, 超时秒数)
            api_key = resolve_api_key(config)
            if not api_key:
                raise ValueError("API key not found. Set it in Hhh 柏拉图图片API管理.")
            images = [image for image in [参考图1, 参考图2, 参考图3, 参考图4, 参考图5] if image is not None]
            resolved_size = GPT_SIZE_BY_RATIO.get(画幅比例, "1024x1024") if 画幅比例 != "auto" else "1024x1024"
            adapter = BltcyImagesAdapter()
            result = adapter.call_gpt_image(
                config=config,
                api_key=api_key,
                prompt=提示词,
                size=resolved_size,
                aspect_ratio=画幅比例,
                n=生成数量,
                quality=质量,
                seed=随机种子,
                output_format=输出格式,
                input_fidelity=保真度,
                images=images,
                mask=遮罩,
            )
            pil_images = result.pop("images", [])
            if not pil_images:
                raise ValueError("No images were returned from the API")
            tensor = pil_list_to_batch(pil_images)
            url = (result.get("image_urls") or [""])[0]
            meta = {
                "ok": True,
                "family": "gpt",
                "mode": "image_to_image" if images else "text_to_image",
                "model": 模型,
                "resolved_size": resolved_size,
                "aspect_ratio": 画幅比例,
                "requested_n": int(生成数量),
                "returned_n": int(tensor.shape[0]) if hasattr(tensor, "shape") else 0,
                "response": result,
            }
            return (tensor, dumps(meta), url)
        except Exception as exc:
            error = error_payload("bltcy_gpt_image_error", str(exc), config)
            return (ExecutionBlocker(None), dumps(error), "")
