import json

import torch

try:
    from comfy_execution.graph_utils import ExecutionBlocker
except Exception:
    class ExecutionBlocker:
        def __init__(self, value):
            self.value = value

from .adapters import get_adapter
from .secret_store import resolve_api_key
from .utils.image import pil_list_to_batch
from .utils.response import dumps, error_payload


IMAGE_SIZES = ["auto", "1024x1024", "1536x1024", "1024x1536", "1792x1024", "1024x1792"]
ASPECT_RATIOS = ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "21:9"]
QUALITIES = ["auto", "low", "medium", "high"]
FORMATS = ["png", "jpeg", "webp"]


class HhhapiTextToImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("STRING", {"default": "", "forceInput": True}),
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "negative_prompt": ("STRING", {"default": "", "multiline": True}),
                "size": (IMAGE_SIZES, {"default": "1024x1024"}),
                "aspect_ratio": (ASPECT_RATIOS, {"default": "auto"}),
                "quality": (QUALITIES, {"default": "auto"}),
                "n": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 0xFFFFFFFFFFFFFFFF}),
                "output_format": (FORMATS, {"default": "png"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "response_json", "image_url")
    FUNCTION = "run"
    CATEGORY = "Hhhapi"

    def run(self, config, prompt, negative_prompt, size, aspect_ratio, quality, n, seed, output_format):
        parsed = {}
        try:
            parsed = json.loads(config or "{}")
            if parsed.get("task_type") != "text_to_image":
                raise ValueError("Provider task_type must be text_to_image")
            api_key = resolve_api_key(parsed)
            if not api_key:
                raise ValueError("API key not found. Set it in Hhhapi Provider.")
            adapter = get_adapter(parsed.get("protocol", ""))
            result = adapter.call_text_to_image(
                parsed, api_key, prompt, negative_prompt, size, aspect_ratio, quality, n, seed, output_format
            )
            images = result.pop("images", [])
            tensor = pil_list_to_batch(images)
            url = (result.get("image_urls") or [""])[0]
            return (tensor, dumps(result), url)
        except Exception as exc:
            error = error_payload("image_api_error", str(exc), parsed)
            return (ExecutionBlocker(None), dumps(error), "")


class HhhapiImageToImage:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "mask": ("MASK",),
            "image2": ("IMAGE",),
            "image3": ("IMAGE",),
            "image4": ("IMAGE",),
            "image5": ("IMAGE",),
            "image6": ("IMAGE",),
            "image7": ("IMAGE",),
            "image8": ("IMAGE",),
        }
        return {
            "required": {
                "config": ("STRING", {"default": "", "forceInput": True}),
                "image1": ("IMAGE",),
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "size": (IMAGE_SIZES, {"default": "1024x1024"}),
                "quality": (QUALITIES, {"default": "auto"}),
                "n": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 0xFFFFFFFFFFFFFFFF}),
                "output_format": (FORMATS, {"default": "png"}),
                "multi_image_mode": (["multipart_repeated_field", "concat_grid"], {"default": "multipart_repeated_field"}),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "response_json", "image_url")
    FUNCTION = "run"
    CATEGORY = "Hhhapi"

    def run(
        self,
        config,
        image1,
        prompt,
        size,
        quality,
        n,
        seed,
        output_format,
        multi_image_mode,
        mask=None,
        image2=None,
        image3=None,
        image4=None,
        image5=None,
        image6=None,
        image7=None,
        image8=None,
    ):
        parsed = {}
        try:
            parsed = json.loads(config or "{}")
            if parsed.get("task_type") != "image_to_image":
                raise ValueError("Provider task_type must be image_to_image")
            api_key = resolve_api_key(parsed)
            if not api_key:
                raise ValueError("API key not found. Set it in Hhhapi Provider.")
            adapter = get_adapter(parsed.get("protocol", ""))
            images = [img for img in [image1, image2, image3, image4, image5, image6, image7, image8] if img is not None]
            result = adapter.call_image_to_image(
                parsed, api_key, prompt, images, mask, size, quality, n, seed, output_format, multi_image_mode
            )
            pil_images = result.pop("images", [])
            tensor = pil_list_to_batch(pil_images)
            url = (result.get("image_urls") or [""])[0]
            return (tensor, dumps(result), url)
        except Exception as exc:
            error = error_payload("image_api_error", str(exc), parsed)
            return (ExecutionBlocker(None), dumps(error), "")

